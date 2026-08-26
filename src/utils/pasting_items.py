import os
import random
import time
from typing import Callable
from queue import Queue, Empty
from PySide6.QtGui import Qt
from PySide6.QtCore import Signal, QThread, QMargins, QTimer, QFileSystemWatcher, QObject
from PySide6.QtWidgets import QMainWindow, QTableWidget, QTableWidgetItem, QRadioButton, QWidget,\
    QHBoxLayout, QButtonGroup, QVBoxLayout, QPushButton, QCheckBox, QFrame, QScrollArea, QLabel,\
    QProgressBar
from src.utils.os_utils import move_to_trash, extract_filename_from_path, count_tree, \
    volume_of_path, TRASH_UNAVAILABLE, \
    copy_tree_with_progress, get_all_item_names_in_directory, extract_parent_path_from_path, \
    increment_max_item_name, delete_item, size_bytes_to_string
from src.ui_components.misc_widgets.dialogs_and_messages import QDialogFreeTextButtons, \
    prompt_trash_unavailable
from src.non_ui_components.user_actions import (UserAction_CopyPasteItemsUsingThread,
                                                UserAction_MoveFilesUsingThread)
from src.shared.vars import logger as logger


class PastingManager:
    """
    Orchestrates several pasters (each responsible for a unique thread), and maintains a queue
    of pasting tasks in case all pasters are busy.
    """
    # A paste finishing faster than this never shows a progress window at all
    SHOW_PROGRESS_AFTER_MS = 1000
    # How long app shutdown is willing to wait for in-flight copies to notice they should stop
    SHUTDOWN_WAIT_MS = 3000

    def __init__(self, caller, num_threads: int = 6, sample_every_ms: int = 3000):
        self.caller = caller
        self.paster_objects = {}
        self.update_ui_timers = {}
        # What show_pending_pasting_process should display, per paster, once its timer fires
        self._pending_ui_info = {}
        for i in range(num_threads):
            paster_object = PasterObject(self.caller)
            paster_object.pasting_finished.connect(self.pasting_finished)
            paster_object.progress.connect(self.update_pasting_progress)
            paster_object.id = i
            self.paster_objects[i] = paster_object
            # Connected once here, not per paste, so the timer stays cancellable and repeated
            # pastes don't stack up connections
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda paster_id=i: self.show_pending_pasting_process(paster_id))
            self.update_ui_timers[i] = timer
        self.tasks_queue = []
        self.start_next_queue_timer = QTimer()
        self.start_next_queue_timer.timeout.connect(self.handle_next_task_if_thread_available)
        self.sample_every_ms = sample_every_ms

        self.running_processes_ui = PastingProcessesUi()
        # self.running_processes_ui.show()
        self.running_processes_ui.break_pasting_signal.connect(self.break_pasting_process)

        self.queue_msg = QDialogFreeTextButtons(
            button_texts=["Cancel all"],
            title_text="Paste request added to queue",
            message_text="Too many pasting processes are currently running. Your latest paste "
                         "request will start automatically when possible",
            btn_width=100
            )

    def show_pending_pasting_process(self, paster_id: int):
        """
        Shows the progress row for a paste that is still running SHOW_PROGRESS_AFTER_MS in. Short
        pastes never get here, because pasting_finished stops the timer first.
        """
        info = self._pending_ui_info.pop(paster_id, None)
        paster = self.paster_objects.get(paster_id)
        if info is None or paster is None or paster.is_available:
            return
        self.running_processes_ui.show()
        num_items = str(len(info['copied_file_paths']))
        self.running_processes_ui.add_widget(
            paster_id, f"Pasting {num_items} items to {info['dest_path']}")

    def update_pasting_progress(self, paster_id: int, files_done: int, files_total: int,
                                bytes_done: int, bytes_total: int):
        self.running_processes_ui.update_progress(paster_id, files_done, files_total,
                                                  bytes_done, bytes_total)

    def paste(self,
              copied_file_paths: list[str],
              dest_path: str,
              delete_source_after_paste: bool,  # copy-paste VS cut-paste
              when_done: Callable = None,
              # rename_item_names_in_dest: list[tuple[str, str]] = [],
              source_dest_pairs: list[tuple[str, str, str]] = []):
        logger.info("paste_items_via_thread")
        available_paster = self.take_first_available_paster()
        if available_paster is None:
            # All pasters are busy -> add task to queue and wait for a paster to become available
            logger.info("All pasters are busy")
            self.tasks_queue.append({'copied_file_paths': copied_file_paths,
                                     'dest_path': dest_path,
                                     'delete_source_after_paste': delete_source_after_paste,
                                     'when_done': when_done,
                                     # 'rename_item_names_in_dest': rename_item_names_in_dest,
                                     'source_dest_pairs': source_dest_pairs})
            self.queue_msg.show()
            self.start_next_queue_timer.start(self.sample_every_ms)
        else:
            # Idle paster found -> use it to paste items
            logger.info("Idle paster found")
            self._pending_ui_info[available_paster.id] = {'copied_file_paths': copied_file_paths,
                                                          'dest_path': dest_path}
            self.update_ui_timers[available_paster.id].start(self.SHOW_PROGRESS_AFTER_MS)
            self.paste_using_paster(available_paster,
                                    copied_file_paths, dest_path, delete_source_after_paste,
                                    when_done,
                                    # rename_item_names_in_dest,
                                    source_dest_pairs)

    def take_first_available_paster(self):
        logger.info("take_first_available_paster")
        for i, paster in self.paster_objects.items():
            if paster.is_available:
                # Found available paster !
                paster.lock()
                return paster
        # No available pasters found
        return None

    def paste_using_paster(self,
                           paster,
                           copied_file_paths: list[str],
                           dest_path: str,
                           delete_source_after_paste: bool,  # copy-paste VS cut-paste
                           when_done: Callable = None,
                           # rename_item_names_in_dest: list[tuple[str, str]] = [],
                           source_dest_pairs: list[tuple[str, str, str]] = []):
        logger.info("paste_using_paster")
        paster.run(copied_file_paths, dest_path, delete_source_after_paste, when_done,
                   # rename_item_names_in_dest,
                   source_dest_pairs)

    def handle_next_task_if_thread_available(self):
        logger.info("handle_next_task_if_thread_available")
        if len(self.tasks_queue) >= 1:
            available_paster = self.take_first_available_paster()
            if available_paster is not None:
                task = self.tasks_queue.pop(0)
                self.paste_using_paster(available_paster,
                                        task['copied_file_paths'],
                                        task['dest_path'],
                                        task['delete_source_after_paste'],
                                        task['when_done'],
                                        # task['rename_item_names_in_dest'],
                                        task['source_dest_pairs'],
                                        )
        if len(self.tasks_queue)==0:
            self.queue_msg.hide()
            self.start_next_queue_timer.stop()

    def safetly_kill_all_threads(self):
        logger.info("safetly_kill_all_threads")
        # Ask everyone to stop first, then wait once - waiting on each in turn would serialise
        # the timeouts and make quitting take N times as long
        paster_objects = list(self.paster_objects.values())
        for paster_object in paster_objects:
            paster_object.break_thread_run(wait=False)
        for paster_object in paster_objects:
            if paster_object.pasting_thread is not None:
                paster_object.pasting_thread.wait(self.SHUTDOWN_WAIT_MS)
        self.paster_objects.clear()

    def break_pasting_process(self, paster_obj_id: int):
        logger.info(f"break_pasting_process ({paster_obj_id})")
        # Only asks the thread to stop; the row is removed when the thread's finished signal
        # reaches pasting_finished. Removing it here too ran the teardown twice.
        self.paster_objects[paster_obj_id].break_thread_run(wait=False)
    
    def pasting_finished(self, paster_obj_id: int):
        logger.info(f"pasting_finished ({paster_obj_id})")
        # Cancels the "show progress after 1s" timer if the paste beat it
        if paster_obj_id in self.update_ui_timers:
            self.update_ui_timers[paster_obj_id].stop()
        self._pending_ui_info.pop(paster_obj_id, None)
        self.running_processes_ui.remove_widget(paster_obj_id)
        if len(self.running_processes_ui.widgets_list) == 0:
            self.running_processes_ui.hide()



