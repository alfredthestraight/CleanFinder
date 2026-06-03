import pandas as pd

from PySide6.QtWidgets import QMainWindow, QTableView, QAbstractItemView, QLabel, QFileDialog, \
    QMenu, QPushButton, QColorDialog, QVBoxLayout, QMenuBar, QWidget, QDialogButtonBox
from PySide6 import QtCore
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QIcon, QAction

from src.data_models import SimplePandasModel2
from src.shared.vars import conf_manager as conf
from src.utils.utils import get_full_icon_path, is_legal_key_sequence
from src.utils.os_utils import extract_extension_from_path, extract_filename_from_path
from src.ui_components.misc_widgets.shortcut_keys_configuration import KeyboardShortcutSelectorUi
from src.ui_components.misc_widgets.dialogs_and_messages import CustomQDialogButtonBox, \
    QDialogButtonsAndWidgets
from src.ui_components.misc_widgets.misc_widgets import DropdownTextValues
from src.ui_components.misc_widgets.shortcut_keys_configuration import LabelsSelectionPerCategory


class color_picker:
    def __init__(self, row: int, styles_tbl: QTableView):
        self.row = row
        self.styles_tbl = styles_tbl

    def __call__(self):
        color = QColorDialog.getColor()
        if color.isValid():
            selected_rgb = 'rgb(' + ', '.join([str(color.red()),
                                               str(color.green()),
                                               str(color.blue())]) + ')'
            self.styles_tbl.model().setData(self.styles_tbl.model().index(self.row, 2),
                                            selected_rgb, Qt.ItemDataRole.EditRole)


class folder_picker:
    def __init__(self, row: int, styles_tbl: QTableView):
        self.row = row
        self.styles_tbl = styles_tbl

    def __call__(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.Directory)
        file_dialog.setOption(QFileDialog.Option.ShowDirsOnly)
        folder = file_dialog.getExistingDirectory(dir=conf.DEFAULT_PATH)
        if folder:
            self.styles_tbl.model().setData(self.styles_tbl.model().index(self.row, 2),
                                            folder, Qt.ItemDataRole.EditRole)


class date_format_picker:
    def __init__(self, row: int, styles_tbl: QTableView, curr_format: str):
        self.row = row
        self.styles_tbl = styles_tbl
        self.curr_format = curr_format
        self.available_formats = ["%Y/%m/%d %H:%M",
                                  "%Y-%m-%d %H:%M",
                                  "%Y/%m/%d %H:%M:%S",
                                  "%Y-%m-%d %H:%M:%S"]

    def __call__(self):
        self.selection_widget = DropdownTextValues(
            self.available_format,
            buttons=QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            default_value=self.curr_format
        )
        btn_selected = self.selection_widget.exec()
        if btn_selected == 1:
            self.styles_tbl.model().setData(self.styles_tbl.model().index(self.row, 2),
                                            self.selection_widget.text, Qt.ItemDataRole.EditRole)


class font_picker:
    def __init__(self, row: int, styles_tbl: QTableView):
        self.row = row
        self.styles_tbl = styles_tbl

    def __call__(self):
        file_dialog = QFileDialog()
        folder, _ = file_dialog.getOpenFileName(dir='/System/Library/Fonts/Supplemental')
        if folder:
            ext = extract_extension_from_path(folder)
            if ext.lower() in ['ttf', 'ttc']:
                font_name = extract_filename_from_path(folder).replace('.' + ext, '')
                self.styles_tbl.model().setData(self.styles_tbl.model().index(self.row, 2),
                                                font_name, Qt.ItemDataRole.EditRole)


# Create the menu bar
def populate_menubar_and_connect_triggers(ui_obj: QMainWindow, menubar_manager):

    ui_obj.menu_bar = ui_obj.menuBar()

    # Add a file menu
    ui_obj.file_menu = QMenu("File", ui_obj)
    ui_obj.menu_bar.addMenu(ui_obj.file_menu)

    # Add actions to the file menu
    ui_obj.new_folder_action = QAction("Create new folder", ui_obj)
    ui_obj.new_file_action = QAction("Create file", ui_obj)
    ui_obj.save_action = QAction("Save", ui_obj)

    ui_obj.file_menu.addAction(ui_obj.new_folder_action)
    ui_obj.file_menu.addAction(ui_obj.new_file_action)
    ui_obj.file_menu.addSeparator()
    ui_obj.file_menu.addAction(ui_obj.save_action)

    # Add an edit menu
    ui_obj.edit_menu = QMenu("Edit", ui_obj)
    ui_obj.edit_menu = ui_obj.menu_bar.addMenu("Edit")

    # Add actions to the edit menu
    ui_obj.copy_action = QAction("Copy", ui_obj)
    ui_obj.paste_action = QAction("Paste", ui_obj)
    ui_obj.configure_keyboard_shortcuts_action = QAction("Keyboard shortcuts", ui_obj)
    ui_obj.configure_styles_action = QAction("Edit configurations", ui_obj)
    ui_obj.show_hide_left_pane = QAction("Show / Hide left pane", ui_obj)
    # ui_obj.zoom_action = QAction("Zoom", ui_obj)

    ui_obj.edit_menu.addAction(ui_obj.copy_action)
    ui_obj.edit_menu.addAction(ui_obj.paste_action)
    ui_obj.edit_menu.addAction(ui_obj.configure_keyboard_shortcuts_action)
    ui_obj.edit_menu.addAction(ui_obj.configure_styles_action)
    ui_obj.edit_menu.addAction(ui_obj.show_hide_left_pane)
    # ui_obj.edit_menu.addAction(ui_obj.zoom_action)

    ui_obj.configure_styles_action.triggered.connect(menubar_manager.configure_styles)
    ui_obj.configure_keyboard_shortcuts_action.triggered.connect(menubar_manager.configure_keymap)
    ui_obj.show_hide_left_pane.triggered.connect(menubar_manager.run_show_hide_left_pane)


