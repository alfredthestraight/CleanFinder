import os
import zipfile
from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QFont, QColor, QBrush, QCursor
from PySide6.QtCore import Qt, QItemSelectionModel, Signal, QThread, QTimer
from src.shared.vars import conf_manager as conf, logger as logger
from src.utils.os_utils import (open_application, extract_filename_from_path, delete_item,
                                move_to_trash, extract_extension_from_path, dir_)
from src.utils.utils import get_max_integer_suffix_among_strings_with_prefix
from src.shared.vars import threads_server
from PySide6.QtWidgets import (QMessageBox, QLabel, QLineEdit, QPushButton, QHBoxLayout, QDialog,
                               QVBoxLayout)
from src.ui_components.misc_widgets.dialogs_and_messages import message_box_w_arrow_keys_enabled


def map_shortcut_name_to_func(file_explorer_obj, action_name: str):
    return {
        "NEW_WINDOW": file_explorer_obj.add_new_ui,
        "UP": file_explorer_obj.go_to_parent_dir,
        "ENTER": file_explorer_obj.on_enter,
        "BACK": file_explorer_obj.go_to_previous_path,
        "FORWARD": file_explorer_obj.go_to_next_path,
        "COPY_SELECTED_ITEMS_TO_CLIPBOARD": file_explorer_obj.copy_selected_items_to_clipboard,
        "CUT": file_explorer_obj.cut_item,
        "PASTE_FROM_CLIPBOARD": file_explorer_obj.paste_items_from_clipboard,
        "SELECT_ALL": file_explorer_obj.select_all,
        "EXTEND_SELECTION_UPWARDS": file_explorer_obj.extend_selection_upwards,
        "EXTEND_SELECTION_DOWNWARDS": file_explorer_obj.extend_selection_downwards,
        "PERMANENTLY_DELETE": file_explorer_obj.permanently_remove_items,
        "LAUNCH_FIND_WINDOW": file_explorer_obj.encompassing_ui.launch_search_window,
        "UNDO_LAST_ACTION": file_explorer_obj.undo_last_action,
        "REDO_LAST_UNDONE_ACTION": file_explorer_obj.redo_last_undone_action,
        "SELECT_ALL_UNTIL_END": file_explorer_obj.select_all_items_from_curr_to_end,
        "SELECT_ALL_UNTIL_START": file_explorer_obj.select_all_items_from_curr_to_head}[action_name]


class change_items_names_case:
    def __init__(self, encompassing_obj, case):
        self.case = case
        self.encompassing_obj = encompassing_obj

    def to_lowercase(self, filename):
        self.encompassing_obj.replace_item_name(filename, filename.lower())

    def to_uppercase(self, filename):
        self.encompassing_obj.replace_item_name(filename, filename.upper())

    def __call__(self):
        for path in self.encompassing_obj.selected_items_paths:
            filename = extract_filename_from_path(path)
            if self.case == 'lower':
                self.to_lowercase(filename)
            elif self.case == 'upper':
                self.to_uppercase(filename)


class open_file_as_app:
    def __init__(self, app_path):
        self.app_path = app_path

    def __call__(self):
        open_application(self.app_path)


def next_new_dir_name(curr_directories_names: list[str], new_dir_name: str):
    """
    When user creates a new folder, and there are already folders named "New folder" and
    "New folder 1", the new folder name should then be "New folder 2"
    """
    max_suff = get_max_integer_suffix_among_strings_with_prefix(curr_directories_names,
                                                                new_dir_name)
    if max_suff is None:
        suff = ' 1'
    else:
        suff = ' ' + str(max_suff + 1)
    return new_dir_name + suff


