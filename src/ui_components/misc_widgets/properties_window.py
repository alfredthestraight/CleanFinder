from typing import Union, Callable
import numpy as np
import os
import datetime
from PySide6.QtWidgets import (QTabWidget, QLabel, QPushButton, QVBoxLayout, QFileDialog, QWidget,
                               QDialog, QDialogButtonBox, QLineEdit, QFrame)
from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon
from src.utils.os_utils import (resize_and_save_png_file, get_item_size_pretty, get_file_apps_info,
                                get_file_type, extract_extension_from_path, copy_item, is_dir,
                                delete_item)

from src.shared.locations import ICONS_DIR, SYSTEM_DEFAULT_ICONS_DIR
from src.utils.utils import convert_incs_to_png, get_full_icon_path
from PySide6.QtCore import Signal, QObject, QThread
from src.shared.vars import conf_manager as conf


def create_separating_line() -> QFrame:
    sep_line = QFrame()
    sep_line.setFrameShape(QFrame.Shape.HLine)
    sep_line.setFrameShadow(QFrame.Shadow.Sunken)
    return sep_line


class Worker(QObject):
    finished = Signal()
    progress = Signal(int)

    def __init__(self, func_to_run_in_thread: Callable, only_finish_when_outcome_equals,
                 run_params: dict = {}):
        super().__init__()
        self.func_to_run_in_thread = func_to_run_in_thread
        self._run_params = run_params
        self.outcome = None
        self.is_finished = False
        self.only_finish_when_outcome_equals = only_finish_when_outcome_equals

    @property
    def run_params(self):
        return self._run_params

    @run_params.setter
    def run_params(self, new_run_params):
        self._run_params = new_run_params

    def run(self):
        self.outcome = self.func_to_run_in_thread(**self.run_params)
        if (self.only_finish_when_outcome_equals is None or
                self.outcome == self.only_finish_when_outcome_equals):
            self.is_finished = True
            self.finished.emit()


