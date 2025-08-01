import os
import random
import time
from typing import Callable
from queue import Queue
from PySide6.QtGui import Qt
from PySide6.QtCore import Signal, QThread, QMargins, QTimer, QFileSystemWatcher, QObject
from PySide6.QtWidgets import QMainWindow, QTableWidget, QTableWidgetItem, QRadioButton, QWidget,\
    QHBoxLayout, QButtonGroup, QVBoxLayout, QPushButton, QCheckBox, QFrame, QScrollArea, QLabel
from src.utils.os_utils import move_to_trash, extract_filename_from_path, copy_and_paste_item, \
    get_all_item_names_in_directory, extract_parent_path_from_path, increment_max_item_name, \
    delete_item
from src.ui_components.misc_widgets.dialogs_and_messages import QDialogFreeTextButtons
from src.non_ui_components.user_actions import (UserAction_CopyPasteItemsUsingThread,
                                                UserAction_MoveFilesUsingThread)
from src.shared.vars import logger as logger


class PastingManager:
    """
    Orchestrates several pasters (each responsible for a unique thread), and maintains a queue
    of pasting tasks in case all pasters are busy.
    """
    def __init__(self, caller, num_threads: int = 6, sample_every_ms: int = 3000):
        self.caller = caller
        self.paster_objects = {}
        self.update_ui_timers = {}
        for i in range(num_threads):
            paster_object = PasterObject(self.caller)
            paster_object.pasting_finished.connect(self.pasting_finished)
            paster_object.id = i
            self.paster_objects[i] = paster_object
            self.update_ui_timers[i] = QTimer()
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

    def add_pasting_process_to_ui(self, paster, copied_file_paths, dest_path):
        if not paster.is_available:
            self.running_processes_ui.show()
            num_items = str(len(copied_file_paths))
            self.running_processes_ui.add_widget(paster.id, f"Pasting {num_items} items to {dest_path}")

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
            self.update_ui_timers[available_paster.id].singleShot(1000, lambda: self.add_pasting_process_to_ui(available_paster, copied_file_paths, dest_path))
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
        while len(self.paster_objects) > 0:
            k = list(self.paster_objects.keys())[0]
            paster_object = self.paster_objects.pop(k)
            paster_object.break_thread_run()

    def break_pasting_process(self, paster_obj_id: int):
        logger.info(f"break_pasting_process ({paster_obj_id})")
        self.paster_objects[paster_obj_id].break_thread_run()
        self.pasting_finished(paster_obj_id)
    
    def pasting_finished(self, paster_obj_id: int):
        logger.info(f"pasting_finished ({paster_obj_id})")
        self.update_ui_timers[paster_obj_id].stop()
        self.running_processes_ui.remove_widget(paster_obj_id)
        if len(self.running_processes_ui.widgets_list) == 0:
            self.running_processes_ui.hide()



class PasterObject(QWidget):
    pasting_finished = Signal(int)

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


    @property
    def is_available(self):
        if self.pasting_thread is None:
            return True
        return not self.pasting_thread.isRunning() and self._is_available

    def lock(self):
        self._is_available = False

    def break_thread_run(self, wait=True):
        if self.pasting_thread is not None:
            self.pasting_thread._forced_to_stop = True
            if wait:
                self.pasting_thread.wait()

    def _init_pasting_thread(self):
        self.pasting_thread = PasteItemsThread(results_queue = self.queue)
        self.pasting_thread.finished.connect(self.pasting_thread_finished)

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

    def pasting_thread_finished(self, thread_id: int = 0):
        logger.info(f"pasting_thread_finished ({thread_id})")
        self.time_finished = time.time()

        if self.when_done is not None:
            self.when_done()

        result = self.queue.get()
        if len(result) == 0:
            self._is_available = True
            return

        if result['call_type'] == 'paste_error':
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

        elif result['call_type'] == 'finished_all':
            print("result['call_type'] == 'finished_all' ", time.time())
            self.items_pasted = self.items_pasted + result['items_pasted']
            if len(self.items_pasted) > 0:
                if self.delete_source_after_paste:
                    print("self.caller.keep_last_action - UserAction_MoveFilesUsingThread ", time.time())
                    self.caller.keep_last_action(
                        UserAction_MoveFilesUsingThread(self.items_pasted,
                                                        self.caller))
                else:
                    print("self.caller.keep_last_action - UserAction_CopyPasteItemsUsingThread ", time.time())
                    self.caller.keep_last_action(
                        UserAction_CopyPasteItemsUsingThread(self.items_pasted,
                                                             self.caller))
                print("self.caller.select_pasted_items_where_ui_is_in_path ", time.time())
                self.caller.select_pasted_items_where_ui_is_in_path(
                    path = self.dest_path,
                    items = [extract_filename_from_path(i[1]) for i in self.items_pasted]
                )

        elif result['call_type'] == 'item_already_exist':
            item_name = result['item_name']
            # 'items_skipped': items_skipped,
            # 'items_not_pasted': items_not_pasted,
            # 'items_pasted': items_pasted})
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

        self._is_available = True
        self.pasting_finished.emit(self.id)



