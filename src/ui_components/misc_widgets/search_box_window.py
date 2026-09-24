from PySide6 import QtCore
from PySide6.QtWidgets import (QTableView, QAbstractItemView, QLineEdit, QSizePolicy, QVBoxLayout,
                               QHBoxLayout, QToolButton, QLabel, QHeaderView, QDialog,
                               QDialogButtonBox, QPushButton, QStyledItemDelegate, QStyle)
from PySide6.QtCore import Signal, QObject, QThread, Qt
from PySide6.QtGui import QFont, QFontMetrics
import os
import time
import pandas as pd
from src.utils.os_utils import run_file_in_terminal
from src.utils.utils import enable_home_end_keys
from src.data_models import SimplePandasModel
from src.shared.vars import conf_manager as conf


# The three states of the status label under the search box.
SEARCHING_TEXT = 'Searching...'
SEARCH_FINISHED_TEXT = 'Search finished'
PARTIAL_RESULTS_TEXT = 'Showing partial results. Scroll to end to continue'

# config.json keys holding the last state of the two toggle buttons next to the search box, as
# 'Y'/'N'. See ConfigurationsManager for how they are loaded and written back.
SEARCH_CASE_SENSITIVE_CONFIG_KEY = 'SEARCH_CASE_SENSITIVE'
SEARCH_CURRENT_DIR_ONLY_CONFIG_KEY = 'SEARCH_CURRENT_DIR_ONLY'

# How long quit_all_threads() waits for a search thread to actually stop before giving up on it.
# Bounded, because Worker.run() can sit for a long time inside next(files_iter) walking a slow or
# disconnected volume, and an unbounded wait would freeze the whole window.
THREAD_SHUTDOWN_WAIT_MS = 2000

# Search threads that did not stop within THREAD_SHUTDOWN_WAIT_MS. Their Worker is still executing
# run(), so freeing it would leave the running thread and the dialog's still-registered
# 'chunk_finished' connection pointing at freed memory - which is what crashed the app. Keeping the
# record here holds both objects alive instead; finished ones are dropped by
# _discard_finished_abandoned_threads() the next time a search thread is started.
# The Worker also references its dialog (Worker.encompassing_obj), so a record kept here keeps the
# dialog alive too - which is what the still-running run() needs, since it reads the dialog's
# results table.
_ABANDONED_SEARCH_THREADS = []


def _discard_finished_abandoned_threads():
    """Drop the records of abandoned threads that have since stopped on their own."""
    # Edited in place rather than rebound, so the list object itself stays the one every other
    # reference to it is holding.
    _ABANDONED_SEARCH_THREADS[:] = [record for record in _ABANDONED_SEARCH_THREADS
                                    if not record['thread'].isFinished()]


# The two buttons at the bottom of the window. Both are styled explicitly so they look like each
# other: an unstyled QPushButton is drawn by the native macOS style, which paints the dialog's
# default button blue by itself. Read out of the config on every call (like the toggles above the
# results do), so a colour changed in Edit -> Edit configurations shows up in the next window.
def blue_button_style():
    return """
        QPushButton{background-color: """ + conf.WINDOWS_FILE_EXPLORER_BLUE + """;
        color: white;
        border: 1px solid """ + conf.WINDOWS_FILE_EXPLORER_BLUE + """;
        padding: 4px 18px;
        }
        QPushButton:pressed{background-color: white;
        color: """ + conf.WINDOWS_FILE_EXPLORER_BLUE + """;
        }"""


def grey_button_style():
    # Lighter than conf.BASE_GREY_COLOR (rgb(236, 236, 236)), which sat too close to the window's
    # own background; the border is what keeps the button readable as a button at this lightness.
    return """
        QPushButton{background-color: rgb(249, 249, 249);
        color: black;
        border: 1px solid lightgrey;
        padding: 4px 18px;
        }
        QPushButton:pressed{background-color: white;
        }"""