class PasterObject(QWidget):
    pasting_finished = Signal(int)
    # paster id, files_done, files_total, bytes_done, bytes_total
    progress = Signal(int, int, int, int, int)

    """
    Wrapper over a thread which does the actual pasting
    """
    def __init__(self, caller=None):
        super().__init__()
        self.caller = caller
        self.queue = Queue()
        self.pasting_thread = None
        self._is_available = True
        self.id = random.randint(0, 1000000)
        self.dialog = None
        # Where to place the paste dialogs; set by QDialogPasteExistingItem once one is shown
        self.position_on_screen = None


    @property
    def is_available(self):
        if self.pasting_thread is None:
            return True
        return not self.pasting_thread.isRunning() and self._is_available

    def lock(self):
        self._is_available = False

    def break_thread_run(self, wait=False):
        """
        Asks the copy to stop. Does NOT wait by default - the worker checks the stop flag before
        every file, and cleanup happens on its finished signal. Waiting here would block the UI
        thread (this is called from the Cancel button and from app shutdown).
        """
        if self.pasting_thread is not None:
            self.pasting_thread.stop()
            if wait:
                self.pasting_thread.wait()

    def _init_pasting_thread(self):
        self.pasting_thread = PasteItemsThread(results_queue = self.queue)
        self.pasting_thread.finished.connect(self.pasting_thread_finished)
        self.pasting_thread.progress.connect(self._relay_progress)

    def _relay_progress(self, files_done, files_total, bytes_done, bytes_total):
        self.progress.emit(self.id, files_done, files_total, bytes_done, bytes_total)

    def process_user_response(self, response: str = None, apply_to_all: bool = False):
        """
        Called by QDialogPasteExistingItem when the user answers. Name conflicts are already
        resolved up front by TableWithRadioButtons, so what reaches here is the paste-error
        acknowledgement - the paster was already released in pasting_thread_finished, so this
        only has to dismiss the dialog.
        """
        logger.info(f"PasterObject.process_user_response ({response})")
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self,
            copied_file_paths: list[str] = [],
            dest_path: str = "",
            delete_source_after_paste: bool = False,  # copy-paste VS cut-paste
            when_done: Callable = None,
            source_dest_pairs: list[tuple[str, str, str]] = [],):

        self.copied_file_paths = copied_file_paths.copy()
        self.dest_path = dest_path
        self.delete_source_after_paste = delete_source_after_paste
        self.when_done = when_done
        self.source_dest_pairs = source_dest_pairs

        self.items_pasted = []

        if len(self.source_dest_pairs) >= 1:
            if self.pasting_thread is None:
                self._init_pasting_thread()
            self.pasting_thread.set_run_params(self.source_dest_pairs,
                                               self.delete_source_after_paste)
            self.pasting_thread.start()    # NOTE THERE'S A DIFFERENCE BETWEEN start() and run().
                                           # run() will not emit the finished signal in the end
                                           # and therefore both isRunning and isFinished will
                                           # always return False

    def _take_last_result(self) -> dict:
        """
        Reads the worker's result without ever blocking the UI thread. PasteItemsThread always
        puts exactly one result before run() returns, and `finished` only fires after that, so
        there is normally one item waiting. Drains anything extra rather than leaving it for the
        next paste on this paster to pick up.
        """
        result = {}
        while True:
            try:
                result = self.queue.get_nowait()
            except Empty:
                return result

    def pasting_thread_finished(self, thread_id: int = 0):
        logger.info(f"pasting_thread_finished ({thread_id})")
        self.time_finished = time.time()

        if self.when_done is not None:
            self.when_done()

        result = self._take_last_result()
        call_type = result.get('call_type')

        if call_type == 'paste_error':
            item_name = result['item_name']
            self.dialog = QDialogPasteExistingItem(self,
                                                   button_texts=['Ok'],
                                                   title_text = f'File {item_name} Could not be pasted. Aborting paste operation.',
                                                   message_text = 'Paste error',
                                                   item_name=item_name,
                                                   encompassing_obj=self)
            if self.position_on_screen is not None:
                self.dialog.move(self.position_on_screen)
            self.dialog.show()

        elif call_type == 'item_already_exist':
            item_name = result['item_name']
            self.dialog = QDialogPasteExistingItem(self,
                                                   button_texts=['Skip', 'Replace', 'Keep both'],
                                                   title_text = f'File {item_name} already exists in the destination folder',
                                                   message_text = 'What do you want to do?',
                                                   item_name=item_name,
                                                   encompassing_obj=self,
                                                   include_checkbox=True)
            if self.position_on_screen is not None:
                self.dialog.move(self.position_on_screen)
            self.dialog.show()

        # A move whose sources couldn't be trashed copied the items over but left the
        # originals behind - say so, rather than letting the move look like it worked.
        sources_not_trashed = result.get('sources_not_trashed', [])
        if len(sources_not_trashed) > 0:
            prompt_trash_unavailable(volume_of_path(sources_not_trashed[0]),
                                     len(sources_not_trashed))

        # A cancelled paste still pasted whatever it got through before stopping, so it is
        # recorded for undo exactly like a completed one
        if call_type in ('finished_all', 'forced_to_stop', 'paste_error'):
            self.items_pasted = self.items_pasted + result.get('items_pasted', [])
            if len(self.items_pasted) > 0:
                if self.delete_source_after_paste:
                    self.caller.keep_last_action(
                        UserAction_MoveFilesUsingThread(self.items_pasted,
                                                        self.caller))
                else:
                    self.caller.keep_last_action(
                        UserAction_CopyPasteItemsUsingThread(self.items_pasted,
                                                             self.caller))
                self.caller.select_pasted_items_where_ui_is_in_path(
                    path = self.dest_path,
                    items = [extract_filename_from_path(i[1]) for i in self.items_pasted]
                )

        self._is_available = True
        self.pasting_finished.emit(self.id)



