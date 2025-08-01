from sortedcontainers import SortedDict
from PySide6 import QtCore
from PySide6.QtWidgets import QTreeView, QHeaderView, QFileSystemModel
from PySide6.QtCore import QSize
from src.utils.os_utils import *
from src.utils.utils import get_full_path_from_index
from src.shared.vars import conf_manager as conf, logger as logger


class RowHeightDelegate(QItemDelegate):
    def __init__(self, row_height: int):
        self.row_height = row_height
        super(RowHeightDelegate, self).__init__()

    def sizeHint(self, option, index) -> QtCore.QSize:
        return QSize(0, self.row_height)


class TreeFileExplorer(QTreeView):
    def __init__(self, model=None, parent=None, font_size=conf.TEXT_FONT_SIZE, root_path='/',
                 encompassing_ui=None, xdim=None):
        super().__init__(parent=parent)
        self.encompassing_ui = encompassing_ui

        if model is None:
            model = QFileSystemModel()
            model.setRootPath(root_path)

        model.setFilter(QDir.Filter.NoDotAndDotDot | QDir.Filter.Dirs)
        self.model = model
        self.setModel(self.model)

        self.configure_cols_and_headers()

        # Set font size
        f = self.font()
        f.setPointSize(font_size)
        self.setFont(f)

        # Connect clicks to methods
        self.clicked.connect(self.handle_clicked)
        self.expanded.connect(self.handle_expanded)
        self.collapsed.connect(self.handle_collapsed)

        self.current_max_depth = 1
        self.open_branches = SortedDict()
        self.max_open_branch_length = 0
        self.open_branches_depths = SortedDict()
        self.max_open_branch_depth = 0

        self.xdim = xdim

    def sizeHint(self):
        default_size = super().sizeHint()
        if self.xdim is None:
            return default_size
        else:
            return QSize(256, 681)

    def configure_cols_and_headers(self):
        self.header().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.hideColumn(1)
        self.hideColumn(2)
        self.hideColumn(3)
        self.header().hide()
        self.setAlternatingRowColors(False)
        # Row height
        self.setItemDelegate(RowHeightDelegate(conf.TREE_ROW_HEIGHT))
        self.setStyleSheet(conf.TREE_STYLE)

    def get_child_index(self, index, row=0, column=0):
        return self.model.index(row, 0, column)

    def _get_item_depth_within_tree_hierarchy(self, index):
        if self.get_child_index(0, 0, index).data() is None:
            depth = -1
        else:
            depth = 0
        overall_branch = index.data()
        overall_size = len(overall_branch)
        while index.parent().isValid():
            index = index.parent()
            overall_branch = index.data() + '/' + overall_branch
            overall_size = len(overall_branch)
            depth += 1
        return depth, overall_branch, overall_size

    def _get_largest_child_string(self, index):
        max_size_child_data = ''
        max_size_child_size = 0
        if index.data() is not None:
            has_another_child = True
            i = -1
            while has_another_child:
                i += 1
                # child_data = index.child(i, 0).data()
                child_data = self.get_child_index(i, 0, index).data()
                if child_data is None:
                    has_another_child = False
                else:
                    child_size = len(child_data)
                    if child_size > max_size_child_size:
                        max_size_child_data = child_data
                        max_size_child_size = child_size
        return max_size_child_data

    def handle_collapsed(self, index):
        branch_depth, branch_str, _ = self._get_item_depth_within_tree_hierarchy(index)
        branch_str_len = len(branch_str)
        try:
            self.open_branches.pop(branch_str_len)
            self.open_branches_depths(branch_depth)
        except:
            pass
        if branch_str_len == self.max_open_branch_length:
            self.max_open_branch_length = 1 if len(self.open_branches) == 0 else max(list(self.open_branches.keys()))
            self.max_open_branch_depth = 1 if len(self.open_branches) == 0 else max(list(self.open_branches_depths.keys()))
            self.setColumnWidth(0, self.max_open_branch_length * 5 + (1 + self.max_open_branch_depth) * 30)
        logger.info("Tree collapsed: " + str(self.open_branches))

    def handle_expanded(self, index):
        dir_(index)
        branch_depth, branch_str, _ = self._get_item_depth_within_tree_hierarchy(index)
        branch_str_len = len(branch_str)
        if branch_str_len > self.max_open_branch_length:
            self.max_open_branch_length = branch_str_len
        if branch_depth > self.max_open_branch_depth:
            self.max_open_branch_depth = branch_depth
        self.setColumnWidth(0, self.max_open_branch_length * 5 + (1 + self.max_open_branch_depth) * 30)
        self.open_branches[len(branch_str)] = branch_str
        self.open_branches_depths[branch_depth] = branch_str
        logger.info("Tree expanded: " + str(self.open_branches))


    def find_immediate_folders(self, parent_index):
        folders = []
        for row in range(self.model.rowCount(parent_index)):
            child_index = self.model.index(row, 0, parent_index)
            if self.model.isDir(child_index):
                folders.append(child_index)
        return folders

    def handle_clicked(self, index):
        clicked_path = get_full_path_from_index(index)
        logger.info('Tree click: ' + clicked_path)
        if clicked_path != self.encompassing_ui.file_explorer.pandasModel.path:
            self.encompassing_ui.file_explorer.change_path(clicked_path,
                                                           reset_tree_selection=False)

    def expand_specific_folder(self, folder_path):
        # Get the index of the specified folder
        folder_index = self.model.index(folder_path)

        if folder_index.isValid():
            # Expand the folder
            self.expand(folder_index)
            # Hide all other folders
            self.hide_all_except(folder_index)

    def hide_all_except(self, except_index):
        root_index = self.rootIndex()
        self.hide_recursively(root_index, except_index)

    def hide_recursively(self, parent_index, except_index):
        for row in range(self.model.rowCount(parent_index)):
            child_index = self.model.index(row, 0, parent_index)
            if child_index != except_index and not except_index.isAncestorOf(child_index):
                self.setRowHidden(row, parent_index, True)
            self.hide_recursively(child_index, except_index)

    def traverseDirectory(self, parentindex, callback=None):
        if self.model.hasChildren(parentindex):
            path = self.model.filePath(parentindex)
            it = QtCore.QDirIterator(path, self.model.filter() | QtCore.QDir.Filter.NoDotAndDotDot)
            while it.hasNext():
                childIndex = self.model.index(it.next())
                self.traverseDirectory(childIndex, callback=callback)