class paths_history():
    """
    Keeps track of user's paths history to support forward and backward navigation
    """
    def __init__(self, path: str):
        self.paths = [path]
        self.curr_index = 0

    def clear_history(self):
        self.paths = []
        self.curr_index = 0

    def has_history(self):
        return len(self.paths) > self.curr_index + 1

    def has_forward_paths(self):
        return 0 < self.curr_index

    def add_path(self, newpath: str):
        self.reset_head_to_current_path()
        self.paths.insert(0, newpath)

    def prev_path(self):
        if self.has_history():
            return self.paths[self.curr_index + 1]
        else:
            return None

    def next_path(self):
        if self.has_forward_paths():
            return self.paths[self.curr_index - 1]
        else:
            return None

    def curr_path(self):
        return self.paths[self.curr_index]

    def move_to_path_in_direction(self, direction: int):
        # direction = 1: forward, direction = -1: backward
        self.curr_index = self.curr_index + direction

    def move_to_prev_path(self):
        self.curr_index = self.curr_index + 1

    def move_to_next_path(self):
        self.curr_index = self.curr_index - 1

    def reset_head_to_current_path(self):
        self.paths = self.paths[self.curr_index:]
        self.curr_index = 0

    def remove_paths_and_subpaths_from_history(self, paths: list[str]):
        indices_of_paths_removed = []
        for i, p in enumerate(self.paths):
            for p1 in paths:
                if p == p1 or p.startswith(p1 + '/'):
                    indices_of_paths_removed.append(i)
        self.curr_index = self.curr_index - len([i for i in indices_of_paths_removed if i <= self.curr_index])
        self.paths = [p for i, p in enumerate(self.paths) if i not in indices_of_paths_removed]



class RowSelectionExtender:
    """
    When user presses the arrow buttons while holding down the shift key, the selection should be
    extended according to the logic specified here
    """
    def __init__(self, encompassing_obj):
        self.encompassing_obj = encompassing_obj
        self.overall_direction = 0

    def reset(self):
        self.overall_direction = 0

    def calc_selection_update(self, direction: int, current_rows: list[int]) -> (int, int, int):
        # Extend selection
        if self.overall_direction == direction:
            method_id = 3
            selection_type = 2
            if direction == 1:
                affected_row = max(current_rows) + 1
            elif direction == -1:
                affected_row = min(current_rows) - 1
        # Subtract from selection
        else:
            method_id = 4
            selection_type = 4
            if direction == 1:
                affected_row = min(current_rows)
            elif direction == -1:
                affected_row = max(current_rows)
        return method_id, selection_type, affected_row

    def __call__(self, direction: int = 1):
        selected_indices = self.encompassing_obj.selectedIndexes()
        if len(selected_indices) == 0:
            return
        current_rows = self.encompassing_obj._extract_item_rows_from_indices(selected_indices)

        # One row already selected, and a new one is now requested to be selected
        if len(current_rows) == 1:
            self.overall_direction = direction

        if len(current_rows) >= 1:
            method_id, selection_type, affected_row = self.calc_selection_update(direction, current_rows)
            self.encompassing_obj.keep_selection_as_prev(self.encompassing_obj.selectedIndexes())
            if selection_type == 2:
                self.encompassing_obj.selectionModel().select(
                    self.encompassing_obj.index_at_row_and_col(affected_row, 0),
                    QItemSelectionModel.SelectionFlag.Rows | QItemSelectionModel.SelectionFlag.Select
                )
            else:
                self.encompassing_obj.selectionModel().select(
                    self.encompassing_obj.index_at_row_and_col(affected_row, 0),
                    QItemSelectionModel.SelectionFlag.Rows | QItemSelectionModel.SelectionFlag.Deselect
                )
            # Two rows were already selected, but user deselected one of them (one remaining)
            if len(current_rows) == 2 and selection_type == 4:
                self.overall_direction = 1


class QLineEdit_EditFinenameExcludingExtension(QLineEdit):

    def focusInEvent(self, event):
        super().focusInEvent(event)
        split_text = self.text().split('.')
        if len(split_text) == 1:
            self.setSelection(0, len(self.text()))
        elif len(split_text[0]) == 0 or len(split_text[1]) == 0:
            self.setSelection(0, len(self.text()))
        elif len(split_text) == 2:
            self.setSelection(0, len(split_text[0]))
        else:
            # Select allexcept the extension
            newtext = '.'.join(split_text[:-1])
            self.setSelection(0, len(newtext))