class PasteItemsThread(QThread):
    """
    Wrapper which performs the actual pasting of items from source to destination.
    """
    # files_done, files_total, bytes_done, bytes_total
    progress = Signal(int, int, int, int)

    # Never emit progress more often than this. One signal per copied file would flood the UI
    # thread's event queue on a big folder, which is itself a freeze.
    PROGRESS_INTERVAL_SECONDS = 0.1

    def __init__(self,
                 results_queue: Queue = None,  # queue used to send output to the caller class
                 parent=None):
        super().__init__(parent)
        self.results_queue = results_queue
        self._forced_to_stop = False

    def set_run_params(self,
                       source_dest_pairs: list[tuple[str, str, str]],  # [(from, to, when_conflicting), ...]
                       delete_source_after_paste: bool):
        self.source_dest_pairs = source_dest_pairs
        self.delete_source_after_paste = delete_source_after_paste
        # Cleared here, not in run(): a cancel arriving between start() and the thread actually
        # entering run() would otherwise be silently discarded
        self._forced_to_stop = False

    def stop(self):
        """Asks the copy to abort. Safe to call from the UI thread - it never blocks."""
        self._forced_to_stop = True

    def run(self):
        items_skipped = []
        items_not_pasted = []
        items_pasted = []
        # Sources a move (cut + paste) copied over but could not remove, because their
        # volume has no Trash. Reported once at the end so the move doesn't silently
        # turn into a copy.
        sources_not_trashed = []
        result = {'call_type': 'finished_all'}

        try:
            # Sizing pass first, so progress can be reported against a real total. This walks
            # every source tree, which is exactly why it belongs here and not on the UI thread.
            files_total = 0
            bytes_total = 0
            for src, _dest, _when_conflicting in self.source_dest_pairs:
                if self._forced_to_stop:
                    break
                if os.path.exists(src):
                    num_files, num_bytes = count_tree(src)
                    files_total += num_files
                    bytes_total += num_bytes

            self._files_done = 0
            self._bytes_done = 0
            self._last_progress_emit = 0.0
            self.progress.emit(0, files_total, 0, bytes_total)

            def on_file_done(num_bytes: int):
                self._files_done += 1
                self._bytes_done += num_bytes
                now = time.monotonic()
                if now - self._last_progress_emit >= self.PROGRESS_INTERVAL_SECONDS:
                    self._last_progress_emit = now
                    self.progress.emit(self._files_done, files_total,
                                       self._bytes_done, bytes_total)

            for src, dest, when_conflicting in self.source_dest_pairs:
                if self._forced_to_stop:
                    result = {'call_type': 'forced_to_stop'}
                    break

                if not os.path.exists(src):
                    continue
                filename = extract_filename_from_path(src)

                # Item with identical name already in destination path
                if os.path.exists(dest):
                    if when_conflicting == 'skip_item':
                        items_skipped.append((src, dest))
                        continue
                    elif when_conflicting == 'keep_both':
                        # change dest path to indicate duplication
                        dest_dir = extract_parent_path_from_path(dest)
                        dest = increment_max_item_name(get_all_item_names_in_directory(dest_dir),
                                                       extract_parent_path_from_path(dest),
                                                       filename)
                    elif when_conflicting == 'replace':
                        delete_item(dest)
                    # This part should never be reached:
                    else:
                        result = {'call_type': 'item_already_exist', 'item_name': dest}
                        break

                # Perform the actual pasting
                success = 0  # Nothing happened
                if src != dest:
                    success = copy_tree_with_progress(src, dest,
                                                      should_stop=lambda: self._forced_to_stop,
                                                      on_file_done=on_file_done)

                if success == -2:
                    # Cancelled part-way through this item; its partial copy has been removed
                    result = {'call_type': 'forced_to_stop'}
                    break
                elif success == -1:
                    result = {'call_type': 'paste_error', 'item_name': filename}
                    break

                if success == 1:
                    items_pasted.append((src, dest))
                elif success == 0:
                    items_not_pasted.append((src, dest))
                if self.delete_source_after_paste:
                    if move_to_trash(src) == TRASH_UNAVAILABLE:
                        sources_not_trashed.append(src)

            self.progress.emit(self._files_done, files_total, self._bytes_done, bytes_total)

        except Exception:
            # Without this the `finally` below would be the only thing standing between an
            # unexpected error and a caller waiting forever for a result
            logger.exception("PasteItemsThread.run failed")
            result = {'call_type': 'paste_error',
                      'item_name': extract_filename_from_path(self.source_dest_pairs[0][0])
                      if self.source_dest_pairs else ''}
        finally:
            # Single writer to the queue, on every exit path
            result.update({'items_skipped': items_skipped,
                           'items_not_pasted': items_not_pasted,
                           'items_pasted': items_pasted,
                           'sources_not_trashed': sources_not_trashed})
            self.results_queue.put(result)