class RunInThread:
    """
    For occasions where a function needs to be run in a separate thread
    NOTE: in many cases in this project using this triggered a runtime error ("API misuse:
    modification of a menu's items on a non-main thread when the menu is part of the main
    menu"), and I had to use custom QThread and Worker directly
    """
    def __init__(self, func_to_run_in_thread: Callable, func_to_run_when_finished: Callable = None,
                 only_finish_when_outcome_equals=None, params: dict = {}):
        self.func_to_run_when_finished = func_to_run_when_finished
        self.thread = QThread()
        self.worker = Worker(func_to_run_in_thread, only_finish_when_outcome_equals, params)
        self.worker.moveToThread(self.thread)
        self.is_alive = True

        self.thread.started.connect(self.worker.run)
        if func_to_run_when_finished is not None:
            self.worker.finished.connect(func_to_run_when_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

    def run(self):
        self.worker.run()

    @property
    def params(self):
        return self.worker.run_params

    @params.setter
    def params(self, new_params):
        self.worker.run_params = new_params

    @property
    def is_finished(self):
        return self.worker.is_finished

    def kill(self):
        print("Killing myself (pasting thread):", str(id(self)))
        self.thread.quit()
        self.is_alive = False


class PropertiesWindowCalculateSizeInThread(QDialog):
    def __init__(self, item_or_items: Union[str, list[str]]):
        super(PropertiesWindowCalculateSizeInThread, self).__init__()

        self.is_currently_presented = True
        self.thread_runner = RunInThread(func_to_run_in_thread=get_item_size_pretty,
                                         func_to_run_when_finished=self.update_item_size_label_text,
                                         params={'fs': item_or_items})
        self.thread_runner.thread.start()

        self.setGeometry(300, 300, 300, 300)

    def update_item_size_label_text(self):
        self.item_size.setText("Size:\t\t\t" + str(self.thread_runner.worker.outcome[2]))

    def apply(self):
        print("Apply button clicked")

    def kill_thread(self):
        self.thread_runner.kill()

    def accept(self):
        print("OK button clicked")
        super(PropertiesWindowCalculateSizeInThread, self).accept()
        if hasattr(self, 'new_icon_src_path') and hasattr(self, 'item'):
            if self.new_icon_src_path is not None:
                if is_dir(self.item):
                    success = copy_item(self.new_icon_src_path,
                                        get_full_icon_path(conf.FOLDER_ICON_NAME))
                else:
                    file_type_ext = extract_extension_from_path(self.item)
                    if file_type_ext == '':
                        success = copy_item(self.new_icon_src_path,
                                            get_full_icon_path(conf.FILE_ICON_NAME))
                    else:
                        new_icon_ext = extract_extension_from_path(self.new_icon_src_path)
                        dest_full_name = \
                            os.path.join(ICONS_DIR, file_type_ext + '.' + new_icon_ext)
                        success = copy_item(self.new_icon_src_path, dest_full_name)
                if success >= 0:
                    if new_icon_ext == 'icns':
                        dest_full_name_as_png = \
                            os.path.join(ICONS_DIR, file_type_ext + '.png')
                        if os.path.exists(dest_full_name_as_png):
                            delete_item(dest_full_name_as_png)
                        success = convert_incs_to_png(dest_full_name)
                        delete_item(dest_full_name)
                        dest_full_name = dest_full_name_as_png
                        if success < 0:
                            return
                    resize_and_save_png_file(dest_full_name)
        self.done(Qt.WidgetAttribute.WA_DeleteOnClose.value)
        self.kill_thread()
        self.is_currently_presented = False

    def reject(self):
        print("Cancel button clicked")
        super(PropertiesWindowCalculateSizeInThread, self).reject()
        self.done(Qt.WidgetAttribute.WA_DeleteOnClose.value)
        self.kill_thread()
        self.is_currently_presented = False

    def move_to_random_position(self, base_x: int, base_y: int):
        if base_x > 800:
            x = abs(base_x + int(np.random.normal(0, 60, 1))) - 500
        elif base_x < 800:
            x = abs(base_x + int(np.random.normal(0, 60, 1))) + 500
        else:
            x = abs(base_x + int(np.random.normal(0, 60, 1)))
        y = abs(base_y + int(np.random.normal(0, 100, 1))) + 200
        if x < 10:
            x = 10
        if y < 10:
            y = 10
        self.move(QPoint(x, y))


class PropertiesWindowSingleItem(PropertiesWindowCalculateSizeInThread):
    def __init__(self, item: str, encompassing_obj):
        super(PropertiesWindowSingleItem, self).__init__(item)

        self.setWindowTitle(item.split(os.sep)[-1])
        self.encompassing_obj = encompassing_obj
        self.new_icon_src_path = None
        self.new_icon_dest_png_full_name = None
        self.item = item

        default_app, _ = get_file_apps_info(item)
        if default_app is not None:
            default_app = default_app.absoluteString.__str__().split(os.sep)[-2].\
                replace('.app', '').replace('%20', ' ')
        if os.path.isdir(item):
            file_type = "Directory"
        else:
            file_type = get_file_type(item)
        location = os.sep.join(item.split(os.sep)[:-1])
        creation_time = \
            datetime.datetime.fromtimestamp(os.path.getctime(item)).strftime(conf.DATE_FORMAT)
        last_modified_time = \
            datetime.datetime.fromtimestamp(os.path.getmtime(item)).strftime(conf.DATE_FORMAT)
        last_access_time = \
            datetime.datetime.fromtimestamp(os.stat(item).st_atime).strftime(conf.DATE_FORMAT)

        # Create the tab widget
        self.tabs = QTabWidget()
        self.general_tab = QWidget()
        self.misc_tab = QWidget()

        # Add tabs to the tab widget
        # self.tabs.addTab(self.general_tab, "General")

        # Labels for general tab
        self.file_type = QLabel(f"File type:\t\t{file_type}")

        self.app_icon = QIcon()
        icon_path = get_full_icon_path(extract_extension_from_path(item))
        if icon_path is not None:
            self.app_icon.addFile(icon_path)
        else:
            if is_dir(item):
                self.app_icon.addFile(get_full_icon_path(conf.FOLDER_ICON_NAME))
            else:
                self.app_icon.addFile(get_full_icon_path(conf.FILE_ICON_NAME))
        self.change_icon_pushbutton = QPushButton(icon=self.app_icon)
        self.change_icon_pushbutton.setStyleSheet(
            "QPushButton{border: none; background-color: white;}"
        )
        self.change_icon_pushbutton.clicked.connect(self.change_extension_icon)
        self.change_icon_pushbutton.setIconSize(QSize(50, 50))

        line1 = create_separating_line()

        if len(location) <= 10:
            self.location = QLabel(f"Location:\t\t{location}")
        else:
            self.location = QLabel("Location:")
            self.location_box = QLineEdit(location)
            self.location_box.setMaximumWidth(500)
            self.location_box.setStyleSheet(
                "QLineEdit{border: none; background-color: transparent;}")
            self.location_box.setReadOnly(True)

        self.item_size = QLabel("Size:\t\t\t")   # Waiting to be updates
        self.creation_date = QLabel(f"Created at:\t\t{creation_time}")
        self.modified_date = QLabel(f"Modified at:\t\t{last_modified_time}")
        self.last_access_date = QLabel(f"Last accessed at:\t\t{last_access_time}")
        line2 = create_separating_line()

        # Layout for General tab
        self.general_layout = QVBoxLayout()
        self.general_tab.setLayout(self.general_layout)

        self.general_layout.addWidget(self.file_type)
        self.general_layout.addWidget(self.change_icon_pushbutton)
        self.general_layout.addWidget(line1)
        self.general_layout.addWidget(self.location)
        if hasattr(self, 'location_box'):
            self.general_layout.addWidget(self.location_box)
        self.general_layout.addWidget(self.item_size)
        self.general_layout.addWidget(line2)
        self.general_layout.addWidget(self.creation_date)
        self.general_layout.addWidget(self.modified_date)
        self.general_layout.addWidget(self.last_access_date)

        # Layout for Misc tab
        self.misc_layout = QVBoxLayout()
        self.misc_label = QLabel("Miscellaneous settings go here")
        self.misc_layout.addWidget(self.misc_label)
        self.misc_tab.setLayout(self.misc_layout)

        # Create the buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        # Connect the buttons to their functions
        self.button_box.accepted.connect(self.accept)  # OK button
        self.button_box.rejected.connect(self.reject)  # Cancel button

        # Main layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(1, 10, 1, 5)   # left, top, right, bottom
        self.main_layout.addWidget(self.general_tab)
        self.main_layout.addWidget(self.button_box)

        self.setLayout(self.main_layout)

    def change_extension_icon(self):
        self.default_app_selection = QFileDialog()
        img_file_path, _ = \
            self.default_app_selection.getOpenFileName(self, "Select app",
                                                       SYSTEM_DEFAULT_ICONS_DIR,
                                                       options=QFileDialog.Option.DontResolveSymlinks)
        self.new_icon_src_path = img_file_path
        if self.new_icon_src_path == '':  # If the user cancels the selection
            return
        try:
            self.change_icon_pushbutton.setIcon(QIcon(self.new_icon_src_path))
        except:
            pass


class PropertiesWindowMultipleItems(PropertiesWindowCalculateSizeInThread):
    def __init__(self, items_list: list[str], encompassing_obj):
        super(PropertiesWindowMultipleItems, self).__init__(items_list)
        self.setWindowTitle(items_list[0].split(os.sep)[-1] + " (and other items)")
        self.encompassing_obj = encompassing_obj
        self.items_list = items_list

        # Create the tab widget
        self.tabs = QTabWidget()
        self.general_tab = QWidget()
        self.misc_tab = QWidget()

        # Layout for General tab
        self.general_layout = QVBoxLayout()
        self.general_tab.setLayout(self.general_layout)

        # Labels for general tab
        self.number_of_items = QLabel("Items selected:\t\t" + str(len(items_list)))
        line1 = create_separating_line()
        # self.location = QLabel("Location:\t\t" + self.encompassing_obj.path)

        if len(self.encompassing_obj.path) <= 100:
            self.location = QLabel("Location:\t\t" + self.encompassing_obj.path)
        else:
            self.location = QLabel("Location:")
            self.location_box = QLineEdit(self.encompassing_obj.path)
            self.location_box.setMaximumWidth(500)
            self.location_box.setStyleSheet(
                "QLineEdit{border: none; background-color: transparent;}")
            self.location_box.setReadOnly(True)

        line2 = create_separating_line()
        self.item_size = QLabel("Size:\t\t\t")   # Waiting to be updated

        self.general_layout.addWidget(self.number_of_items)
        self.general_layout.addWidget(line1)
        self.general_layout.addWidget(self.location)
        if hasattr(self, 'location_box'):
            self.general_layout.addWidget(self.location_box)
        self.general_layout.addWidget(line2)
        self.general_layout.addWidget(self.item_size)

        # Layout for Misc tab
        self.misc_layout = QVBoxLayout()
        self.misc_label = QLabel("Miscellaneous settings go here")
        self.misc_layout.addWidget(self.misc_label)
        self.misc_tab.setLayout(self.misc_layout)

        # Create the buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        # Connect the buttons to their functions
        self.button_box.accepted.connect(self.accept)  # OK button
        self.button_box.rejected.connect(self.reject)  # Cancel button

        # Main layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(1, 10, 1, 5)   # left, top, right, bottom
        self.main_layout.addWidget(self.general_tab)
        self.main_layout.addWidget(self.button_box)

        self.setLayout(self.main_layout)
