from PySide6 import QtWidgets
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QToolBar, QLabel, QCheckBox, QPushButton, QHBoxLayout, \
    QSplitter, QFileDialog, QWidget


class QFileDialogWithCheckbox(QFileDialog):

    def __init__(self, directory=None, checkbox_text=None, default_state=False):
        super(QFileDialogWithCheckbox, self).__init__(directory=directory)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        # self.setAcceptMode(QFileDialog.AcceptOpen)
        self.setFileMode(QFileDialog.FileMode.Directory)

        grid_layout = self.findChild(QtWidgets.QGridLayout)
        grid_layout.children()[0]
        # self.parentWidget()

        self.checkbox = QCheckBox(checkbox_text)

        w1 = grid_layout.itemAtPosition(2, 1).widget()
        w1.setFixedHeight(0)
        w1.setStyleSheet("border: 0px")

        grid_layout.removeWidget(grid_layout.itemAtPosition(3, 0).widget())
        grid_layout.removeWidget(grid_layout.itemAtPosition(3, 1).widget())
        grid_layout.removeWidget(grid_layout.itemAtPosition(2, 0).widget())
        grid_layout.addWidget(self.checkbox, 3, 1)
        self.checkbox.setChecked(default_state)


class CustomSizeQSplitter(QSplitter):

    def __init__(self, type, parent, default_width=None, default_height=None):
        super().__init__(type, parent)
        self.default_width = default_width
        self.default_height = default_height

    def sizeHint(self):
        hint_dims = super(CustomSizeQSplitter, self).sizeHint()
        if self.default_width is not None:
            x = self.default_width
        else:
            x = hint_dims.width()

        if self.default_height is not None:
            y = self.default_height
        else:
            y = hint_dims.height()

        return QSize(x, y)


class CustomSizeQToolBar(QToolBar):
    def __init__(self, parent=None, default_width: int = None, default_height: int = None):
        self.default_width = default_width
        self.default_height = default_height
        if parent is not None:
            super(CustomSizeQToolBar, self).__init__(parent)
        else:
            super(CustomSizeQToolBar, self).__init__()

    def sizeHint(self):
        hint_dims = super(CustomSizeQToolBar, self).sizeHint()
        if self.default_width is not None:
            x = self.default_width
        else:
            x = hint_dims.width()

        if self.default_height is not None:
            y = self.default_height
        else:
            y = hint_dims.height()

        return QSize(x, y)
