import pandas as pd

from PySide6 import QtCore, QtGui
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtWidgets import QListView

from src.utils.os_utils import get_icon_names, get_dataframe_of_file_names_in_directory, is_dir
from src.utils.utils import get_full_icon_path

from src.shared.vars import conf_manager as conf
from src.non_ui_components.configurations_manager import is_string_rgb
import time
# About roles:
# https://doc.qt.io/qt-6/qt.html


class PandasModelBase(QtCore.QAbstractTableModel):

    def __init__(self, datapath=None,
                 data=None,
                 sorted=True,
                 cols_mapping={2: 5, 1: 7},
                 columns_ordering_scheme=[(1, 1), (2, 0), (0, 0), (3, 0)]):
        if datapath is not None:
            super(PandasModelBase, self).__init__()
            self._data = get_dataframe_of_file_names_in_directory(datapath)
            self.columns = self._data.columns.values
            self._path = datapath
        elif data is not None:
            super(PandasModelBase, self).__init__()
            self._data = data
            self.columns = self._data.columns.values
            self._path = ''
        else:
            super(PandasModelBase, self).__init__()
            self._data = pd.DataFrame()
            self.columns = []
            self._path = ''
        self.sorted = sorted

        if self.sorted:
            self.cols_mapping = cols_mapping
            self._columns_ordering_scheme = columns_ordering_scheme
            self.enforce_sorting()

        self.cut_items = []
        self.cut_items_path = ''
        self.allow_decoration_role = True

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, newpath):
        self._path = newpath

    @property
    def columns_ordering_scheme(self):
        return self._columns_ordering_scheme

    @columns_ordering_scheme.setter
    def columns_ordering_scheme(self, value):
        self._columns_ordering_scheme = value

    def data(self, index, role):

        curr_row = index.row()

        # Text to display
        if role == Qt.ItemDataRole.DisplayRole:
            # See below for the nested-list data structure.
            # .row() indexes into the outer list,
            # .column() indexes into the sub-list
            text = self._data.iloc[curr_row, index.column()]
            return text

        if role == Qt.ItemDataRole.EditRole:
            return True

        # Something to display left of the text (specifically - the icon)
        if role == Qt.ItemDataRole.DecorationRole and self.allow_decoration_role:
            if index.column() == conf.FILENAME_COLUMN_INDEX:
                item_type = self._data.iloc[curr_row, :]['file_type']
                return QtGui.QIcon(get_full_icon_path(item_type))

        # Change text color by column
        if role == Qt.ItemDataRole.ForegroundRole:
            if index.column() != conf.FILENAME_COLUMN_INDEX:
                return QtGui.QBrush(QColor.fromRgb(conf.FILE_EXPLORER_FONT_COLOR_OTHER_COLS_R,
                                                   conf.FILE_EXPLORER_FONT_COLOR_OTHER_COLS_G,
                                                   conf.FILE_EXPLORER_FONT_COLOR_OTHER_COLS_B))
            elif (self._data.iloc[curr_row, 0] in self.cut_items and
                  self.cut_items_path == self._path):
                return QColor('grey')
            elif self._data.iloc[curr_row, 9]:
                return QColor('grey')

        if role == Qt.ItemDataRole.FontRole:
            if (self._data.iloc[curr_row, 0] in self.cut_items and
                    self.cut_items_path == self._path):
                boldFont = QFont()
                boldFont.setItalic(True)
                return boldFont

    def rowCount(self, index):
        # The length of the outer list.
        return self._data.shape[0]

    def columnCount(self, index):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        return self._data.shape[1]

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == QtCore.Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self._data.columns.values[section].format(section)

        # Other headers
        return super().headerData(section, orientation, role)

    def sortByColumn(self, column_ind_list, ascending_list, case_insensitive=True, data_to_sort=None):
        self.beginResetModel()
        if data_to_sort is None:
            data_to_sort = self._data
        mapped_columns = [self.cols_mapping.get(x, x) for x in column_ind_list]
        if conf.FOLDERS_ALWAYS_ABOVE_FILES:
            mapped_columns = [conf.IS_FOLDER_COLUMN_INDEX] + mapped_columns
            ascending_list = [False] + ascending_list
        if case_insensitive:
            data_to_sort.sort_values(by=list(data_to_sort.columns[mapped_columns]),
                                     ascending=ascending_list, axis=0, inplace=True,
                                     key=lambda col: col.str.lower() if col.dtype == 'object' else col)
        else:
            data_to_sort.sort_values(by=list(data_to_sort.columns[mapped_columns]),
                                     ascending=ascending_list, axis=0, inplace=True)
        data_to_sort.reset_index(drop=True, inplace=True)
        self.endResetModel()

    def enforce_sorting(self, data_to_sort=None):
        if data_to_sort is None:
            data_to_sort = self._data
        if data_to_sort.shape[0] > 0:
            self.sortByColumn(column_ind_list=[x[0]
                                               for x in self._columns_ordering_scheme[::-1]],
                              ascending_list=[x[1]==0
                                              for x in self._columns_ordering_scheme[::-1]],
                              data_to_sort=data_to_sort)
        data_to_sort.reset_index(drop=True, inplace=True)

    def insertRows(self, new_row: list, position: int = None):
        if position is None:
            position = self._data.index.max() + 1
        self.beginResetModel()
        self._data.loc[position + 1] = new_row
        self.endResetModel()
        if self.sorted:
            self.enforce_sorting()
        self._data.reset_index(drop=True, inplace=True)


    def deleteRows(self, item_name):
        self.beginResetModel()
        ind_to_delete = \
            list(self._data[self._data.iloc[:, conf.FILENAME_COLUMN_INDEX] == item_name].index)
        self._data.drop(index=ind_to_delete, inplace=True)
        self._data.reset_index(drop=True, inplace=True)
        self.endResetModel()

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if value is not None and role == Qt.ItemDataRole.EditRole:
            self._data.iloc[index.row(), 0] = value
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
            return True
        return False

    def replace_data_and_path(self, newdata: pd.DataFrame, newpath: str,
                              cols_ordering_scheme: list[tuple[int]]=None):
        self._data = newdata
        self._path = newpath
        if self.sorted:
            if cols_ordering_scheme is not None:
                self.columns_ordering_scheme = cols_ordering_scheme
            self.enforce_sorting()
        self._data.reset_index(drop=True, inplace=True)
        self.layoutChanged.emit()

    def update_item(self, row, column, new_value):
        index = self.index(row, column)
        self.setData(index, new_value, Qt.ItemDataRole.EditRole)
        # Emit the dataChanged signal to notify the view
        self.dataChanged.emit(index, index)

    # Notify about structure changes (e.g., rows/columns added or removed)
    def refresh_data(self):
        newdata = get_dataframe_of_file_names_in_directory(self._path)
        if self.sorted:
            self.enforce_sorting(newdata)
        if newdata.equals(self._data):
            return
        else:
            self.beginResetModel()
            self._data = newdata
            self.endResetModel()
            if self.sorted:
                self.enforce_sorting()
            self.layoutChanged.emit()


    def flags(self, index):
        return Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable



