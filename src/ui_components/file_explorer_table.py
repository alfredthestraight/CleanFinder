import os.path
import time
import numpy as np
import datetime
from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QFont, QColor, QPixmap, QKeySequence, QDrag
from PySide6.QtCore import Qt, QSize, QItemSelectionModel, QMimeData, QUrl, QRect, QItemSelection
from PySide6.QtWidgets import (QApplication, QTableView, QAbstractItemView, QMessageBox,
                               QScrollBar, QHeaderView)
from src.ui_components.misc_widgets.properties_window import (PropertiesWindowSingleItem,
                                                              PropertiesWindowMultipleItems)
from src.ui_components.misc_widgets.dialogs_and_messages import QDialogFreeTextButtons, \
    message_box_w_arrow_keys_enabled, prompt_message
from src.ui_components.misc_widgets.misc_widgets import QFileDialogWithCheckbox
from src.non_ui_components.user_actions import UserAction_RenameItem, UserAction_CreateItem
from src.shared.locations import DRAGGING_ICON, ICONS_DIR, APPLICATION_DIRECTORIES
from src.shared.vars import conf_manager as conf, logger as logger, extensions_to_icons_mapper
from src.utils.os_utils import (get_item_date_modified, get_dataframe_of_file_names_in_directory,
                                rename_file_or_dir, run_file_in_terminal, beautify_bytes_size,
                                is_dir, is_path_an_app, get_all_items_in_path, parent_directory,
                                extract_extension_from_path, extract_filename_from_path, is_root,
                                save_app_icon_in_app_icons_dir, dir_)
from src.utils.utils import SinglePathQFileSystemWatcherWithContextManager, single_run_qtimer, \
    map_key_to_new_row_num, create_qaction_key_sequence
from src.utils.file_explorer_utils import DeletionThread, MyStyledItem, ReplaceTextInSelectedItems,\
    next_new_dir_name, paths_history, ItemsZipper, map_shortcut_name_to_func, RowSelectionExtender,\
     PrefixSuffixChangeInSelectedItems, validate_name_change_is_approved
from src.ui_components.misc_widgets.context_menu import ContextMenuDelegate
from src.shared.vars import threads_server