class RadioButtonGroupWidget(QWidget):
    def __init__(self, gap_size: int = None, texts: list[str] = None):
        super().__init__()
        # Create a horizontal layout for the radio buttons
        layout = QHBoxLayout()
        if gap_size is not None:
            layout.setContentsMargins(QMargins(0, 0, 0, 0))  # No extra margins
            layout.setSpacing(gap_size)
        self.setLayout(layout)

        # Create radio buttons
        if texts is None:
            self.skip = QRadioButton("Skip item")
            self.replace = QRadioButton("Replace")
            self.keep_both = QRadioButton("Keep both")
        else:
            self.skip = QRadioButton(texts[0])
            self.replace = QRadioButton(texts[1])
            self.keep_both = QRadioButton(texts[2])

        self.skip.setChecked(True)

        # Add buttons to a button group (ensures mutual exclusivity)
        self.button_group = QButtonGroup(self)
        self.button_group.addButton(self.skip)
        self.button_group.addButton(self.replace)
        self.button_group.addButton(self.keep_both)

        # Add buttons to the layout
        layout.addWidget(self.skip)
        layout.addWidget(self.replace)
        layout.addWidget(self.keep_both)


class TableWithRadioButtons(QMainWindow):
    def __init__(self, caller, dest_path: str, conflicting_item_names: list[str] = [], copied_file_paths: list[str] = [], delete_source_after_paste: bool = False):
        super().__init__()

        self.caller = caller
        self.dest_path = dest_path
        self.copied_file_paths = copied_file_paths
        self.conflicting_item_names = conflicting_item_names
        self.delete_source_after_paste = delete_source_after_paste

        self.set_table_data(conflicting_item_names)
        main_buttons_layout = self.create_main_buttons_layout()
        apply_to_all_layout = self.create_apply_to_all_layout()

        self.cancel_btn.clicked.connect(self.close)
        self.apply_btn.clicked.connect(self.apply_user_selection)

        # Set up the main window layout
        main_widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addLayout(apply_to_all_layout)
        layout.addLayout(main_buttons_layout)
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

        # Window configuration
        self.setWindowTitle("Item(s) already exists in the destination folder")
        self.table.setColumnWidth(0, 350)  # Wider column for item names
        self.table.setColumnWidth(1, 100)  # Narrower column for radio buttons
        self.resize(700, 400)

    def set_table_data(self, item_names):
        # Set up the main table widget
        self.table = QTableWidget(len(item_names), 2)  # 10 rows, 2 columns
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setHorizontalHeaderLabels(["Item", "What do you want to do?"])
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(1, 1)
        self.table.horizontalHeader().setStretchLastSection(True)

        # Populate the table
        default_row_height = self.table.verticalHeader().defaultSectionSize()
        for i, item in enumerate(item_names):
            # Set item in the first column
            self.table.setItem(i, 0, QTableWidgetItem(item))

            # Add radio button group in the second column
            radio_buttons_widget = RadioButtonGroupWidget()
            self.table.setCellWidget(i, 1, radio_buttons_widget)
            self.table.setRowHeight(i, default_row_height * 1.1)

    def create_apply_to_all_layout(self):
        self.apply_to_all_buttons = \
            RadioButtonGroupWidget(gap_size=24, texts=['Skip all  ', 'Replace all', 'Keep all'])
        self.apply_to_all_buttons.skip.clicked.connect(
            lambda: self.check_action_for_all_items('skip_item'))
        self.apply_to_all_buttons.replace.clicked.connect(
            lambda: self.check_action_for_all_items('replace'))
        self.apply_to_all_buttons.keep_both.clicked.connect(
            lambda: self.check_action_for_all_items('keep_both'))
        apply_to_all_layout = QHBoxLayout()
        apply_to_all_layout.setContentsMargins(0, 0, 32, 0)
        apply_to_all_layout.addWidget(self.apply_to_all_buttons)
        apply_to_all_layout.setAlignment(Qt.AlignRight)
        return apply_to_all_layout

    def check_action_for_all_items(self, action: str):
        for i in range(0, len(self.conflicting_item_names)):
            if action == 'skip_item':
                self.table.cellWidget(i, 1).skip.setChecked(True)
            elif action == 'replace':
                self.table.cellWidget(i, 1).replace.setChecked(True)
            elif action == 'keep_both':
                self.table.cellWidget(i, 1).keep_both.setChecked(True)

    def create_main_buttons_layout(self, buttons_width=70):
        self.cancel_btn = QPushButton('Cancel')
        self.apply_btn = QPushButton('Apply')

        self.cancel_btn.setFixedWidth(buttons_width)
        self.apply_btn.setFixedWidth(buttons_width)

        main_buttons_layout = QHBoxLayout()
        main_buttons_layout.addWidget(self.apply_btn)
        main_buttons_layout.addWidget(self.cancel_btn)
        main_buttons_layout.setStretchFactor(self.apply_btn, 1)
        main_buttons_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        return main_buttons_layout

    def apply_user_selection(self):
        user_selections = {}
        for i in range(0, len(self.conflicting_item_names)):
            user_selections[self.conflicting_item_names[i]] = (
                self.table.cellWidget(i, 1).button_group.checkedButton().text().\
                    replace(" ", "_").lower())
        self.close()

        item_names_to_keep_both = [x for x in user_selections if user_selections[x] == 'keep_both']
        items_to_skip = [k for k, v in user_selections.items() if v == 'skip_item']
        self.copied_file_paths = [x for x in self.copied_file_paths
                                  if extract_filename_from_path(x) not in items_to_skip]
        if len(self.copied_file_paths) > 0:
            self.caller.paste_items_via_thread(self.copied_file_paths,
                                               self.dest_path,
                                               self.delete_source_after_paste,
                                               item_names_to_keep_both=item_names_to_keep_both)


