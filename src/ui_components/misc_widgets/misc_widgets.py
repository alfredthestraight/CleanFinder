from PySide6 import QtWidgets
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QToolBar, QLabel, QCheckBox, QPushButton, QHBoxLayout, \
    QSplitter, QFileDialog, QWidget, QProgressBar


class ProgressBar(QWidget):
    def __init__(self):
        super().__init__()
        self.progress_bar = QProgressBar(self)
        self.progress_value = 0
        self.progress_bar.setValue(self.progress_value)

    def update_progress(self, percent_inc, to_percentage=None):
        if self.progress_value < 100:
            if to_percentage is not None:
                self.progress_value = to_percentage
            else:
                self.progress_value += percent_inc
            self.progress_bar.setValue(self.progress_value)
            QtWidgets.QApplication.instance().processEvents()



class ProgressBarWrapper(ProgressBar):
    def __init__(self, caller, header="Copying progress"):
        super().__init__()
        self.pasting_thread = caller
        self.setWindowTitle(header)

        # Create layout
        self.layout = QHBoxLayout()

        # Create progress bar
        self.layout.addWidget(self.progress_bar)

        self.label = QLabel()
        self.label.setText("0%")
        self.layout.addWidget(self.progress_bar)
        self.layout.addWidget(self.label)

        # Create button
        self.button = QPushButton('Cancel', self)
        if hasattr(caller, 'abort'):
            self.button.clicked.connect(caller.abort)
        self.layout.addWidget(self.button)

        self.setLayout(self.layout)

    def update_progress(self, percent_inc):
        # super().update_progress(percent_inc)
        val = int(self.progress_value)
        self.label.setText(f"{val}%")
        QtWidgets.QApplication.instance().processEvents()



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