class PandasModel(PandasModelBase):
    """
    Pandas model which also supports drag and drop
    """
    def flags(self, index):
        return (Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled |
                Qt.ItemFlag.ItemIsDropEnabled | Qt.ItemFlag.ItemIsEditable)

    def supportedDropActions(self):
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction

    def mimeTypes(self):
        return ['application/x-qabstractitemmodeldatalist']


class MiscItemsTable(QtCore.QAbstractTableModel):

    def __init__(self, dict=None, spacer_column_indent=0):
        super(MiscItemsTable, self).__init__()
        self._data = pd.DataFrame(dict)
        icon_names = pd.DataFrame(get_icon_names(self._data.Path.to_list()), index=['file_type']).T
        self._data = pd.merge(self._data, icon_names, left_on='Path', right_index=True, how='left')
        if spacer_column_indent > 0:
            self._data.insert(0, 'spacer_col', ' ' * spacer_column_indent)
            self.FAVORITES_FILENAME_COLUMN_INDEX = 1
        else:
            self.FAVORITES_FILENAME_COLUMN_INDEX = 0
        self.columns = self._data.columns.values
        self._path = ''
        self.spacer_column_indent = spacer_column_indent

    def flags(self, index):
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled

    def data(self, index, role):
        # Text to display
        if role == Qt.ItemDataRole.DisplayRole:
            # See below for the nested-list data structure.
            # .row() indexes into the outer list,
            # .column() indexes into the sub-list
            return self._data.iloc[index.row(), index.column()]

        if role == Qt.ItemDataRole.EditRole:
            return True

        if role == Qt.ItemDataRole.DecorationRole:
            if index.column() == self.FAVORITES_FILENAME_COLUMN_INDEX:
                item_icon = self._data.iloc[index.row(), :]['icon_full_path']
                return QtGui.QIcon(item_icon)

    def rowCount(self, index):
        # The length of the outer list.
        return self._data.shape[0]

    def columnCount(self, index):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        return self._data.shape[1]

    def appendRow(self, new_item_name, new_item_path, new_item_icon=None):
        self.beginResetModel()
        # new_item_icon = get_icon_names([new_item_path])[new_item_path]
        if is_dir(new_item_path) and new_item_name not in self._data.Name.to_list():
            self._data.loc[len(self._data)] = {'spacer_col': ' ' * self.spacer_column_indent,
                                               'Name': new_item_name,
                                               'Path': new_item_path,
                                               'icon_full_path': new_item_icon,
                                               'file_type': 'Folder'}
        self.endResetModel()

    def deleteRow(self, item_name):
        df_index_to_remove = self._data[self._data.Name == item_name].index[0]
        self._data.drop(index=df_index_to_remove, inplace=True)
        self.endResetModel()

    def changeItemRow(self, from_row, to_row):
        self.beginResetModel()

        ind = list(self._data.index)
        if from_row < to_row:
            ind = ind[0:from_row] + ind[from_row+1:to_row+1] + [ind[from_row]] + ind[to_row+1:]
        elif from_row > to_row:
            ind = ind[0:to_row] + [ind[from_row]] + ind[to_row:from_row] + ind[from_row+1:]

        self._data = self._data.loc[ind, :]
        self._data.reset_index(drop=True, inplace=True)

        self.endResetModel()