class FileExplorerTable(QTableView):
    def __init__(self, data_model: QtCore.QAbstractTableModel,
                 root_dir_path: str,
                 xdim: int = None, ydim: int = None,
                 parent=None, encompassing_ui=None):
        super().__init__(parent=parent)

        self.structure_changed = False
        self.just_changed_path_flag = False
        self.started_dragging = False
        self.click_timer = None

        self.prev_selected_index = None
        self.last_selected_index = None

        self.last_selection_change_time = 0.0
        self.encompassing_ui = encompassing_ui
        self.browsing_history_manager = paths_history(root_dir_path.lstrip())
        self.row_selection_extender = RowSelectionExtender(self)  # When user presses Shift+Up/Down
        self.deletion_threads = []
        self.zipping_threads = []
        self.user_communications_ui = threads_server['s1']
        self.cols_to_hide = [4, 5, 6, 7, 8, 9]


        """
         Source data
        """
        self.pandasModel = data_model
        self.setModel(self.pandasModel)
        self.make_cut_items_greyed_out()
        self.num_columns = self.source_data.shape[1]


        """
         Drag & drop support
        """
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.drag_start_pos = None
        self.rubber_band = None
        self.setMouseTracking(True)


        """
         General visibility
        """
        self.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.xdim = xdim
        self.ydim = ydim
        # logger.info("Resizing to " + str(xdim) + ", " + str(ydim))
        self.setStyleSheet(conf.FILE_EXPLORER_STYLE)
        self.setAlternatingRowColors(conf.FILE_EXPLORER_ALTERNATING_ROW_COLORS)
        self.delegate = MyStyledItem(self, margin=0, radius=10, border_width=1,
                                     border_color=QColor("lightgrey"))
        self.setItemDelegate(self.delegate)
        self.delegate.editingFinishedSignal.connect(self.replace_item_name)

        # Selection visibility & behavior
        # https://doc.qt.io/qtforpython-6/overviews/stylesheet-examples.html
        # https://doc.qt.io/qt-5/qabstractitemview.html#SelectionMode-enum
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)  # SelectItems / SelectColumns / SelectRows
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)    # NoEditTriggers / DoubleClicked
        self._configure_headers()
        self.horizontalHeader().sectionResized.connect(self.update_structure_changed)
        self._set_cols_widths()
        self.set_scrollbars()


        """
         context menu:
        """
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenuEvent)
        self.properties_dialog_boxes = []


        """
         Functionality & usability
        """
        self.viewport().installEventFilter(self)
        selection_model = self.selectionModel()
        selection_model.selectionChanged.connect(self.on_selectionChanged)
        self.clicked.connect(self.on_clicked)
        self.doubleClicked.connect(self.on_doubleClicked)


        try:
            self.initialize_all_key_sequences()
        except:
            pass

        # Track changes in the file system
        self.connect_filesystem_watcher()


    @property
    def path(self):
        return self.pandasModel.path

    @property
    def source_data(self):
        return self.pandasModel._data

    @property
    def num_items(self):
        return self.source_data.shape[0]

    @property
    def encompassing_uis_manager(self):
        return self.encompassing_ui.encompassing_uis_manager

    @property
    def first_selected_item_index(self):
        if len(self.selectedIndexes()) > 0:
            return self.selectedIndexes()[0]
        else:
            return None

    @property
    def currently_selected_filename_indices(self):
        return [x for x in self.selectedIndexes() if x.column() == 0]

    @property
    def currently_selected_filenames(self):
        return [x.data() for x in self.selectedIndexes() if x.column() == 0]

    def total_size_of_selected_files(self):
        try:
            return int(self.source_data[
                           (self.source_data['Name'].isin(self.currently_selected_filenames)) &
                           (~self.source_data['is_folder'])
                       ].size_raw.sum())
        except:
            print("Error in total_size_of_selected_files")

    @property
    def selected_item_path(self):
        if len(self.selectedIndexes()) > 0:
            filename = self.first_selected_item_index.data()
            return os.path.join(self.path, filename)
        else:
            return None

    @property
    def selected_items_paths(self):
        return self._extract_full_paths_from_indices(self.selectedIndexes())

    # E.g., when user selected "cut_items", which means some rows should be greyed out
    def refresh_display_for_items(self, from_row: int, to_row: int):
        self.pandasModel.dataChanged.emit(from_row, to_row, [Qt.ItemDataRole.DisplayRole])

    def row_nums_where_items_texts_are(self, txts_list: list[str]):
        if len(txts_list) == 0:
            return []
        return list(self.source_data[
            self.source_data.iloc[:, conf.FILENAME_COLUMN_INDEX].isin(txts_list)
        ].index)

    def index_at_row_and_col(self, row_num: int, col_num: int) -> QtCore.QModelIndex:
        return self.model().index(row_num, col_num)

    def index_of_item_name(self, item_name: str):
        if item_name in self.source_data.Name.values:
            row_num = self.source_data.index[self.source_data.Name == item_name][0]
            return self.index_at_row_and_col(row_num, 0)
        else:
            return None

    def _retrieve_only_filename_indices(self, indices: list[QtCore.QModelIndex]):
        if len(indices) == 0:
            return []
        else:
            return [indices[i]
                    for i in range(len(indices))
                    if indices[i].column() == 0]

    def _extract_item_rows_from_indices(self, indices: list[QtCore.QModelIndex]):
        return [ind.row() for ind in self._retrieve_only_filename_indices(indices)]

    def _extract_full_paths_from_indices(self, indices: list[QtCore.QModelIndex]):
        return [os.path.join(self.path, ind.data())
                for ind in self._retrieve_only_filename_indices(indices)]

    def get_filenames_from_indices(self, indices: list[QtCore.QModelIndex]):
        return [x.data() for x in indices if x.column() == 0]

    def get_full_path_of_index(self, index: QtCore.QModelIndex):
        return os.path.join(self.path, index.data())

    def select_rows(self, start_row: int, end_row: int):
        selection_model = self.selectionModel()
        selection_model.clearSelection()  # Clear any previous selections

        for row in range(start_row, end_row + 1):
            index_top = self.index_at_row_and_col(row, 0)  # Top-left index of the row
            index_bottom = self.index_at_row_and_col(row, 0)

            selection_model.select(
                QItemSelection(index_top, index_bottom),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
            )

    def select_row_where_item_text_is(self, txt: str):
        for row in range(self.num_items):
            if txt == self.pandasModel.index(row, 0).data():
                source_index = self.pandasModel.index(row, 0)
                self.selectionModel().select(source_index,
                                             QItemSelectionModel.SelectionFlag.Select |
                                             QItemSelectionModel.SelectionFlag.Rows)
                return

    def select_rows_where_items_texts_are(self, txts_list: list[str]):
        for txt in txts_list:
            self.select_row_where_item_text_is(txt)

    def delayed_select_rows_where_items_texts_are(self, new_items_names, delay=300):
        self.print_stuff_timer = \
            single_run_qtimer(delay,
                              lambda: self.select_rows_where_items_texts_are(new_items_names))

    """
     Structure change
    """
    def update_structure_changed(self):
        if self.encompassing_ui._allow_structure_updates:
            self.structure_changed = True

    def adapt_width_of_last_column(self):
        self.setColumnWidth(3,
                            self.width() - self.columnWidth(0) - self.columnWidth(1) -
                            self.columnWidth(2) - 30)


    """
     User actions undo/redo
    """
    def keep_last_action(self, action):
        self.encompassing_uis_manager.keep_last_action(action)

    def undo_last_action(self):
        self.encompassing_uis_manager.undo_last_action()
        with self.watcher:  # Temporarily disable files watcher
            self.pandasModel.refresh_data()

    def redo_last_undone_action(self):
        self.encompassing_uis_manager.redo_last_undone_action()
        with self.watcher:  # Temporarily disable files watcher
            self.pandasModel.refresh_data()


    """
    Mouse events 
    """

    def mousePressEvent(self, event):
        self.mouse_press_event_tmp = event
        self.last_row = self.num_items
        self.tmp_bool = True
        self.press_pos = event.position()
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(self.press_pos.toPoint())
            # Clicking in an empty area:
            if index.data() is None:
                # logger.info("mousePressEvent in an empty area")
                self.drag_start_pos = event.position()
                self.rubber_band = QRect(self.drag_start_pos.x(),
                                         self.drag_start_pos.y(),
                                         0, 0)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        If user started by clicking not on an item, but on the empty space, and then moved the
        cursor - any item the cursor goes over will e included in the selection:
        """
        if self.drag_start_pos:
            if event.buttons() == Qt.MouseButton.LeftButton:
                self.setDragEnabled(False)
                index = self.indexAt(event.position().toPoint())
                curr_row = index.row()
                self.selectRow(curr_row)
                if self.tmp_bool:
                    if curr_row != -1 and curr_row < self.last_row:
                        for i in range(curr_row, self.last_row):
                            self.selectRow(i)
                        self.tmp_bool = False
        elif event.buttons() == Qt.MouseButton.LeftButton:
            self.started_dragging = True
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                if (self.press_pos.x() - event.position().x() > 4 or
                        self.press_pos.y() - event.position().y() > 4):
                    self.startDrag(index)
        else:
            self.started_dragging = False
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.structure_changed:
            self.structure_changed = False
            self.adapt_width_of_last_column()

        self.setDragEnabled(True)
        self.drag_start_pos = None
        self.tmp_bool = True
        self.pandasModel.allow_decoration_role = True
        self.started_dragging = False

        super().mouseReleaseEvent(event)


    """
    Drag & drop events, item selection via cursor dragging
    """
    # Moving the cursor with an item dragged
    def dragMoveEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            self.refresh_display_for_items(index, index.siblingAtRow(index.row()-1))
            self.refresh_display_for_items(index, index.siblingAtRow(index.row()+1))

    def dragEnterEvent(self, event):
        if not self.started_dragging:
            return
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def startDrag(self, index):
        if not self.started_dragging:
            return

        # Create a QDrag object
        drag = QDrag(self)

        # Set up the data to drag
        mime_data = QMimeData()
        # The text carried on the drag (could be dropped in any text editor)
        mime_data.setText("\n".join(self.selected_items_paths))
        drag.setMimeData(mime_data)

        # Set the custom pixmap for the dragged item (no decorations)
        pixmap = QPixmap(os.path.join(ICONS_DIR, DRAGGING_ICON))
        drag.setPixmap(pixmap)

        # Start the drag operation
        drag.exec(Qt.DropAction.MoveAction)


    def dropEvent(self, event):
        self.started_dragging = False
        self.cancel_cut_items()
        self.viewport().update()
        self.drag_start_pos = None
        source_paths = self.selected_items_paths
        dest_name = self.indexAt(event.position().toPoint()).data()
        if dest_name is not None:
            dest_path = os.path.join(self.path, dest_name)
            if dest_path in source_paths:
                return
            if not os.path.isdir(dest_path):
                pass
            else:
                event.acceptProposedAction()    # NOTE: this cancels the dragging-back animation
                self.encompassing_uis_manager.\
                    paste_items(dest_path=dest_path,
                                source_paths=source_paths,
                                delete_source_after_paste=True)

    def select_items_within_rubber_band(self):
        selection_rect = self.rubber_band.normalized()
        table_bottom_last_coor = self.rowViewportPosition(self.num_items-1)
        rect_coors = selection_rect.getCoords()
        if rect_coors[2] <= table_bottom_last_coor:
            self.releaseMouse()
            self.mousePressEvent(self.mouse_press_event_tmp)


    """
    Context menu
    """

    def contextMenuEvent(self, event):

        if not os.path.exists(self.path):
            prompt_message("Path no longer exists",
                           "The current path you are in (" + self.path + ") no longer exist")
            return

        index_clicked = self.index_at_row_and_col(self.indexAt(event).row(), 0)
        clicked_item_name = index_clicked.data()
        clicked_on_empty_space = clicked_item_name is None

        items_paths = self.selected_items_paths

        contextMenu = ContextMenuDelegate(self).populate_context_menu(
            clicked_on_empty_space, clicked_item_name, items_paths
        )

        # Show context menu at the position of the mouse event
        event.setX(event.x() + 20)
        event.setY(event.y() + 10)
        contextMenu.exec(self.mapToGlobal(event))


    def open_item_from_context_menu(self):
        self.on_doubleClicked(self.currently_selected_filename_indices[0])


    """
    Items name manipulation
    """
    def add_prefix_or_suffix_to_items_names(self):
        dialog = PrefixSuffixChangeInSelectedItems()
        reply = dialog.exec()
        if reply == 1 and (dialog.prefix != "" or dialog.suffix != ""):
            for path in self.selected_items_paths:
                filename = extract_filename_from_path(path)
                ext = extract_extension_from_path(path)
                if '.' in filename:
                    ext = '.' + ext
                self.replace_item_name(filename,
                                       dialog.prefix +
                                       filename.replace(ext, "") +
                                       dialog.suffix +
                                       ext)


    def replace_substring_in_items_names(self):
        dialog = ReplaceTextInSelectedItems("replace")
        reply = dialog.exec()
        if dialog.existing_text == dialog.new_text:
            return
        if reply == 1 and dialog.existing_text != "":
            new_items_names = \
                self.replace_substring_in_selected_names_aux(dialog.existing_text, dialog.new_text)
            self.delayed_select_rows_where_items_texts_are(new_items_names)


    def delete_substring_from_items_names(self):
        dialog = ReplaceTextInSelectedItems("remove")
        reply = dialog.exec()
        if reply == 1 and dialog.existing_text != "":
            self.replace_substring_in_selected_names_aux(dialog.existing_text, "")


    def replace_substring_in_selected_names_aux(self, old_text: str, new_text: str) -> list[str]:
        new_items_names = []
        for path in self.selected_items_paths:
            filename = extract_filename_from_path(path)
            ext = extract_extension_from_path(path)
            if '.' in filename:
                ext = '.' + ext
            new_file_name = filename.replace(ext, "").replace(old_text, new_text) + ext
            self.replace_item_name(filename, new_file_name)
            new_items_names.append(new_file_name)
        return new_items_names

    def replace_item_name(self, old_text: str, new_text: str):
        logger.info(f"FileExplorerTable.replace_item_name: {old_text} -> {new_text}")
        if old_text == '___User_clicked_esc___' and new_text == '___User_clicked_esc___':
            return
        if old_text == new_text:
            return
        existing_names_in_path = self.source_data.iloc[:, conf.FILENAME_COLUMN_INDEX].tolist()
        approval = validate_name_change_is_approved(old_text, new_text,
                                                    new_text in existing_names_in_path)
        if approval == 0:
            return
        changed_row = \
            np.where(self.source_data.iloc[:, conf.FILENAME_COLUMN_INDEX] == old_text)[0][0]
        # Update the pandas model
        self.source_data.iloc[changed_row, conf.FILENAME_COLUMN_INDEX] = new_text
        # Update the name in the OS
        rename_file_or_dir(os.path.join(self.path, old_text), new_text)
        self.keep_last_action(UserAction_RenameItem(self.path, old_text, new_text))

    def rename_item(self):
        if len(self.selected_items_paths) == 1:
            self.invoke_filename_editor(
                index=self.currently_selected_filename_indices[len(self.currently_selected_filename_indices)-1]
            )


    """
    Item deletion
    """
    def make_sure_user_wants_to_remove_items(self, permanently: bool = False):
        item_names = self.get_filenames_from_indices(self.selectedIndexes())
        if len(item_names) == 1:
            message_end = 'delete this item?'
        else:
            message_end = 'delete these items?'
        if permanently:
            message_end = 'permanently ' + message_end
        response = message_box_w_arrow_keys_enabled("Are you sure you want to " + message_end,
                                                    "Quit?").exec()
        return response


    def _remove_items(self, permanently: bool = False):
        reply = self.make_sure_user_wants_to_remove_items(permanently)
        if reply != QMessageBox.StandardButton.Yes:
            return
        else:
            logger.info("FileExplorerTable._remove_items - deleting dead threads")
            for thrd in self.deletion_threads:
                if not thrd.currently_running:
                    thrd.quit()
                    self.deletion_threads.remove(thrd)

            self.cancel_cut_items()
            paths = self._extract_full_paths_from_indices(self.selectedIndexes())
            self.browsing_history_manager.remove_paths_and_subpaths_from_history(paths)
            deletion_thread = DeletionThread(paths, permanently)
            self.deletion_threads.append(deletion_thread)
            deletion_thread.start()
            self.encompassing_uis_manager.remove_paths_and_subpaths_from_browsing_histories(paths)
            self.deletion_timer = \
                single_run_qtimer(200, lambda: self.encompassing_uis_manager.refresh_all_uis())


    def remove_items(self):
        self._remove_items(permanently=False)

    def permanently_remove_items(self):
        self._remove_items(permanently=True)


    def open_properties(self):
        # Discard any closed properties dialog boxes
        self.properties_dialog_boxes = [prop_box for prop_box in self.properties_dialog_boxes
                                        if prop_box.is_currently_presented]
        items_paths = self._extract_full_paths_from_indices(self.selectedIndexes())
        if len(items_paths) == 1:
            properties = PropertiesWindowSingleItem(self.selected_item_path, self)
        else:
            properties = PropertiesWindowMultipleItems(items_paths, self)
        try:
            properties.move_to_random_position(self.encompassing_ui.splitter.pos().x(),
                                               self.encompassing_ui.splitter.pos().y())
            properties.show()
            self.properties_dialog_boxes.append(properties)
        except:
            pass


    def keep_selection_as_prev(self, indices: list[QtCore.QModelIndex]):
        if len(indices) > 0:  # Something was already selected
            self.prev_selected_index = indices[0]
        else:
            self.prev_selected_index = None


    def change_path(self, new_path: str,
                    reset_path_history: bool = True,
                    direction: int = None,   # In case user clicks on back/forward button
                    reset_tree_selection: bool = True,
                    selected_path_after_change: str = None):

        if new_path == self.browsing_history_manager.curr_path():
            return 1

        logger.info(f"Changing path from {self.path} to {new_path}")

        self.pandasModel.replace_data_and_path(
            get_dataframe_of_file_names_in_directory(new_path), new_path,
            self.encompassing_uis_manager.get_columns_ordering_scheme(new_path))
        self.connect_filesystem_watcher()

        self.encompassing_ui.path_changed(new_path, reset_tree_selection)

        if direction is not None:
            self.browsing_history_manager.move_to_path_in_direction(direction)
        else:
            self.browsing_history_manager.add_path(new_path)

        if reset_path_history:
            self.browsing_history_manager.reset_head_to_current_path()
        self.prev_selected_index = None
        self.just_changed_path_flag = True

        # Select the directory from which user changed path
        if selected_path_after_change is not None:
            text = selected_path_after_change.split('/')[-1]
            self.select_row_where_item_text_is(text)

        return 1


    def create_new_dir(self):
        if not os.path.exists(self.path):
            prompt_message("Path no longer exists",
                           "The current path you are in (" + self.path + ") no longer exist")
        all_current_directories = get_all_items_in_path(self.browsing_history_manager.curr_path(), 2)
        new_dir_name = next_new_dir_name(all_current_directories, conf.NEW_FOLDER_NAME_TEMPLATE)
        new_folder_path = os.path.join(self.browsing_history_manager.curr_path(), new_dir_name)
        logger.info("file_explorer_table.create_new_dir: " + new_folder_path)
        os.mkdir(new_folder_path)
        self.encompassing_uis_manager.keep_last_action(UserAction_CreateItem(new_folder_path))
        with self.watcher:  # Temporarily disable files watcher
            self.pandasModel.insertRows({'Name': new_dir_name,
                                         'Date modified': get_item_date_modified(new_folder_path),
                                         'Size': '--',
                                         'Type': 'Folder',
                                         'file_type': conf.FOLDER_ICON_NAME,
                                         'size_raw': 0,
                                         'extension_n_char': 0,
                                         'date_modified_raw': os.path.getctime(new_folder_path),
                                         'is_folder': True, 'is_hidden': False})
        self.click_timer = \
            single_run_qtimer(100, self.invoke_filename_editor,
                              index=self.index_of_item_name(new_dir_name))

    def add_new_ui(self):
        logger.info("Adding new ui")
        self.encompassing_uis_manager.create_new_window(root_dir_path=conf.DEFAULT_PATH)


    def open_item(self, item_path: str, app_name: str = None):
        logger.info("FileExplorerTable.open_item")
        if is_dir(item_path):
            success = self.change_path(item_path)
        else:
            success = run_file_in_terminal(item_path, app_name)
        return success


    def on_enter(self):
        selected_indices = self.selectedIndexes()
        if len(selected_indices) == 0:
            # Nothing selected
            return
        if len(selected_indices) > self.num_columns_shown:
            # More than one item selected
            return
        new_path = self.get_full_path_of_index(selected_indices[0])
        if is_dir(new_path):
            try:
                self.change_path(new_path)
            except:
                pass
        else:
            self.open_item(new_path)


    def open_file_with_specified_app(self, full_file_path: str):
        select_app_dialog = \
            QFileDialogWithCheckbox(directory=APPLICATION_DIRECTORIES[0],
                                    checkbox_text="Use this app as the defalt app "
                                                  "for itmes of this type")
        outcome = select_app_dialog.exec()
        selected_app = select_app_dialog.selectedFiles()[0]
        if outcome == 1:
            if is_path_an_app(selected_app):
                if select_app_dialog.checkbox.isChecked():
                    self.set_default_app_for_files_with_extension(full_file_path, selected_app)
                self.open_item(full_file_path, selected_app)
            else:
                prompt_message("Not an app",
                               f"Selection ('{selected_app}') is not a valid app",
                               QMessageBox.StandardButton.Ok)


    def set_default_app_for_files_with_extension(self, path_of_file_with_ext: str, app_path: str):
        logger.info(f"FileExplorerTable.set_default_app_for_files_with_extension: {path_of_file_with_ext}, {app_path}")
        extensions_to_icons_mapper. \
            set_default_app_for_extension(path_of_file_with_ext, app_path)
        ext = extract_extension_from_path(path_of_file_with_ext)
        if extensions_to_icons_mapper.extension_has_existing_icon(ext):
            icon_full_path = \
                extensions_to_icons_mapper.get_icon_path_for_extension(
                    extract_extension_from_path(path_of_file_with_ext)
                )
            save_app_icon_in_app_icons_dir(icon_full_path, ext,
                                           delete_tmp_dir_after_completion=True)


    def invoke_filename_editor(self, **args):
        try:
            self.edit(args['index'])
            logger.info("FileExplorerTable.invoke_filename_editor: success")
        except:
            logger.info("FileExplorerTable.invoke_filename_editor: failure")
            return


    def on_selectionChanged(self, selected, deselected):
        """
        Called when the selection is changed (either by clicking on a not-selected item,
        or by using the arrow keys).
        Clicking on an already-selected item will not invoke this method.
        """
        time_now = time.time()
        self.prev_selected_index = deselected.indexes()[0] if len(deselected.indexes()) > 0 else None
        self.last_selected_index = selected.indexes()[0] if len(selected.indexes()) > 0 else None
        size_items = beautify_bytes_size(self.total_size_of_selected_files())[2]
        num_items = len(self.currently_selected_filename_indices)
        self.encompassing_ui.refresh_bottom_toolbar_text(num_items, size_items)
        self.last_selection_change_time = time_now


    def on_clicked(self, index):
        time_now = time.time()
        if self.click_timer is not None:
            self.click_timer.stop_timer()

        # on_selectionChanged will not be invoked when user clicks on the same item which was
        #  already selected, so need to check this programatically
        time_lag_since_last_selection_change = time_now - self.last_selection_change_time

        # Rename item:
        if time_lag_since_last_selection_change > 0.32:
                self.click_timer = \
                    single_run_qtimer(500, self.invoke_filename_editor, index=index)
        self.keep_selection_as_prev(self.selectedIndexes())



    def on_doubleClicked(self, index):
        if self.click_timer is not None:
            self.click_timer.stop_timer()
        logger.info("FileExplorerTable.on_doubleClicked")
        clicked_item_full_path = os.path.join(self.path, index.data())
        success = self.open_item(clicked_item_full_path)
        if success == 256:  # Could not find an application to open the file with
            msg = f"Could not find a proper application to open item {index.data()}"
            select_app_txt = "Select app"
            dialog = QDialogFreeTextButtons([select_app_txt, "Cancel"],
                                            title_text="No app found", message_text=msg,
                                            btn_width=120)
            dialog.exec()
            if dialog.clicked_button == select_app_txt:
                self.open_file_with_specified_app(clicked_item_full_path)


    """
        Copy, cut, paste...
    """
    def copy_selected_items_to_clipboard(self):
        item_paths = self.selected_items_paths
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(p) for p in item_paths])
        QApplication.clipboard().setMimeData(mime_data)
        self.cancel_cut_items()
        logger.info(f"Copied item(s) {item_paths} to clipboard")

    def copy_item_path_to_clipboard(self):
        item_path = self.selected_item_path
        if item_path is None:
            return
        QApplication.clipboard().setText(item_path)
        self.make_cut_items_greyed_out()
        self.cancel_cut_items()
        logger.info(f"Copied file path {item_path} to clipboard")

    def copy_current_path_to_clipboard(self):
        QApplication.clipboard().setText(self.path)


    def paste_items_from_clipboard(self):
        delete_after_pasting = (len(self.encompassing_uis_manager.cut_items_names) > 0)
        self.encompassing_uis_manager.\
            paste_items_from_clipboard(dest_path=self.path,
                                       delete_source_after_paste=delete_after_pasting)
        self.cancel_cut_items()


    def cut_item(self):
        logger.info("FileExplorerTable.cut_item")
        self.copy_selected_items_to_clipboard()
        indices = self.selectedIndexes()
        item_names = list(set(self.get_filenames_from_indices(indices)))
        self.encompassing_uis_manager.cut_items_names = item_names
        self.encompassing_uis_manager.cut_items_path = self.path
        self.make_cut_items_greyed_out()

    def make_cut_items_greyed_out(self):
        self.pandasModel.cut_items = self.encompassing_uis_manager.cut_items_names
        self.pandasModel.cut_items_path = self.encompassing_uis_manager.cut_items_path
        row_nums = self.row_nums_where_items_texts_are(self.pandasModel.cut_items)
        if len(row_nums) > 0:
            self.refresh_display_for_items(min(row_nums), max(row_nums))

    def on_escape(self):
        self.cancel_cut_items()

    def cancel_cut_items(self):
        if len(self.encompassing_uis_manager.cut_items_names) > 0:
            cut_items_tmp = self.pandasModel.cut_items.copy()
            self.pandasModel.cut_items = []
            self.encompassing_uis_manager.cancel_cut_items()
            row_nums = self.row_nums_where_items_texts_are(cut_items_tmp)
            if len(row_nums) > 0:
                self.refresh_display_for_items(min(row_nums), max(row_nums))

    """
        Navigation using keyboard shortcuts
    """
    def go_to_previous_path(self):
        logger.info("FileExplorerTable.go_to_previous_path")
        if self.browsing_history_manager.has_history():
            prev_path = self.browsing_history_manager.prev_path()
            if os.path.exists(prev_path):
                self.change_path(prev_path, False, 1)

    def go_to_next_path(self):
        logger.info("FileExplorerTable.go_to_next_path")
        if self.browsing_history_manager.has_forward_paths():
            next_path = self.browsing_history_manager.next_path()
            if os.path.exists(next_path):
                self.change_path(next_path, False, -1)

    def go_to_parent_dir(self):
        logger.info("FileExplorerTable.go_to_parent_dir")
        if is_root(self.browsing_history_manager.curr_path()):
            return
        parent_path = parent_directory(self.browsing_history_manager.curr_path())
        if is_dir(parent_path):
            try:
                curr_path = self.browsing_history_manager.curr_path()
                if os.path.exists(self.path):
                    self.change_path(parent_path, selected_path_after_change=curr_path)
                else:
                    # Path user is in no longer exists (was deleted)
                    self.change_path(parent_path)
            except:
                pass

    def extend_selection_downwards(self):
        self.row_selection_extender(1)

    def extend_selection_upwards(self):
        self.row_selection_extender(-1)

    def select_all(self):
        logger.info("FileExplorerTable.select_all")
        self.selectAll()

    def go_to_item_starting_with_string(self, st: str):
        names_arr = self.source_data['Name'].str.lower().to_numpy()
        items_starting_with_st = np.where([x[0] == st for x in names_arr])[0]
        if items_starting_with_st.shape[0] > 0:
            self.selectRow(items_starting_with_st[0])


    """
        Keyboard shortcuts mappings
    """
    def initialize_all_key_sequences(self):
        # Remove all existing shortcuts:
        for act in self.actions():
            act.setShortcut(QKeySequence())
        for i in range(len(conf.get("keyboard_shortcuts"))):
            func_name = list(conf.get("keyboard_shortcuts").keys())[i]
            for shortcut in conf.get("keyboard_shortcuts")[func_name]:
                create_qaction_key_sequence(self, shortcut,
                                            map_shortcut_name_to_func(self, func_name))


    def select_all_items_from_curr_to_end(self):
        if len(self.selectedIndexes()) == 0:
            self.select_all()
        else:
            self.select_rows(self.first_selected_item_index.row(), self.num_items - 1)
        self.row_selection_extender.reset()

    def select_all_items_from_curr_to_head(self):
        if len(self.selectedIndexes()) > 0:
            self.select_rows(0, self.first_selected_item_index.row())
            self.row_selection_extender.reset()


    # Key press events in general (not related to any specific widget)
    def keyPressEvent(self, e):
        if not self.hasFocus():
            return
        new_row = map_key_to_new_row_num(e.key(), self)
        if new_row is not None:
            self.keep_selection_as_prev(self.selectedIndexes())
            self.selectRow(new_row)
        else:
            if e.key() == QtCore.Qt.Key.Key_Delete:  # Delete
                if len(self.selectedIndexes()) > 0:
                    self.remove_items()
            elif e.key() == QtCore.Qt.Key.Key_F2:    # F2
                self.rename_item()
            elif (e.key() == QtCore.Qt.Key.Key_Return) or (e.key() == QtCore.Qt.Key.Key_Enter):    # Enter
                    self.on_enter()
            elif e.key() == QtCore.Qt.Key.Key_Escape:    # Enter
                self.on_escape()


    """
        Miscellaneous methods
    """
    def on_header_clicked(self, col):
        logger.info("FileExplorerTable.on_header_clicked")
        self.encompassing_uis_manager.switch_ordering_of_file_explorer_column(col, self.path)
        self.pandasModel.columns_ordering_scheme = \
            self.encompassing_uis_manager.get_columns_ordering_scheme(self.path)
        with self.watcher:  # Temporarily disable files watcher
            self.pandasModel.enforce_sorting()

    def format_headers(self, cols_to_hide: list[int] = []):
        logger.info("FileExplorerTable.format_headers")
        self.header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.header.setFont(QFont(conf.TEXT_FONT))
        self.header.setStretchLastSection(True)
        self.header.setStyleSheet(conf.FILE_EXPLORER_HEADER_STYLE)
        for col_i in cols_to_hide:
            self.hideColumn(col_i)

    def _configure_headers(self):
        # Rows
        if conf.FILE_EXPLORER_SHOW_ROW_NUMBERS:
            self.verticalHeader().setVisible(True)
            self.verticalHeader().setStyleSheet(conf.FILE_EXPLORER_ROWS_STYLE)
        else:
            self.verticalHeader().setVisible(False)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.verticalHeader().setDefaultSectionSize(conf.FILE_EXPLORER_ROW_HEIGHT)

        # Headers
        self.header = self.horizontalHeader()
        self.num_columns_shown = self.num_columns - len(self.cols_to_hide)
        self.format_headers(self.cols_to_hide)
        self.header.sectionClicked.connect(self.on_header_clicked)

    def _set_cols_widths(self):
        for col_width_pair in [(0, conf.FILE_EXPLORER_COL_WIDTH_1),
                               (1, conf.FILE_EXPLORER_COL_WIDTH_2),
                               (2, conf.FILE_EXPLORER_COL_WIDTH_3),
                               (3, conf.FILE_EXPLORER_COL_WIDTH_4)]:
            self.setColumnWidth(col_width_pair[0], col_width_pair[1])


    def _refresh_source_data(self):
        logger.info("FileExplorerTable._refresh_source_data")
        with self.watcher:  # Temporarily disable files watcher
            self.pandasModel.refresh_data()
        # Select the item which was selected before the refresh
        if self.prev_selected_index is not None:
            row = self.prev_selected_index.row()
            if self.source_data.shape[0] > row:
                logger.info("FileExplorerTable._refresh_source_data, self.source_data.shape[0] > row")
                if self.source_data.iloc[row, conf.FILENAME_COLUMN_INDEX] == \
                        self.prev_selected_index.data():
                    try:
                        self.selectRow(self.prev_selected_index.row())
                    except:
                        self.keep_selection_as_prev(self.selectedIndexes())

    def zip_items(self, indices_to_zip: list[QtCore.QModelIndex] = None):
        if indices_to_zip is not None:
            paths_to_zip = self._extract_full_paths_from_indices(indices_to_zip)
        else:
            paths_to_zip = self._extract_full_paths_from_indices(self.selectedIndexes())
        zip_filename = "zip_" + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + ".zip"
        zip_filename_path = os.path.join(self.path, zip_filename)

        zipping_thread = ItemsZipper(paths_to_zip, zip_filename_path,
                                     user_communications_ui=self.user_communications_ui)
        self.zipping_threads.append(zipping_thread)
        zipping_thread.run()

        self.click_timer = \
            single_run_qtimer(1000,
                              lambda: self.encompassing_uis_manager.refresh_all_uis())

    def refresh_all_configurations(self):
        logger.info("FileExplorerTable.refresh_all_configurations")
        self.header.setStyleSheet(conf.FILE_EXPLORER_HEADER_STYLE)
        self.verticalHeader().setStyleSheet(conf.FILE_EXPLORER_ROWS_STYLE)
        self.verticalHeader().setDefaultSectionSize(conf.FILE_EXPLORER_ROW_HEIGHT)
        self.setStyleSheet(conf.FILE_EXPLORER_STYLE)
        self.vertical_scrollbar.setStyleSheet(conf.VERTICAL_SCROLLBAR_STYLE)
        self.horizontal_scrollbar.setStyleSheet(conf.HORIZONTAL_SCROLLBAR_STYLE)
        self.model().refresh_data()

    def set_scrollbars(self):
        logger.info("FileExplorerTable.set_scrollbars")
        self.vertical_scrollbar = QScrollBar()
        self.horizontal_scrollbar = QScrollBar()
        self.vertical_scrollbar.setStyleSheet(conf.VERTICAL_SCROLLBAR_STYLE)
        self.horizontal_scrollbar.setStyleSheet(conf.HORIZONTAL_SCROLLBAR_STYLE)
        self.setVerticalScrollBar(self.vertical_scrollbar)
        self.setHorizontalScrollBar(self.horizontal_scrollbar)

    def sizeHint(self):
        if self.xdim is None:
            return super().sizeHint()
        else:
            return QSize(self.xdim, 681)

    # Reacts to changes in the file system (e.g., renaming, deleting, etc.)
    def connect_filesystem_watcher(self):
        self.watcher = SinglePathQFileSystemWatcherWithContextManager(self.path)
        self.watcher.directoryChanged.connect(self._refresh_source_data)
        self.watcher.fileChanged.connect(self._refresh_source_data)