class QDialogPasteExistingItem(QDialogFreeTextButtons):
    def __init__(self, caller, button_texts, item_name, encompassing_obj=None,
                 include_checkbox=False, title_text="", message_text=""):
        super().__init__(button_texts, title_text=title_text, message_text=message_text)
        self.caller = caller
        self.include_checkbox = include_checkbox
        self.encompassing_obj = encompassing_obj

        if include_checkbox:
            self.do_the_same_for_all_items_checkbox = QCheckBox()
            self.do_the_same_for_all_items_checkbox.setText("Repeat for all following items")
            self.layout.addWidget(self.do_the_same_for_all_items_checkbox)

    @property
    def position(self):
        if hasattr(self.encompassing_obj, 'position_on_screen'):
            return self.encompassing_obj.position_on_screen
        else:
            return self.pos

    @position.setter
    def position(self, new_pos):
        self.encompassing_obj.position_on_screen = new_pos

    def keyPressEvent(self, event):
        self.position = self.pos()
        if (event.key() == Qt.Key.Key_Escape):
            self.generate_click_on_button('Cancel all')
            self.done(Qt.WidgetAttribute.WA_DeleteOnClose.value)

    def accept(self):
        self.done(Qt.WidgetAttribute.WA_DeleteOnClose.value)
        self.position = self.pos()
        if self.include_checkbox:
            self.caller.process_user_response(
                self.selected_button_, self.do_the_same_for_all_items_checkbox.isChecked()
            )
        else:
            self.caller.process_user_response(self.selected_button_, None)

    def reject(self):
        self.position = self.pos()
        super().reject()