# Adds a single row at a time, with no sorting or anything else
class SimplePandasModel(PandasModelBase):
    def __init__(self, data=None):
        super(SimplePandasModel, self).__init__(data=data, sorted=False)
        self.num_rows = 0

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return self._data.iloc[index.row(), index.column()]

    def insertRows(self, new_row):
        self.beginResetModel()
        self._data.loc[self.num_rows, :] = new_row
        self.num_rows += 1
        self.endResetModel()

    def clear_all_data(self):
        self._data = self._data.iloc[0:0, :]


class SimplePandasModel2(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, parnet=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid():
            value = self._data.iloc[index.row(), index.column()]
            if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
                return str(value)
            elif role == Qt.ItemDataRole.ForegroundRole:
                if is_string_rgb(value):
                    col = QColor()
                    col.setRed(int(value.replace('rgb(', '').split(',')[0]))
                    col.setGreen(int(value.replace('rgb(', '').split(', ')[1]))
                    col.setBlue(int(value.replace(')', '').split(', ')[2]))
                    return col

    def setData(self, index, value, role):
        if role == Qt.ItemDataRole.EditRole:
            self._data.iloc[index.row(), index.column()] = value
            return True
        return False

    def headerData(self, col, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._data.columns[col]

    def flags(self, index):
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable


class simple_list_model(QListView):

    procDone = QtCore.Signal(int)

    def __init__(self):
        self.inner_list = []
        super(simple_list_model, self).__init__()

    @QtCore.Slot()
    def add(self, item):
        self.inner_list.append(item)
        self.procDone.emit(1)

    def pop(self):
        self.inner_list.pop()
