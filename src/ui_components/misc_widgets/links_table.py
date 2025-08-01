import os
from PySide6.QtWidgets import (QTableView, QAbstractItemView, QMenu, QFrame, QHeaderView,
                               QFileDialog)
from PySide6.QtCore import Qt, QSize
from src.utils.os_utils import *
from src.data_models import MiscItemsTable
from src.shared.locations import DRAGGING_ICON, BASE_ICONS_DIR, ICONS_DIR, SYSTEM_ROOT_DIR, \
    SYSTEM_DEFAULT_ICONS_DIR
from src.utils.utils import configure_context_menu, add_actions_to_context_menu, get_full_icon_path
from src.shared.vars import conf_manager as conf
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QPixmap, QDrag


class DragAndDropFunctionality():
    def startDrag(self, supportedActions):
        drag = QDrag(self)
        mimeData = self.model().mimeData(self.selectedIndexes())
        drag.setMimeData(mimeData)
        dropAction = drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        event.accept()

    def dragMoveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        source = event.source()
        if source is not self:
            source_model = source.model()
            target_model = self.model()
            selected_indexes = [x for x in source.selectedIndexes() if x.column() == 0]
            return source_model, target_model, selected_indexes
        else:
            return None, None, None


class LinksTable(DragAndDropFunctionality, QTableView):
    def __init__(self, favorites_dict=None,
                 row_height: int = conf.FAVORITES_ROW_HEIGHT,
                 spacer_column_indent: int = 0,
                 parent=None, encompassing_ui=None):
        super().__init__(parent=parent)
        self.encompassing_ui = encompassing_ui
        self.table = MiscItemsTable(favorites_dict, spacer_column_indent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.verticalHeader().setDefaultSectionSize(row_height)
        self.setModel(self.table)
        self.setShowGrid(False)
        if spacer_column_indent > 0:
            for col_i in range(2, len(self.table.columns)):
                self.setColumnHidden(col_i, True)
        else:
            for col_i in range(1, len(self.table.columns)):
                self.setColumnHidden(col_i, True)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        if spacer_column_indent > 0:
            self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        else:
            self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.setIconSize(QSize(20, 20))

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        # self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDropIndicatorShown(True)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenuEvent)
        self.index_right_clicked_on = None

    def dragMoveEvent(self, e):
        e.accept()

    def dragEnterEvent(self, event):
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def startDrag(self, supportedActions):
        # Get the selected indexes and create the mime data
        indexes = self.selectedIndexes()
        if not indexes:
            return

        # Create a QDrag object
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(indexes[0].row()))
        drag.setMimeData(mime)

        # Set a custom pixmap to show while dragging
        drag.setPixmap(QPixmap(DRAGGING_ICON))

        # Start the drag operation
        drag.exec(Qt.DropAction.MoveAction)

    def dropEvent(self, event):
        source_model, target_model, selected_indexes = super(LinksTable, self).dropEvent(event)
        if source_model is not None:
            if selected_indexes:
                for index in selected_indexes:
                    if index.isValid():
                        new_item_name = index.data()
                        new_item_path = os.path.join(source_model.path, index.data())
                        target_model.appendRow(new_item_name,
                                               new_item_path,
                                               get_full_icon_path(conf.FOLDER_ICON_NAME))
                        target_model._data.reset_index(drop=True, inplace=True)
                        self.update_config_file_favorites_dict()
            event.acceptProposedAction()
        elif type(event.source()).__name__ == "LinksTable":
            self.table.changeItemRow(int(event.mimeData().text()),
                                     self.indexAt(event.position().toPoint()).row())
            self.update_config_file_favorites_dict()
        else:
            super().dropEvent(event)

    def contextMenuEvent(self, event):
        contextMenu = QMenu(self)
        configure_context_menu(contextMenu)
        self.index_right_clicked_on = self.indexAt(event)
        if (self.index_right_clicked_on.data() == conf.FAVORITES_TITLE or
                self.index_right_clicked_on.data() is None):
            return

        selected_item_path = self.model()._data[
            self.model()._data.Name == self.index_right_clicked_on.data()
        ].Path.iloc[0]

        actions_list = [{"menu_item_name": "Remove from list",
                         "associated_method": self.remove_item_from_list},
                        {"menu_item_name": "Change icon",
                         "associated_method": self.select_new_icon},
                        {"menu_item_name": "Revert to default icon",
                         "associated_method": lambda: self.revert_to_default_folder_icon(selected_item_path)}]
        add_actions_to_context_menu(contextMenu, self, actions_list)

        # Show context menu at the position of the mouse event
        contextMenu.exec(self.mapToGlobal(event))
        self.clearSelection()

    def remove_item_from_list(self):
        item_name_to_remove = self.selectedIndexes()[0].data()
        if item_name_to_remove in self.table._data.Name.to_list():
            self.table.deleteRow(item_name_to_remove)
            self.table._data.reset_index(drop=True, inplace=True)
            self.update_config_file_favorites_dict()

    def revert_to_default_folder_icon(self, item_path):
        if item_path in conf.default_config['BASIC_FAVORITES_DICT']['Path']:
            if item_path == os.path.expanduser("~/Desktop"):
                default_icon_path = os.path.join(BASE_ICONS_DIR, '_desktop_.png')
            elif item_path == os.path.expanduser("~/Downloads"):
                default_icon_path = os.path.join(BASE_ICONS_DIR, '_downloads_.png')
            elif item_path == os.path.expanduser("~/Documents"):
                default_icon_path = os.path.join(BASE_ICONS_DIR, '_document_.png')
        else:
            default_icon_path = os.path.join(BASE_ICONS_DIR, conf.FOLDER_ICON_NAME + '.png')

        self.change_icon(default_icon_path)

    def select_new_icon(self):
        self.icon_selection = QFileDialog()
        # Open dialog box and wait for user selection
        icon_file_path, _ = \
            self.icon_selection.getOpenFileName(self,
                                                "Select icon",
                                                SYSTEM_DEFAULT_ICONS_DIR,
                                                options=QFileDialog.Option.DontResolveSymlinks)
        if icon_file_path == '':
            return
        self.change_icon(icon_file_path)

    def change_icon(self, new_icon_full_path: str):
        if self.index_right_clicked_on is not None:
            icn_name = ('favorites_' +
                        self.index_right_clicked_on.data() +
                        '.' +
                        extract_extension_from_path(new_icon_full_path))
            dest_icon_name = os.path.join(ICONS_DIR, icn_name)
            copy_item(new_icon_full_path, dest_icon_name)
            self.table._data.iloc[self.index_right_clicked_on.row(), 3] = dest_icon_name
            self.clearSelection()
            self.update_config_file_favorites_dict()

    def update_config_file_favorites_dict(self):
        fv_dct = self.table._data.loc[:, ['Name', 'Path', 'icon_full_path']].to_dict(orient='list')
        conf.set_attr('BASIC_FAVORITES_DICT', new_att_value=fv_dct)

    def path_at_row(self, row: int) -> str:
        return self.table._data.loc[row, 'Path']