class MyStyledItem(QtWidgets.QStyledItemDelegate):

    editingFinishedSignal = Signal(str, str)

    def __init__(self, view, margin, radius, border_color,
                 border_width,
                 grid_type=conf.FILE_EXPLORER_TABLE_GRID_TYPE_NAME,
                 parent=None):
        """
        margin: distance between border and top of cell
        radius: radius of rounded corner
        border_color: color of border
        border_width: width of border
        """
        super().__init__(parent)
        self.view = view
        self.margin = margin
        self.radius = radius
        self.border_color = border_color
        self.border_width = border_width
        self.grid_type = grid_type
        self.encompassing_obj = None

        self.set_row_hover_brush_color()
        self.set_disabled_row_hover_brush_color()

        self.cut_items = []
        self.cut_items_path = ''

    def set_row_hover_brush_color(self,
                                  r: int = conf.FILE_EXPLORER_ROW_HOVER_R,
                                  g: int = conf.FILE_EXPLORER_ROW_HOVER_G,
                                  b: int = conf.FILE_EXPLORER_ROW_HOVER_B):
        brushColor = QColor()
        brushColor.setRgb(r, g, b)
        self.row_hover_brush = QBrush()
        self.row_hover_brush.setColor(brushColor)
        self.row_hover_brush.setStyle(Qt.BrushStyle.SolidPattern)

    def set_disabled_row_hover_brush_color(self,
                                           r: int = conf.FILE_EXPLORER_ROW_HOVER_R - 100,
                                           g: int = conf.FILE_EXPLORER_ROW_HOVER_G - 40,
                                           b: int = conf.FILE_EXPLORER_ROW_HOVER_B):
        brushColor = QColor()
        brushColor.setRgb(r, g, b)
        self.disabled_row_hover_brush = QBrush()
        self.disabled_row_hover_brush.setColor(brushColor)
        self.disabled_row_hover_brush.setStyle(Qt.BrushStyle.SolidPattern)

    # Row-hovering
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        model = index.model()
        pos = self.view.viewport().mapFromGlobal(QCursor.pos())
        for c in range(model.columnCount(index)):
            r = self.view.visualRect(index.siblingAtColumn(c))
            if r.adjusted(0, 0, 1, 1).contains(pos):
                if option.widget.started_dragging:
                    option.backgroundBrush = option.palette.highlight()
                else:
                    option.backgroundBrush = self.row_hover_brush
                break


    """
    Customizing the table area
    """
    def sizeHint(self, option, index):
        # increase original sizeHint to accommodate space needed for border
        size = super().sizeHint(option, index)

        size = size.grownBy(QtCore.QMargins(0, self.margin, 0, self.margin))
        return size


    """
    Allowing for editing of items in the table
    """
    def createEditor(self, parent, option, index):
        logger.info(">> MyStyledItem.createEditor")
        self.editor = QLineEdit_EditFinenameExcludingExtension(parent)
        self.editor.setContentsMargins(24, 5, 1, 5)   # left, top, rightd, bottom
        self.editor.setFont(QFont(conf.TEXT_FONT, conf.TEXT_FONT_SIZE))
        self.editor.setStyleSheet(conf.RENAME_TEXTBOX_STYLE)
        self.editor.installEventFilter(self.editor)
        return self.editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
        # print('updateEditorGeometry')

    def setEditorData(self, editor, index):
        editor.setText(index.data())
        # print('setEditorData')

    # After user finished setting the new name
    def setModelData(self, editor, model, index):
        self.editingFinishedSignal.emit(index.data(), editor.text())

    def eventFilter(self, obj, event):
        qtype = event.type()
        if (qtype == QtCore.QEvent.Type.KeyPress):
            if event.key() == Qt.Key.Key_Escape:
                self.editingFinishedSignal.emit('___User_clicked_esc___', '___User_clicked_esc___')
            if event.key() == QtCore.Qt.Key.Key_End:
                self.editor.setCursorPosition(len(self.editor.text()))
            if event.key() == QtCore.Qt.Key.Key_Home:
                self.editor.setCursorPosition(0)
        return super().eventFilter(obj, event)