class SinglePasteProcessUiWidget(QFrame):
    btn_clicked = Signal()

    def __init__(self, button_text: str = "", top_text: str = "", width: int = 300, height: int = 150):
        super().__init__()
        self.setWindowTitle("Framed Widget")
        self.setFixedSize(width, height)

        # Set black border using QFrame styles
        self.setObjectName("frame_only");
        self.setStyleSheet("QFrame#frame_only{border: 1px solid rgb(175, 175, 175);}")
        self.setFrameShape(QFrame.Box)
        self.setFrameShadow(QFrame.Plain)
        self.setLineWidth(1)  # Thickness of the border

        # Create the QLabel for the top-left corner
        label = QLabel(top_text, self)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setTextVisible(True)

        self.detail_label = QLabel("", self)

        self.button = QPushButton(button_text)
        self.button.setFixedWidth(80)
        self.button.setFixedHeight(20)
        self.button.clicked.connect(self.emitButtonClickedSignal)

        layout = QVBoxLayout(self)
        layout.addWidget(label, 0, Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.detail_label, 0, Qt.AlignLeft)
        layout.addWidget(self.button, 0, Qt.AlignLeft | Qt.AlignBottom)
        layout.setContentsMargins(5, 10, 5, 10)
        self.setLayout(layout)

    def update_progress(self, files_done: int, files_total: int,
                        bytes_done: int, bytes_total: int):
        """
        Plain widget updates on the UI thread, driven by queued signals from the copy thread.
        Deliberately no processEvents() - that would run a nested event loop.
        """
        if bytes_total > 0:
            percent = int(100 * bytes_done / bytes_total)
        elif files_total > 0:
            percent = int(100 * files_done / files_total)
        else:
            percent = 0
        self.progress_bar.setValue(min(100, max(0, percent)))
        self.detail_label.setText(
            f"{files_done} of {files_total} files "
            f"({size_bytes_to_string(bytes_done)} of {size_bytes_to_string(bytes_total)})")

    def emitButtonClickedSignal(self):
        self.btn_clicked.emit()