def relative_paths_iterator(path: str, current_dir_only: bool = False):
    """Yield every item under `path`, as a path relative to it.

    current_dir_only=False walks the whole tree (depth-first); True lists only the items
    sitting directly in `path`, where the relative path is just the item's name.
    """
    if current_dir_only:
        try:
            names = os.listdir(path)
        except OSError:
            # os.walk silently skips folders it cannot read, so do the same here.
            names = []
        for name in names:
            yield name
    else:
        for root, dirs, files in os.walk(path, topdown=True):
            files_and_dirs = files + dirs
            for name in files_and_dirs:
                yield os.path.join(root, name).replace(path + '/', '')


def files_iterator(path: str, txt: str, case_sensitive: bool = False,
                   current_dir_only: bool = False):
    # Lower-case the searched text once here rather than per item, so the per-item cost of a
    # case-insensitive search is a single .lower() call on the path.
    needle = txt if case_sensitive else txt.lower()
    for relative_path in relative_paths_iterator(path, current_dir_only):
        haystack = relative_path if case_sensitive else relative_path.lower()
        if needle in haystack:
            yield relative_path


class Worker(QObject):
    finished = Signal()
    progress = Signal(int)
    # Emitted (with the worker itself) once a chunk has ended, so the dialog can update the
    # status label. run() executes on a background thread and must not touch widgets - going
    # through a signal connected to a method of the dialog gets the update onto the UI thread.
    chunk_finished = Signal(object)

    def __init__(self, encompassing_obj, num_items_to_find, files_iter):
        self.encompassing_obj = encompassing_obj
        self.num_items_to_find = num_items_to_find
        # The iterator is bound to the worker at construction time instead of being read off
        # the dialog on every item: if the search is restarted mid-chunk, this worker must not
        # silently switch over to the new search's iterator (which would steal results from it).
        self.files_iter = files_iter
        self.chunk_ended = False
        # Set from the UI thread by SearchWindow_threaded.cancel_running_workers(). QThread.quit()
        # cannot stop this loop (it never returns to the thread's event loop), so the loop checks
        # this flag once per item instead: a cancelled worker stops within one item rather than
        # finishing its whole chunk and appending stale results to the table.
        self.cancelled = False
        super().__init__()

    def cancel(self):
        self.cancelled = True

    def run(self):
        i = 0
        while i < self.num_items_to_find:
            if self.cancelled:
                break
            try:
                nextfile = next(self.files_iter)
            except StopIteration:
                # Only the current search may declare itself finished: a cancelled worker
                # exhausting its old iterator must not mark the new search as complete.
                if not self.cancelled:
                    self.encompassing_obj.search_finished = True
                break
            # Re-checked after next(), which can block for a long time while walking the tree.
            if self.cancelled:
                break
            self.encompassing_obj.results_table.model().insertRows(new_row=[nextfile])
            i += 1
        self.chunk_ended = True
        # A cancelled worker belongs to an abandoned search, so it must not touch the threads
        # of the search that replaced it.
        if not self.cancelled:
            # Only the signal is emitted from here. Stopping the threads is left to
            # on_chunk_finished() on the UI thread: quit_all_threads() waits on each thread, and
            # this method *is* one of those threads, so calling it here would be a thread waiting
            # on itself.
            self.chunk_finished.emit(self)


class NoElideDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # Adjust the font metrics to measure the text
        # font_metrics = QFontMetrics(option.font)
        text = index.data()

        # Set up the painter to avoid eliding text
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        # Draw the text directly in the item rectangle
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         text)


