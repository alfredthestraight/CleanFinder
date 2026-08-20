from PySide6 import QtCore
from PySide6.QtWidgets import (QTableView, QAbstractItemView, QLineEdit, QSizePolicy, QVBoxLayout,
                               QHBoxLayout, QToolButton, QHeaderView, QDialog, QDialogButtonBox,
                               QStyledItemDelegate, QStyle)
from PySide6.QtCore import Signal, QObject, QThread, Qt
from PySide6.QtGui import QFont
import os
import time
import pandas as pd
from src.utils.os_utils import run_file_in_terminal
from src.utils.utils import enable_home_end_keys
from src.data_models import SimplePandasModel
from src.shared.vars import conf_manager as conf


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
            self.encompassing_obj.quit_all_threads()


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


class SearchWindow_threaded(QDialog):
    def __init__(self, root_path, encompassing_ui):
        super(SearchWindow_threaded, self).__init__()
        self.root_path = root_path
        self.encompassing_ui = encompassing_ui
        self.threads = {}
        # Search state, initialised here (and not only when a search starts) so that the
        # scrollbar handler and the search-option toggles can be triggered before the
        # first search without raising AttributeError.
        self.files_iter = None
        self.search_finished = True
        self.chunk_ended = True
        self.worker = None
        # Every worker started for the current search; cleared when the search is abandoned.
        self.workers = []
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

        self.search_box = QLineEdit()
        self.search_box.setFont(QFont(conf.TEXT_FONT, conf.TEXTBOX_FONT_SIZE))
        # self.search_box.setStyleSheet(conf.TEXTBOX_STYLE)
        self.search_box.setStyleSheet("""
            QLineEdit{background-color: rgb(255,255,255);
            border:  1px solid lightgrey;
            };""")
        self.search_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        enable_home_end_keys(self.search_box)

        # Toggles to the right of the textbox. Both restart the search when clicked.
        self.case_sensitive_toggle = self.create_search_option_toggle('Aa', 'Case sensitive')
        # A horizontal (sideways) arrow for "stay on this level, do not descend into subfolders".
        self.current_dir_only_toggle = self.create_search_option_toggle(
            '\u2194', 'Only search current directory')

        self.search_row_layout = QHBoxLayout()
        self.search_row_layout.addWidget(self.search_box)
        self.search_row_layout.addWidget(self.case_sensitive_toggle)
        self.search_row_layout.addWidget(self.current_dir_only_toggle)
        self.search_layout.addLayout(self.search_row_layout)

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

        # Main layout
        self.overall_layout.addLayout(self.search_layout)
        self.overall_layout.addLayout(self.results_layout)
        self.overall_layout.addWidget(self.button_box)

        self.setLayout(self.overall_layout)

    def create_search_option_toggle(self, text: str, tooltip: str) -> QToolButton:
        toggle = QToolButton()
        toggle.setText(text)
        toggle.setToolTip(tooltip)
        toggle.setCheckable(True)
        toggle.setChecked(False)
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
            return
        self.cancel_running_workers()
        self.empty_results_table()
        self.quit_all_threads()
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

    def on_search_option_toggled(self, _checked: bool):
        # A search already ran (or is still running) -> throw its results away and search
        # again from scratch under the new search options.
        if self.files_iter is not None:
            self.start_search()

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
        for worker in self.workers:
            worker.cancel()
        self.workers = []

    def next_n_items_finder_thread(self, n: int = 100):
        new_thread_index = len(self.threads)
        self.threads[new_thread_index] = {'thread': QThread(), 'is_alive': True}
        new_thread = self.threads[new_thread_index]['thread']
        self.worker = Worker(self, n, self.files_iter)
        self.workers.append(self.worker)
        self.worker.moveToThread(new_thread)
        new_thread.started.connect(self.worker.run)
        new_thread.start()

    def quit_all_threads(self):
        for thread in self.threads.keys():
            if self.threads[thread]['is_alive']:
                self.threads[thread]['thread'].quit()
                self.threads[thread]['is_alive'] = False

    def accept(self):
        self.cancel_running_workers()
        self.quit_all_threads()
        super(SearchWindow_threaded, self).accept()

    def reject(self):
        self.cancel_running_workers()
        self.quit_all_threads()
        super(SearchWindow_threaded, self).reject()

    def double_click_on_search_result(self, index):
        item_path = os.path.join(self.root_path, index.data())
        if os.path.isdir(item_path):
            self.encompassing_ui.encompassing_uis_manager.create_new_window(item_path)
        else:
            run_file_in_terminal(item_path)