class CloseOnEscapeEventFilter(QtCore.QObject):
    def __init__(self, q_main_window_obj):
        super().__init__()
        self.q_main_window_obj = q_main_window_obj

    def eventFilter(self, source, event):
        if (event.type() == QEvent.Type.KeyPress):
            if (event.key() == Qt.Key.Key_Escape):
                self.q_main_window_obj.close()
        return super().eventFilter(source, event)


class MebuBarManager(QMainWindow):
    def __init__(self, ui):
        super().__init__()
        self.uis_manager = ui.encompassing_uis_manager
        populate_menubar_and_connect_triggers(ui, self)

    """
     Menu bar actions
    """

    def configure_keyboard_shortcuts(self):
        print("configure_keyboard_shortcuts")

    def run_show_hide_left_pane(self):
        print("configure_keymap")
        if conf.LEFT_PANE_WIDTH == 0:
            conf.set_attr('LEFT_PANE_WIDTH', 550)
        else:
            conf.set_attr('LEFT_PANE_WIDTH', 0)
        self.uis_manager.show_or_hide_left_panes()

    def configure_keymap(self):
        print("configure_keymap")

        self.keymap_df_ = pd.DataFrame.from_dict(
            conf.get('keyboard_shortcuts'), orient='index').\
            apply(lambda x: x.dropna().tolist(), axis=1).\
            reset_index()
        self.keymap_df_.columns = ['Action', 'Shortcuts']
        self.keymap_df__original = self.keymap_df_.copy()  # Before any changes are made by the user

        self.shortcuts_selection_widget = \
            LabelsSelectionPerCategory(categories_to_values_df=self.keymap_df_,
                                       value_selection_dialog=KeyboardShortcutSelectorUi,
                                       containing_obj=self)
        self.dialog = \
            QDialogButtonsAndWidgets(widgets_list=[],
                                     buttons_dict={'OK': self.keymap_menu_clicked_ok,
                                                   'Cancel': self.keymap_menu_clicked_cancel,
                                                   'Apply': self.keymap_menu_clicked_apply,
                                                   'Restore defaults': self.restore_default_keymap}
                                     )

        self.overall_layout = QVBoxLayout()
        user_explanation = QLabel()
        user_explanation.setText("Remove keyboard shortcuts, "
                                 "add keyboard shortcuts, or drag & drop displayed shortcuts "
                                 "between actions")
        user_explanation.setStyleSheet("QLabel{background-color: transparent; padding: 5 5 5 5;}")
        self.overall_layout.addWidget(user_explanation)
        self.overall_layout.addWidget(self.shortcuts_selection_widget)
        self.overall_layout.addStretch(1)
        self.overall_layout.addWidget(self.dialog)
        self.main_widget = QWidget()
        self.main_widget.setLayout(self.overall_layout)

        self.keymap_window = QMainWindow()
        self._keymap_window_install_event_filter = CloseOnEscapeEventFilter(self.keymap_window)
        self.keymap_window.installEventFilter(self._keymap_window_install_event_filter)
        self.keymap_window.resize(800, 700)
        self.keymap_window.setCentralWidget(self.main_widget)
        self.keymap_window.setWindowTitle("Keyboard shortcuts")
        self.keymap_window.show()

    def keymap_menu_clicked_ok(self):
        self.keymap_menu_clicked_apply()
        self.keymap_window.close()

    def keymap_menu_clicked_cancel(self):
        self.keymap_window.close()

    def keymap_menu_clicked_apply(self):
        updated_keymap_df = self.shortcuts_selection_widget.updated_categories_to_values_df
        rows_changes = updated_keymap_df[
            updated_keymap_df.Shortcuts != self.keymap_df__original.Shortcuts
        ]
        if rows_changes.shape[0] > 0:
            self.update_keymap_in_configure_file(rows_changes)

    def update_keymap_in_configure_file(self, changed_keymap_df: pd.DataFrame):
        for i, r in changed_keymap_df.iterrows():
            if not all([is_legal_key_sequence(str(s)) for s in r.Shortcuts]):
                continue
            conf.update_config_dict(["keyboard_shortcuts", r.Action], r.Shortcuts)
        self.uis_manager.reload_keyboard_shortcuts()

    def restore_default_keymap(self):
        msg_box = CustomQDialogButtonBox("Restore default configs",
                                         f"Are you sure? This cannot be undone")
        reply = msg_box.exec()
        self.keymap_window.close()
        if reply == 1:  # OK
            conf.restore_default_keymap()
            self.uis_manager.reload_keyboard_shortcuts()

    def configure_styles(self):
        print("configure_styles")
        self.styles_window = QMainWindow()
        self.styles_table = QTableView()
        self.styles_table.horizontalHeader().setStyleSheet(
            """QHeaderView::section{
            background-color: transparent; border: none;font-size: 14px; font-weight: 400;}"""
        )
        self.styles_table.horizontalHeader().setStretchLastSection(False)
        self._styles_table_install_event_filter = CloseOnEscapeEventFilter(self.styles_window)
        self.styles_table.installEventFilter(self._styles_table_install_event_filter)

        self.config_data = pd.DataFrame(conf.get_user_styles_config())
        self.config_data_original = self.config_data.copy()
        self.config_data[''] = ''

        self.styles_df = SimplePandasModel2(self.config_data)
        self.styles_table.setModel(self.styles_df)
        self.styles_table.hideColumn(0)
        self.styles_table.hideColumn(3)
        self.styles_table.setColumnWidth(1, 300)
        self.styles_table.setColumnWidth(2, 300)
        self.styles_table.setColumnWidth(4, 33)
        self.styles_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        self.style_selection_buttons = {}
        for i in range(self.config_data.shape[0]):
            btn = QPushButton()
            btn.setFixedWidth(30)
            btn.setFixedHeight(30)
            if str(self.config_data.iloc[i, 2])[:4] == 'rgb(':
                btn.setIcon(QIcon(get_full_icon_path('_color_pick_')))
                btn.clicked.connect(color_picker(i, self.styles_table))
            elif self.config_data.loc[i, 'config_keys_path'][0] == 'DEFAULT_PATH':
                btn.setIcon(QIcon(get_full_icon_path('_symlink_dir_')))
                btn.clicked.connect(folder_picker(i, self.styles_table))
            elif self.config_data.loc[i, 'config_keys_path'][0] == 'DATE_FORMAT':
                btn.setIcon(QIcon(get_full_icon_path('_date_format_picker_')))
                btn.clicked.connect(date_format_picker(i, self.styles_table, conf.DATE_FORMAT))
            elif self.config_data.loc[i, 'Feature'] == 'Font':
                btn.setIcon(QIcon(get_full_icon_path('_font_picker_')))
                btn.clicked.connect(font_picker(i, self.styles_table))
            else:
                continue
            self.style_selection_buttons[i] = btn
            self.styles_table.setIndexWidget(self.styles_table.model().index(i, 4), btn)

        self.styles_window.resize(678, 800)

        self.dialog = \
            QDialogButtonsAndWidgets(widgets_list=[self.styles_table],
                                     buttons_dict={'OK': self.styles_menu_clicked_ok,
                                                   'Cancel': self.styles_menu_clicked_cancel,
                                                   'Apply': self.styles_menu_clicked_apply,
                                                   'Restore defaults': self.restore_default_styles}
                                     )
        self.styles_layout = QVBoxLayout(self.dialog)
        self.styles_layout.addWidget(self.styles_table)
        self.styles_layout.addWidget(self.dialog)

        self.main_widget = QWidget()
        self.main_widget.setLayout(self.styles_layout)
        self.styles_window.setCentralWidget(self.main_widget)
        self.styles_window.show()

    def styles_menu_clicked_ok(self):
        self.styles_menu_clicked_apply()
        self.styles_window.close()

    def styles_menu_clicked_cancel(self):
        self.styles_window.close()

    def styles_menu_clicked_apply(self):
        rows_changes = self.styles_df._data[self.styles_df._data.Value !=
                                            self.config_data_original.Value]
        if len(rows_changes) > 0:
            self.update_styles_in_configure_file(rows_changes)

    def restore_default_styles(self):
        msg_box = CustomQDialogButtonBox("Restore default configs",
                                         f"Are you sure? This cannot be undone")
        reply = msg_box.exec()
        if reply == 1:   # OK
            conf.revert_back_to_default_config()
        self.styles_window.close()

    def update_styles_in_configure_file(self, styles_df: pd.DataFrame):
        for i, r in styles_df.iterrows():
            var_name = r['config_keys_path'][len(r['config_keys_path'])-1]
            if r.value_type == 'int':
                typed_value = int(r.Value)
            elif r.value_type == 'float':
                typed_value = float(r.Value)
            elif r.value_type == 'str':
                typed_value = r.Value
            else:
                continue

            conf.set_attr(r['config_keys_path'], typed_value)

        for w in self.uis_manager.windows:
            w.file_explorer.vertical_scrollbar.update()
            w.file_explorer.horizontal_scrollbar.update()
        self.uis_manager.refresh_all_configurations()

    def new_folder(self):
        print("new_folder")

    def new_file(self):
        print("new_file")

    def save_action(self):
        print("save_action")

    def copy_action(self):
        print("copy_action")

    def paste_action(self):
        print("paste_action")