class PastingProcessesUi(QWidget):
    break_pasting_signal = Signal(int)
    
    def __init__(self, width_per_widget: int = 1000, height_per_widget: int = 130):
        super().__init__()
        self.setWindowTitle("Currently running pasting processes")
        self.height_per_widget = height_per_widget
        self.width_per_widget = width_per_widget
        self.setGeometry(100, 100, 400, self.height_per_widget)
        self.widgets_list = []
        self.setStyleSheet("background-color: rgb(235, 235, 235);")

        # Scroll area for added widgets
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setContentsMargins(0, 0, 0, 0)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(0)
        
        self.scroll_content.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_content)

        # Main layout for the window
        self.main_layout = QVBoxLayout(self)
        self.main_layout.addWidget(self.scroll_area)

    def update_progress(self, widget_id: int, files_done: int, files_total: int,
                        bytes_done: int, bytes_total: int):
        # No-op until the row exists - progress starts arriving before the 1s show timer fires
        for w in self.widgets_list:
            if w.id == widget_id:
                w.update_progress(files_done, files_total, bytes_done, bytes_total)
                return

    def remove_widget(self, widget_id: int):
        widget_ind_to_remove = [i for i, w in enumerate(self.widgets_list) if w.id == widget_id]
        if len(widget_ind_to_remove) > 0:
            widget = self.widgets_list.pop(widget_ind_to_remove[0])
            widget.deleteLater()
            # self.resize(self.width(), widget.height() - 100)
            self.resize(self.width(), (1 + len(self.widgets_list)) * self.height_per_widget)

    def add_widget(self, id: int, text: str = ""):
        new_widget = SinglePasteProcessUiWidget("Cancel", text,
                                                width=self.width_per_widget,
                                                height=self.height_per_widget)
        new_widget.id = id
        new_widget.btn_clicked.connect(self.emit_stop_pasting_signal(self, id))
        self.scroll_layout.addWidget(new_widget)
        self.widgets_list.append(new_widget)
        self.resize(self.width(), (1 + len(self.widgets_list)) * self.height_per_widget)

    def add_widget0(self, id: int, text: str = ""):
        separator = QFrame(self)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet(f"#buttons_frame{{margin-top: 100px;}}")
        separator.setFixedHeight(120)
        # separator.setContentsMargins(0, 0, 0, 0)

        new_widget = QWidget()
        new_widget.id = id
        new_widget.setStyleSheet("background-color: white;")

        new_widget.setFixedHeight(self.height_per_widget)
        layout = QVBoxLayout(new_widget)

        layout.addWidget(separator)
        new_label = QLabel(text)
        new_label.setContentsMargins(0, 0, 0, 0)
        # new_label.setStyleSheet("padding: 0px; border: 0px solid transparent;")
        layout.addWidget(new_label, 0, Qt.AlignLeft | Qt.AlignTop)
        cancel_btn = QPushButton(text="Cancel", parent=new_widget)
        cancel_btn.setFixedWidth(100)
        # cancel_btn.setStyleSheet("padding: 0px; border: 0px solid transparent;")
        cancel_btn.clicked.connect(self.emit_stop_pasting_signal(self, id))
        layout.addWidget(cancel_btn, 2, Qt.AlignRight | Qt.AlignBottom)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setContentsMargins(5, 10, 5, 10)   # left, top, right, bottom

        self.scroll_layout.addWidget(new_widget)
        self.widgets_list.append(new_widget)
        self.resize(self.width(), (1 + len(self.widgets_list)) * self.height_per_widget)

    class emit_stop_pasting_signal(QObject):

        def __init__(self, caller, id):
            super().__init__()
            self.id = id
            self.caller = caller

        def __call__(self):
            self.caller.break_pasting_signal.emit(self.id)