class DeletionThread(QThread):
    """
    Supports deleting items in a separate thread to avoid blocking the UI
    """
    def __init__(self, paths, permanently):
        super().__init__()
        self.paths = paths
        self.permanently = permanently
        self.currently_running = False

    def run(self):
        self.currently_running = True
        success = 0
        for path in self.paths:
            if success == -1:
                break
            if self.permanently:
                success = delete_item(path)
            else:
                success = move_to_trash(path)
        self.currently_running = False



class ItemsZipper:

    def __init__(self, items_paths, zip_dest_file_path, recursive=True, user_communications_ui=None):
        super().__init__()
        self.zipper_thread = ItemsZipThread(items_paths, zip_dest_file_path, recursive)
        self.zipping_ended = False
        self.message_box = None
        self.msg_box_creation_mutex = False
        self.message_box_shown = False
        self.user_communications_ui = threads_server['s1']

    def run(self):
        self.zipper_thread.finished.connect(self.zipping_finished)
        self.zipper_thread.start()
        self.timer = QTimer()
        self.timer.timeout.connect(self.show_message_box)
        self.timer.start(1000)  # Timeout every 1 second unless stopped explicitly

    def show_message_box(self):
        if self.timer.isActive():
            self.timer.stop()
            if self.user_communications_ui:
                self.user_communications_ui({'call_type': 'show_prompt_message',
                                             'msg': "Zipping item(s)",
                                             'caller_id': id(self)})
            self.message_box_shown = True

    def zipping_finished(self, success):
        if self.timer.isActive():
            self.timer.stop()
        if self.message_box_shown:
            if self.user_communications_ui:
                self.user_communications_ui({'call_type': 'remove_prompt_message',
                                             'caller_id': id(self)})
            self.message_box_shown = False


class ItemsZipThread(QThread):
    """
    Supports zipping items in a separate thread to avoid blocking the UI
    """

    finished = Signal(int)  # Signal emitted when copying is complete

    def __init__(self, items_paths, zip_dest_file_path, recursive=True, user_communications_ui=None):
        super().__init__()
        self.items_paths = items_paths
        self.zip_dest_file_path = zip_dest_file_path
        self.recursive = recursive
        self.currently_running = False
        self.user_communications_ui = user_communications_ui

    def run(self):
        self.currently_running = True
        success = self.zip_items(self.items_paths, self.zip_dest_file_path, self.recursive)
        self.finished.emit(success)
        self.currently_running = False

    def zip_items(self, item_paths: list[str], zip_dest_file_path: str, recursive: bool):
        try:
            with zipfile.ZipFile(zip_dest_file_path, 'w') as zipf:
                for item_path in item_paths:
                    zipf.write(item_path, os.path.basename(item_path))
                    if recursive:
                        for root, dirs, files in os.walk(item_path):
                            for file in files:
                                zipf.write(os.path.join(root, file))
                            for directory in dirs:
                                zipf.write(os.path.join(root, directory))
            return 1
        except:
            return -1