class ElidingLabel(QLabel):
    """A QLabel that never forces its container to grow.

    A plain QLabel holding a long path would push the dialog's minimum width past the path's
    full length, so the window could not be made narrower. This one is allowed to shrink and
    shortens the text with '...' in the middle instead, keeping the full text in the tooltip.
    """

    def __init__(self, text: str = ''):
        super().__init__()
        self.full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str):
        self.full_text = text
        self.setToolTip(text)
        self.refresh_elided_text()

    def refresh_elided_text(self):
        # super() so this does not re-enter setText() and clobber self.full_text.
        super().setText(QFontMetrics(self.font()).elidedText(
            self.full_text, Qt.TextElideMode.ElideMiddle, self.width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_elided_text()


class SearchWindow_threaded(QDialog):
    def __init__(self, root_path, encompassing_ui):
        super(SearchWindow_threaded, self).__init__()
        self.root_path = root_path
        self.encompassing_ui = encompassing_ui
        # One record per search thread started: {'thread': QThread, 'worker': Worker,
        # 'is_alive': bool}. The record is what keeps the Worker referenced - a Worker cannot be
        # given a Qt parent, because QObject.moveToThread() refuses to move a parented object -
        # so it must stay referenced for exactly as long as its thread can still be running it.
        self.threads = []
        # Search state, initialised here (and not only when a search starts) so that the
        # scrollbar handler and the search-option toggles can be triggered before the
        # first search without raising AttributeError.
        self.files_iter = None
        self.search_finished = True
        self.chunk_ended = True
        self.worker = None
        # Every worker started for the current search; cleared by quit_all_threads(), once the
        # threads running them have actually stopped.
        self.workers = []
        # False once the dialog has been closed, so the window that owns it can tell whether it
        # still has a usable search window or has to build a new one. Same flag (and same purpose)
        # as PropertiesWindowCalculateSizeInThread.is_currently_presented.
        self.is_currently_presented = True
        self.initUI()
        self.installEventFilter(self)
        self.search_box.setFocus()

    def initUI(self):
        self.setFocus()
        self.setWindowTitle('Search')
        self.setGeometry(300, 300, 300, 300)
        self.resize(500, 600)

        # Layout for General tab
        self.overall_layout = QVBoxLayout()
        self.search_layout = QVBoxLayout()
        self.results_layout = QVBoxLayout()

        # The folder the search runs in, shown above the textbox.
        self.path_label = ElidingLabel(self.root_path)
        self.path_label.setFont(QFont(conf.TEXT_FONT, conf.TEXTBOX_FONT_SIZE))
        self.path_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.path_label.setStyleSheet("""
            QLabel{background-color: transparent;
            border: 1px solid transparent;
            padding-left: 2px;
            }""")
        self.search_layout.addWidget(self.path_label)

        self.search_box = QLineEdit()
        self.search_box.setFont(QFont(conf.TEXT_FONT, conf.TEXTBOX_FONT_SIZE))
        # self.search_box.setStyleSheet(conf.TEXTBOX_STYLE)
        self.search_box.setStyleSheet("""
            QLineEdit{background-color: rgb(255,255,255);
            border:  1px solid lightgrey;
            };""")
        self.search_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        enable_home_end_keys(self.search_box)

        # Toggles to the right of the textbox. Both restart the search when clicked, and both
        # start out at whatever the user last left them at (conf, saved to config.json), so the
        # choice survives closing the search window and quitting the app.
        self.case_sensitive_toggle = self.create_search_option_toggle(
            'Aa', 'Case sensitive', SEARCH_CASE_SENSITIVE_CONFIG_KEY)
        # A horizontal (sideways) arrow for "stay on this level, do not descend into subfolders".
        self.current_dir_only_toggle = self.create_search_option_toggle(
            '\u2194', 'Only search current directory', SEARCH_CURRENT_DIR_ONLY_CONFIG_KEY)

        self.search_row_layout = QHBoxLayout()
        self.search_row_layout.addWidget(self.search_box)
        self.search_row_layout.addWidget(self.case_sensitive_toggle)
        self.search_row_layout.addWidget(self.current_dir_only_toggle)
        self.search_layout.addLayout(self.search_row_layout)

        # Says whether the search is running, has walked the whole tree, or has paused after a
        # chunk. Empty (and invisible) until the first search starts.
        self.status_label = ElidingLabel('')
        self.status_label.setFont(QFont(conf.TEXT_FONT, conf.TEXTBOX_FONT_SIZE))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setStyleSheet("""
            QLabel{background-color: transparent;
            border: 1px solid transparent;
            padding-left: 2px;
            }""")
        self.search_layout.addWidget(self.status_label)

        # Results:
        self.results_table = QTableView()
        self.results_table.setItemDelegate(NoElideDelegate())
        self.results_table.setStyleSheet("""QTableView{border: 0px;  margin: 0px;}""")
        # Interactive (not Stretch) so the user can drag the column boundary in the
        # header to resize it; the header must be visible for the drag handle to exist.
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.results_table.horizontalHeader().setVisible(True)
        # Let a widened column scroll horizontally so long paths can be read in full.
        self.results_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.model = SimplePandasModel(data=pd.DataFrame(columns=['Filename']))
        self.results_table.setModel(self.model)
        # Start the single column filling the window; the user can drag it wider/narrower.
        self.results_table.setColumnWidth(0, 470)
        self.results_table.doubleClicked.connect(self.double_click_on_search_result)
        self.results_table.verticalScrollBar().valueChanged.connect(self.scrollbar_reached_bottom)
        self.results_layout.addWidget(self.results_table)

        # Create the buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # Starts the same search the Enter key starts. No focus and no auto-default, so it
        # cannot take the Enter key away from the search box (the toggles above do the same).
        self.search_button = QPushButton('Search')
        self.search_button.setFont(QFont(conf.TEXT_FONT, conf.TEXTBOX_FONT_SIZE))
        self.search_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.search_button.setAutoDefault(False)
        self.search_button.setStyleSheet(blue_button_style())
        self.search_button.clicked.connect(self.on_search_button_clicked)

        # Search is the window's main action, so it gets the blue; Close is the plain grey one.
        # macOS makes Close the dialog's default button (and paints it blue), hence setDefault.
        self.close_button = self.button_box.button(QDialogButtonBox.StandardButton.Close)
        self.close_button.setFont(QFont(conf.TEXT_FONT, conf.TEXTBOX_FONT_SIZE))
        self.close_button.setAutoDefault(False)
        self.close_button.setDefault(False)
        self.close_button.setStyleSheet(grey_button_style())

        # Search on the left of the bottom row, Close on the right.
        self.bottom_row_layout = QHBoxLayout()
        self.bottom_row_layout.addWidget(self.search_button)
        self.bottom_row_layout.addStretch()
        self.bottom_row_layout.addWidget(self.button_box)

        # Main layout
        self.overall_layout.addLayout(self.search_layout)
        self.overall_layout.addLayout(self.results_layout)
        self.overall_layout.addLayout(self.bottom_row_layout)

        self.setLayout(self.overall_layout)

    def create_search_option_toggle(self, text: str, tooltip: str,
                                    config_key: str) -> QToolButton:
        toggle = QToolButton()
        toggle.setText(text)
        toggle.setToolTip(tooltip)
        toggle.setCheckable(True)
        # Remembered from the last time the user clicked it (see on_search_option_toggled).
        # Set before the signal is connected below, so restoring it does not count as a click
        # and does not start a search in a window that has not been asked for one yet.
        toggle.setChecked(bool(getattr(conf, config_key)))
        # No focus, otherwise the button would swallow the Enter key that starts a search.
        toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        toggle.setFont(QFont(conf.TEXT_FONT, conf.TEXTBOX_FONT_SIZE))
        toggle.setStyleSheet("""
            QToolButton{background-color: rgb(255,255,255);
            border: 1px solid lightgrey;
            padding-left: 6px;
            padding-right: 6px;
            color: black;
            }
            QToolButton:checked{background-color: """ + conf.WINDOWS_FILE_EXPLORER_BLUE + """;
            color: white;
            }""")
        toggle.toggled.connect(self.on_search_option_toggled)
        return toggle

    def empty_results_table(self):
        self.results_table.model().clear_all_data()
        self.update()

    def start_search(self):
        if self.search_box.text() == '':
            # No search is running, so a leftover "Search finished" next to an empty box would lie.
            self.status_label.setText('')
            return
        # Stop the previous search before the table is emptied, not after: a worker that is still
        # running would otherwise append its last rows into the table this just cleared.
        self.cancel_running_workers()
        self.quit_all_threads()
        self.empty_results_table()
        self.search_finished = False
        self.chunk_ended = False
        # Stateful (for the lifecycle of the search-box) iterator which will be
        # used by all workers
        self.files_iter = files_iterator(self.root_path, self.search_box.text(),
                                         self.case_sensitive_toggle.isChecked(),
                                         self.current_dir_only_toggle.isChecked())
        # Find the first n items (the following n items will be looked for once
        # user scrolls all the way down):
        self.next_n_items_finder_thread()

    def on_search_button_clicked(self, _checked: bool = False):
        # clicked emits the button's checked state as its first argument, so the slot has to
        # accept it - start_search() takes none.
        self.start_search()

    def on_search_option_toggled(self, _checked: bool):
        self.save_search_options()
        # A search already ran (or is still running) -> throw its results away and search
        # again from scratch under the new search options.
        if self.files_iter is not None:
            self.start_search()

    def save_search_options(self):
        """Write both toggles' states into the config, so the next search window starts with them.

        Both are written whichever one was clicked - there are only two, and that avoids having
        to work out which button sent the signal. conf.set_attr updates the live attribute and
        the dict that gets written to config.json; the file itself is written when the last
        window closes (UiWindowManager.on_ui_close), which is how every other option is saved.
        """
        conf.set_attr(SEARCH_CASE_SENSITIVE_CONFIG_KEY,
                      'Y' if self.case_sensitive_toggle.isChecked() else 'N')
        conf.set_attr(SEARCH_CURRENT_DIR_ONLY_CONFIG_KEY,
                      'Y' if self.current_dir_only_toggle.isChecked() else 'N')

    def keyPressEvent(self, e):
        if (e.key() == QtCore.Qt.Key.Key_Return) or (e.key() == QtCore.Qt.Key.Key_Enter):   # Enter
            self.start_search()
        elif e.key() == QtCore.Qt.Key.Key_Escape:    # Enter
            self.reject()

    def scrollbar_reached_bottom(self, value: int):
        if value == self.results_table.verticalScrollBar().maximum():
            print("Scrollbar has reached the end")
            if not self.search_finished and self.worker.chunk_ended:
                self.next_n_items_finder_thread()
                time.sleep(0.5)

    def cancel_running_workers(self):
        # Tell every worker of the previous search to stop. They check the flag once per item,
        # so they stop appending rows within one item instead of finishing their chunk and
        # mixing the old search's results into the new one.
        #
        # This only raises the flag; it deliberately does not drop self.workers. A worker whose
        # run() is still executing must stay referenced - freeing it leaves the running thread and
        # the 'chunk_finished' connection registered on this dialog pointing at a destroyed
        # QObject, which is what segfaulted the app. quit_all_threads() releases them instead,
        # after waiting for the threads to actually stop.
        for worker in self.workers:
            worker.cancel()

    def next_n_items_finder_thread(self, n: int = 100):
        _discard_finished_abandoned_threads()
        new_thread = QThread()
        self.worker = Worker(self, n, self.files_iter)
        self.workers.append(self.worker)
        self.threads.append({'thread': new_thread, 'worker': self.worker, 'is_alive': True})
        self.worker.moveToThread(new_thread)
        # Connected to a method of the dialog (not a lambda): the dialog lives on the UI thread,
        # so Qt queues the signal onto it instead of running the slot on the worker's thread.
        self.worker.chunk_finished.connect(self.on_chunk_finished)
        new_thread.started.connect(self.worker.run)
        # This is the single place a chunk begins - both the first one and the ones started by
        # scrolling to the end of the results.
        self.status_label.setText(SEARCHING_TEXT)
        new_thread.start()

    def on_chunk_finished(self, worker):
        """A chunk of results has just ended: either the whole tree was walked, or the chunk
        filled up and the search is waiting for the user to scroll down for more."""
        # The signal is queued, so one emitted by an abandoned search can arrive after a new
        # search has already started - that one must not overwrite the new search's status.
        if worker is not self.worker or worker.cancelled:
            return
        self.status_label.setText(SEARCH_FINISHED_TEXT if self.search_finished
                                  else PARTIAL_RESULTS_TEXT)
        # run() used to stop the threads itself, but it runs on one of the very threads that are
        # waited on below. Doing it here means it happens on the UI thread instead. The search is
        # only paused (the user may scroll for another chunk), so self.worker is kept as the
        # handle scrollbar_reached_bottom() reads - only the finished threads are released.
        self._stop_and_release_threads()

    def _stop_and_release_threads(self):
        """Stop every search thread, then release the workers the stopped ones were running.

        Order matters and is the whole point of this method: a worker may only be dereferenced
        once the thread executing its run() has actually stopped, and its 'chunk_finished'
        connection to this dialog may only be torn down once the worker itself is about to go.
        A worker freed while its thread is still inside run() leaves both the thread and that
        connection pointing at a destroyed QObject, which is what segfaulted the app.
        """
        still_running = []
        for record in self.threads:
            thread, worker = record['thread'], record['worker']
            if record['is_alive']:
                thread.quit()
                record['is_alive'] = False
            if thread.wait(THREAD_SHUTDOWN_WAIT_MS):
                try:
                    worker.chunk_finished.disconnect(self.on_chunk_finished)
                except (RuntimeError, TypeError):
                    # Already disconnected, or the C++ object is gone - either way there is
                    # nothing left to disconnect
                    pass
            else:
                # Still inside run() (a slow or unresponsive volume). Hand the record over rather
                # than freeing a worker the thread is still executing.
                still_running.append(record)

        _ABANDONED_SEARCH_THREADS.extend(still_running)
        self.threads = []
        self.workers = []

    def quit_all_threads(self):
        """Stop the search entirely: release the threads, then let go of the current worker too.

        Used when the search is being replaced or the dialog is closing, as opposed to
        on_chunk_finished(), which only pauses one and keeps self.worker.
        """
        # Raise the cancel flags first. Without it the wait() below would sit for the full
        # timeout on any worker still walking the tree, freezing the window for that long.
        # cancel() is idempotent, so calling this straight after cancel_running_workers()
        # (which every caller but the tests does) costs nothing.
        self.cancel_running_workers()
        self._stop_and_release_threads()
        self.worker = None

    def accept(self):
        self.is_currently_presented = False
        self.cancel_running_workers()
        self.quit_all_threads()
        super(SearchWindow_threaded, self).accept()

    def reject(self):
        self.is_currently_presented = False
        self.cancel_running_workers()
        self.quit_all_threads()
        super(SearchWindow_threaded, self).reject()

    def closeEvent(self, event):
        # QDialog.closeEvent already routes to reject(), which does the thread teardown; this is
        # here so the flag is lowered even if that ever stops being true.
        self.is_currently_presented = False
        super(SearchWindow_threaded, self).closeEvent(event)

    def set_root_path(self, root_path: str):
        """Point an already-open search window at a different folder and start it over.

        The window that owns this dialog reuses it instead of building a new one (see
        ui.launch_search_window), so pressing the search shortcut again has to reset it to the
        state a freshly-built window would have been in.
        """
        self.cancel_running_workers()
        self.quit_all_threads()
        self.root_path = root_path
        self.path_label.setText(root_path)
        self.empty_results_table()
        self.status_label.setText('')
        self.files_iter = None
        self.search_finished = True
        self.chunk_ended = True
        self.search_box.setFocus()

    def double_click_on_search_result(self, index):
        item_path = os.path.join(self.root_path, index.data())
        if os.path.isdir(item_path):
            self.encompassing_ui.encompassing_uis_manager.create_new_window(item_path)
        else:
            run_file_in_terminal(item_path)