class PasteItemsThread(QThread):
    """
    Wrapper which performs the actual pasting of items from source to destination.
    """
    def __init__(self,
                 results_queue: Queue = None,  # queue used to send output to the caller class
                 parent=None):
        super().__init__(parent)
        self.results_queue = results_queue

    def set_run_params(self,
                       source_dest_pairs: list[tuple[str, str, str]],  # [(from, to, when_conflicting), ...]
                       delete_source_after_paste: bool):
        self.source_dest_pairs = source_dest_pairs
        self.delete_source_after_paste = delete_source_after_paste

    def run(self):
        self._forced_to_stop = False

        success = 0  # Nothing happened
        items_skipped = []
        items_not_pasted = []
        items_pasted = []

        for i, d in enumerate(self.source_dest_pairs):
            # time.sleep(0.3)
            if self._forced_to_stop:
                self.results_queue.put({'call_type': 'forced_to_stop',
                                        'items_skipped': items_skipped,
                                        'items_not_pasted': items_not_pasted,
                                        'items_pasted': items_pasted})
                print("PasteItemsThread.run - 'forced_to_stop' ", time.time())
                break

            src, dest, when_conflicting = d
            if not os.path.exists(src):
                continue
            filename = extract_filename_from_path(src)

            # Item with identical name already in destination path
            if os.path.exists(dest):
                if when_conflicting == 'skip_item':
                    print("items_skipped.append((src, dest)) ", time.time())
                    items_skipped.append((src, dest))
                    continue
                elif when_conflicting == 'keep_both':
                    # change dest path to indicate duplication
                    dest_dir = extract_parent_path_from_path(dest)
                    dest = increment_max_item_name(get_all_item_names_in_directory(dest_dir),
                                                   extract_parent_path_from_path(dest), filename)
                elif when_conflicting == 'replace':
                    print("delete_item ", time.time())
                    delete_item(dest)
                # This part should never be reached:
                else:
                    self.results_queue.put({'call_type': 'item_already_exist',
                                            'item_name': dest,
                                            'items_skipped': items_skipped,
                                            'items_not_pasted': items_not_pasted,
                                            'items_pasted': items_pasted})
                    print("self.results_queue.put - 'item_already_exist' ", time.time())
                    return

            # Perform the actual pasting
            if src != dest:
                print("success = copy_and_paste_item ", time.time())
                success = copy_and_paste_item(src, dest_item_full_path=dest)

            if success >= 0:
                # self.items_finished.emit()
                if success == 1:
                    print("items_pasted.append ", time.time())
                    items_pasted.append((src, dest))
                elif success == 0:
                    print("items_not_pasted.append ", time.time())
                    items_not_pasted.append((src, dest))
                if self.delete_source_after_paste:
                    print("move_to_trash(src) ", time.time())
                    move_to_trash(src)
                    print("Finished move_to_trash(src) ", time.time())
            elif success == -1:
                self.results_queue.put({'call_type': 'paste_error', 'item_name': filename,
                                        'items_skipped': items_skipped,
                                        'items_not_pasted': items_not_pasted,
                                        'items_pasted': items_pasted})
                print("self.results_queue.put - 'paste_error' ", time.time())
                return

        self.results_queue.put({'call_type': 'finished_all',
                                'items_skipped': items_skipped,
                                'items_not_pasted': items_not_pasted,
                                'items_pasted': items_pasted})
        print("self.results_queue.put - 'finished_all' ", time.time())




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

        self.button = QPushButton(button_text)
        self.button.setFixedWidth(80)
        self.button.setFixedHeight(20)
        self.button.clicked.connect(self.emitButtonClickedSignal)

        layout = QVBoxLayout(self)
        layout.addWidget(label, 2, Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.button, 2, Qt.AlignLeft | Qt.AlignBottom)
        layout.setContentsMargins(5, 10, 5, 10)
        self.setLayout(layout)

    def emitButtonClickedSignal(self):
        self.btn_clicked.emit()


class PastingProcessesUi(QWidget):
    break_pasting_signal = Signal(int)
    
    def __init__(self, width_per_widget: int = 1000, height_per_widget: int = 80):
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