class PrefixSuffixChangeInSelectedItems(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Insert prefix and/or suffix")

        # Add a main layout to which everything will be added
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self._lbl1 = QLabel("[item name]", self)
        self._lbl2 = QLabel("[.ext]", self)
        self._lbl1.setStyleSheet("QLabel { background-color : transparent;}")
        self._lbl2.setStyleSheet("QLabel { background-color : transparent;}")

        self._prefix = QLineEdit(self)
        self._suffix = QLineEdit(self)
        self._prefix.setPlaceholderText("Prefix")
        self._suffix.setPlaceholderText("Suffix")
        self._prefix.setStyleSheet("QLineEdit { background-color : white;}")
        self._suffix.setStyleSheet("QLineEdit { background-color : white;}")

        self.full_item_name_layout = QHBoxLayout()
        self.full_item_name_layout.addWidget(self._prefix)
        self.full_item_name_layout.addWidget(self._lbl1)
        self.full_item_name_layout.addWidget(self._suffix)
        self.full_item_name_layout.addWidget(self._lbl2)


        self._user_message = QLabel("Insert prefix and/or suffix text to be added to"
                                    "selected item(s)\n", self)
        self.main_layout.addWidget(self._user_message)
        self.main_layout.addLayout(self.full_item_name_layout)

        self.buttons_layout = QHBoxLayout()
        self.main_layout.addLayout(self.buttons_layout)
        self.ok_btn = QPushButton('Select')
        self.cancel_btn = QPushButton('Cancel')
        self.buttons_layout.addWidget(self.ok_btn)
        self.buttons_layout.addWidget(self.cancel_btn)

        self.ok_btn.clicked.connect(self.on_ok_clicked)
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)

    @property
    def prefix(self):
        return self._prefix.text()

    @property
    def suffix(self):
        return self._suffix.text()

    def on_ok_clicked(self):
        self.accept()

    def on_cancel_clicked(self):
        self.reject()


class ReplaceTextInSelectedItems(QDialog):
    def __init__(self, type: str):
        super().__init__()

        if type == "replace":
            self.setWindowTitle("Replace text in items")
        elif type == "remove":
            self.setWindowTitle("Remove text from items")

        # Add a main layout to which everything will be added
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self._existing_text = QLineEdit("")
        self._existing_text.setPlaceholderText("Text to remove")
        self._existing_text.setStyleSheet("QLineEdit { background-color : white;}")

        self._new_text = QLineEdit("")
        self._new_text.setPlaceholderText("New text")
        self._new_text.setStyleSheet("QLineEdit { background-color : white, 0.5;}")

        self.full_item_name_layout = QVBoxLayout()
        self.full_item_name_layout.addWidget(self._existing_text)

        if type == "replace":
            self._user_message = QLabel("Insert original and new texts\n", self)
            self.full_item_name_layout.addWidget(self._new_text)
        elif type == "remove":
            self._user_message = QLabel("What text would you like to omit from item(s) name(s)?\n",
                                        self)

        self.main_layout.addWidget(self._user_message)
        self.main_layout.addLayout(self.full_item_name_layout)

        self.buttons_layout = QHBoxLayout()
        self.main_layout.addLayout(self.buttons_layout)
        self.ok_btn = QPushButton('Select')
        self.cancel_btn = QPushButton('Cancel')
        self.buttons_layout.addWidget(self.ok_btn)
        self.buttons_layout.addWidget(self.cancel_btn)

        self.ok_btn.clicked.connect(self.on_ok_clicked)
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)

    @property
    def existing_text(self):
        return self._existing_text.text()

    @property
    def new_text(self):
        return self._new_text.text()

    def on_ok_clicked(self):
        self.accept()

    def on_cancel_clicked(self):
        self.reject()


def validate_name_change_is_approved(old_text, new_text, item_already_exists=False):
    approval = 1
    if item_already_exists:
        msg = f"An item named {new_text} already exists in path. Please select another name"
        msg = message_box_w_arrow_keys_enabled(msg, "Item already exists",
                                               buttons=[QMessageBox.StandardButton.Ok],
                                               default_button_ind=0)
        approval = 0
        msg.exec()
    elif extract_extension_from_path(new_text).lower() != extract_extension_from_path(old_text).lower():
        old_ext = extract_extension_from_path(old_text)
        new_ext = extract_extension_from_path(new_text)
        msg = f"Are you sure you want to change the extension from {old_ext} to {new_ext}?"
        reply = \
            message_box_w_arrow_keys_enabled(msg, "Extension change",
                                             buttons=[QMessageBox.StandardButton.Ok,
                                                      QMessageBox.StandardButton.Cancel],
                                             default_button_ind=1).exec()
        if reply == QMessageBox.StandardButton.Cancel:
            approval = 0
    return approval
