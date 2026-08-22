import os
import shutil

import pandas as pd

from PySide6.QtWidgets import QMainWindow, QTableView, QAbstractItemView, QLabel, QFileDialog, \
    QMenu, QPushButton, QColorDialog, QVBoxLayout, QMenuBar, QWidget, \
    QScrollArea, QFrame, QStyledItemDelegate, QComboBox, QSpinBox, QDoubleSpinBox, \
    QDialogButtonBox, QStyle, QStyleOptionSpinBox
from PySide6 import QtCore
from PySide6.QtCore import Qt, QEvent, QPointF, QDir
from PySide6.QtGui import QIcon, QAction, QFontDatabase, QPixmap, QPainter, QPolygonF

from src.data_models import SimplePandasModel2
from src.shared.locations import ICONS_DIR, SYSTEM_DEFAULT_ICONS_DIR
from src.shared.vars import conf_manager as conf
from src.utils.utils import get_full_icon_path, is_legal_key_sequence
from src.utils.os_utils import copy_item, extract_extension_from_path, extract_filename_from_path
from src.ui_components.misc_widgets.shortcut_keys_configuration import KeyboardShortcutSelectorUi
from src.ui_components.misc_widgets.dialogs_and_messages import CustomQDialogButtonBox, \
    QDialogButtonsAndWidgets
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


class font_picker:
    def __init__(self, row: int, styles_tbl: QTableView):
        self.row = row
        self.styles_tbl = styles_tbl

    def __call__(self):
        file_dialog = QFileDialog(directory='/System/Library/Fonts/Supplemental')
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        # QDir.Hidden makes dot-folders and dot-files visible. Only settable on a dialog
        # instance - the static getOpenFileName helper used before had no way to pass a filter.
        file_dialog.setFilter(file_dialog.filter() | QDir.Filter.Hidden)
        if not (file_dialog.exec() and file_dialog.selectedFiles()):
            return
        path = file_dialog.selectedFiles()[0]
        if extract_extension_from_path(path).lower() not in ['ttf', 'ttc', 'otf']:
            return

        # Read the font's real family name (and, if new, make it usable this session).
        existing_families = set(QFontDatabase.families())
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id == -1:
            return  # unreadable / not a valid font file
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            return
        family = families[0]

        already_installed = family in existing_families
        if not already_installed:
            # Ask consent, then install to ~/Library/Fonts so it's a permanent system font.
            msg_box = CustomQDialogButtonBox(
                "Install font",
                f"'{family}' isn't installed on your Mac.\n\n"
                f"Install it to your user Fonts folder so you can use it? "
                f"It will be available immediately.")
            if msg_box.exec() != 1:          # user declined -> keep current font
                QFontDatabase.removeApplicationFont(font_id)
                return
            fonts_dir = os.path.expanduser("~/Library/Fonts")
            os.makedirs(fonts_dir, exist_ok=True)
            dest = os.path.join(fonts_dir, os.path.basename(path))
            if not os.path.exists(dest):
                shutil.copy2(path, dest)
            # font_id (from `path`) stays registered -> usable in this session already.

        self.styles_tbl.model().setData(self.styles_tbl.model().index(self.row, 2),
                                        family, Qt.ItemDataRole.EditRole)


MAX_ICON_FILE_SIZE_BYTES = 100 * 1024


def invalid_icon_reason(path: str):
    """Why `path` can't be used as an icon, or None if it can."""
    if extract_extension_from_path(path).lower() != 'png':
        return f"'{os.path.basename(path)}' is not a PNG file."
    if os.path.getsize(path) > MAX_ICON_FILE_SIZE_BYTES:
        return (f"'{os.path.basename(path)}' is "
                f"{os.path.getsize(path) // 1024} KB - the limit is "
                f"{MAX_ICON_FILE_SIZE_BYTES // 1024} KB.")
    if QPixmap(path).isNull():
        return f"'{os.path.basename(path)}' could not be read as an image."
    return None


# Config key -> the filename prefix given to the copy placed in results/icons. Each picker
# gets its own prefix so one row's pick can never overwrite another's.
ICON_PICKER_DEST_PREFIXES = {'FOLDER_ICON_NAME': 'folder_', 'FAVORITES_ICON': 'bookmarks_',
                            'DRAGGED_ITEM_ICON': 'dragged_'}


class icon_picker:
    """Value picker for the icon rows ("Folder icon", "Bookmarks title icon"): copies the chosen PNG
    into results/icons and writes its name (without the extension) into the table, the same way
    LinksTable.change_icon does for a favorite's icon. Apply / OK then stores that name in the
    row's config key."""

    def __init__(self, row: int, styles_tbl: QTableView, dest_prefix: str = 'folder_',
                 button=None):
        self.row = row
        self.styles_tbl = styles_tbl
        self.dest_prefix = dest_prefix
        # The dialog button that opened this picker, so its preview icon can be updated in
        # place once a new icon has been chosen. None when there is no button to update.
        self.button = button

    def __call__(self):
        # Deliberately unfiltered by file type: an invalid pick has to be possible so the
        # user is told why.
        file_dialog = QFileDialog(directory=SYSTEM_DEFAULT_ICONS_DIR)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        # QDir.Hidden makes dot-folders and dot-files visible (icons often live in one,
        # e.g. ~/.icons). Only settable on a dialog instance - the static
        # getOpenFileName helper used before had no way to pass a filter.
        file_dialog.setFilter(file_dialog.filter() | QDir.Filter.Hidden)
        if file_dialog.exec() and file_dialog.selectedFiles():
            self.apply_selected_file(file_dialog.selectedFiles()[0])

    def apply_selected_file(self, path: str) -> bool:
        problem = invalid_icon_reason(path)
        if problem is None:
            # Prefixed so a pick can never overwrite _folder_.png or one of the generated
            # per-extension icons already sitting in results/icons.
            icon_name = self.dest_prefix + extract_filename_from_path(path, include_extension=False)
            dest_path = os.path.join(ICONS_DIR, icon_name + '.png')
            if copy_item(path, dest_path) > 0:
                self.styles_tbl.model().setData(self.styles_tbl.model().index(self.row, 2),
                                                icon_name, Qt.ItemDataRole.EditRole)
                if self.button is not None:
                    self.button.setIcon(QIcon(dest_path))
                return True
            problem = f"'{os.path.basename(path)}' could not be copied into the icons folder."

        CustomQDialogButtonBox(
            "Invalid icon",
            problem + f"\n\nPick a .png image up to {MAX_ICON_FILE_SIZE_BYTES // 1024} KB.",
            buttons=QDialogButtonBox.StandardButton.Ok).exec()
        return False


class numeric_value_changed:
    """Writes a numeric (up/down spin box) edit back into the styles table's model,
    the same way the picker buttons above write their picked value back."""

    def __init__(self, row: int, styles_tbl: QTableView):
        self.row = row
        self.styles_tbl = styles_tbl

    def __call__(self, value):
        self.styles_tbl.model().setData(self.styles_tbl.model().index(self.row, 2),
                                        value, Qt.ItemDataRole.EditRole)


class _IgnoreWheelMixin:
    """Spin boxes in the configure-styles list sit inside a scrollable table, where Qt's
    default of stepping the value on every wheel tick means scrolling the list silently
    edits a setting. Ignoring the event stops that, and (per QWidget::wheelEvent's
    contract) hands the tick to the table underneath so the list scrolls instead."""

    def wheelEvent(self, event):
        event.ignore()


class _BorderlessSpinBoxMixin:
    """Draws the spin box without its frame - only the up/down arrows are painted.

    The spin boxes sit inside the cells of the configure-styles table, where the stock
    frame puts a visible box around every numeric row. A style sheet can hide that frame,
    but any style sheet set on a QSpinBox takes the widget off the macOS style, and the
    up/down arrows are then not drawn at all - so the arrows are painted here by hand
    instead. Clicking and keyboard stepping are unaffected: only painting is replaced.
    """

    ARROW_WIDTH = 7
    ARROW_HEIGHT = 4

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The number itself is drawn by a QLineEdit child, which draws its own border and
        # focus ring on top of the cell - this clears both. Its background is left opaque
        # on purpose: a transparent one leaves the previously drawn digits in place, so
        # every repaint stacks another copy of the number on top of the old one.
        self.lineEdit().setStyleSheet("QLineEdit {border: none;}")

    def _arrow_polygon(self, center, points_up):
        half_width = self.ARROW_WIDTH / 2
        half_height = self.ARROW_HEIGHT / 2
        base_y = center.y() + (half_height if points_up else -half_height)
        tip_y = center.y() - (half_height if points_up else -half_height)
        return QPolygonF([QPointF(center.x() - half_width, base_y),
                          QPointF(center.x() + half_width, base_y),
                          QPointF(center.x(), tip_y)])

    def paintEvent(self, event):
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        painter = QPainter(self)
        # Nothing else paints the widget now that the frame is gone, so the background has
        # to be filled here - otherwise each repaint leaves the previous one showing through.
        painter.fillRect(self.rect(), self.palette().brush(self.backgroundRole()))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for sub_control, points_up in ((QStyle.SubControl.SC_SpinBoxUp, True),
                                       (QStyle.SubControl.SC_SpinBoxDown, False)):
            arrow_rect = self.style().subControlRect(QStyle.ComplexControl.CC_SpinBox,
                                                     option, sub_control, self)
            is_pressed = bool(option.activeSubControls & sub_control) and \
                bool(option.state & QStyle.StateFlag.State_Sunken)
            painter.setBrush(self.palette().highlight() if is_pressed else self.palette().text())
            painter.drawPolygon(self._arrow_polygon(arrow_rect.center(), points_up))


class NoWheelSpinBox(_IgnoreWheelMixin, _BorderlessSpinBoxMixin, QSpinBox):
    pass


class NoWheelDoubleSpinBox(_IgnoreWheelMixin, _BorderlessSpinBoxMixin, QDoubleSpinBox):
    pass


class ConfigDropdownDelegate(QStyledItemDelegate):
    """Item delegate for the "Value" column of the configure-styles table: cells for
    known fixed-choice settings edit via a dropdown instead of a free-text line edit.
    Other cells fall back to the default text editor.

    - Any cell whose current value is exactly 'Y' or 'N' gets a Y/N dropdown.
    - The "Multiselect modifier key" row gets a command/control/option/shift dropdown.
    - The "Date format" row gets a dropdown of the supported strftime formats.
    """

    MODIFIER_KEY_CHOICES = ['command', 'control', 'option', 'shift']
    # Abbreviations MULTISELECT_MODIFIER also accepts (see MULTISELECT_MODIFIER_MAP
    # in file_explorer_table.py), normalized to their canonical dropdown entry.
    MODIFIER_KEY_ABBREVIATIONS = {'cmd': 'command', 'ctrl': 'control', 'alt': 'option'}

    DATE_FORMAT_CHOICES = ["%Y/%m/%d %H:%M",
                           "%Y-%m-%d %H:%M",
                           "%Y/%m/%d %H:%M:%S",
                           "%Y-%m-%d %H:%M:%S"]

    def _row_kind(self, index):
        feature = str(index.model().index(index.row(), 1).data(Qt.ItemDataRole.EditRole)).lower()
        if 'multiselect modifier' in feature:
            return 'modifier'
        if feature == 'date format':
            return 'date_format'
        if str(index.data(Qt.ItemDataRole.EditRole)) in ('Y', 'N'):
            return 'yes_no'
        return None

    def _choices_for_kind(self, kind):
        return {'modifier': self.MODIFIER_KEY_CHOICES,
               'date_format': self.DATE_FORMAT_CHOICES,
               'yes_no': ['Y', 'N']}[kind]

    def createEditor(self, parent, option, index):
        kind = self._row_kind(index)
        if kind is not None:
            combo = QComboBox(parent)
            combo.addItems(self._choices_for_kind(kind))
            # Commit & close as soon as a value is picked, rather than waiting for
            # the editor to lose focus.
            combo.currentIndexChanged.connect(lambda _: self.commitData.emit(combo))
            combo.currentIndexChanged.connect(lambda _: self.closeEditor.emit(combo))
            return combo
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        if isinstance(editor, QComboBox):
            current = str(index.data(Qt.ItemDataRole.EditRole))
            if self._row_kind(index) == 'modifier':
                current = self.MODIFIER_KEY_ABBREVIATIONS.get(current.lower(), current.lower())
            found = editor.findText(current)
            editor.setCurrentIndex(found if found >= 0 else 0)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)


# Create the menu bar
def populate_menubar_and_connect_triggers(ui_obj: QMainWindow, menubar_manager):

    ui_obj.menu_bar = ui_obj.menuBar()

    # Add a file menu (intentionally empty - no actions)
    ui_obj.file_menu = QMenu("File", ui_obj)
    ui_obj.menu_bar.addMenu(ui_obj.file_menu)

    # Add an edit menu (titled "Configure" rather than "Edit" so macOS doesn't
    # auto-inject its standard Edit-menu items, e.g. "Autofill", into it)
    ui_obj.edit_menu = ui_obj.menu_bar.addMenu("Configure")

    # Add actions to the edit menu
    ui_obj.configure_keyboard_shortcuts_action = QAction("Keyboard shortcuts", ui_obj)
    ui_obj.configure_styles_action = QAction("Edit configurations", ui_obj)
    ui_obj.show_hide_left_pane = QAction("Show / Hide left pane", ui_obj)
    # ui_obj.zoom_action = QAction("Zoom", ui_obj)

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
            # Restore the width it had right before it was last hidden.
            conf.set_attr('LEFT_PANE_WIDTH', conf.LEFT_PANE_WIDTH_BEFORE_HIDE)
        else:
            # Remember the current width so it can be restored later, then hide.
            conf.set_attr('LEFT_PANE_WIDTH_BEFORE_HIDE', conf.LEFT_PANE_WIDTH)
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
        # Keep the shortcuts list a bounded height and scroll through the rest, so the
        # window opens short instead of as tall as all ~26 action rows combined.
        self.shortcuts_scroll_area = QScrollArea()
        self.shortcuts_scroll_area.setWidgetResizable(True)
        self.shortcuts_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.shortcuts_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.shortcuts_scroll_area.setWidget(self.shortcuts_selection_widget)

        self.overall_layout.addWidget(user_explanation)
        self.overall_layout.addWidget(self.shortcuts_scroll_area, 1)
        self.overall_layout.addWidget(self.dialog)
        self.main_widget = QWidget()
        self.main_widget.setLayout(self.overall_layout)

        self.keymap_window = QMainWindow()
        self._keymap_window_install_event_filter = CloseOnEscapeEventFilter(self.keymap_window)
        self.keymap_window.installEventFilter(self._keymap_window_install_event_filter)
        self.keymap_window.resize(800, 560)
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
        self.styles_value_delegate = ConfigDropdownDelegate(self.styles_table)
        self.styles_table.setItemDelegateForColumn(2, self.styles_value_delegate)
        self.styles_table.hideColumn(0)
        self.styles_table.hideColumn(3)
        self.styles_table.setColumnWidth(1, 400)
        self.styles_table.setColumnWidth(2, 200)
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
            elif self.config_data.loc[i, 'Feature'] == 'Font':
                btn.setIcon(QIcon(get_full_icon_path('_font_picker_')))
                btn.clicked.connect(font_picker(i, self.styles_table))
            elif self.config_data.loc[i, 'config_keys_path'][-1] in ICON_PICKER_DEST_PREFIXES:
                config_key = self.config_data.loc[i, 'config_keys_path'][-1]
                # The button itself shows the icon currently in use
                btn.setIcon(QIcon(get_full_icon_path(str(self.config_data.iloc[i, 2])) or ''))
                btn.clicked.connect(icon_picker(i, self.styles_table,
                                                dest_prefix=ICON_PICKER_DEST_PREFIXES[config_key],
                                                button=btn))
            else:
                continue
            self.style_selection_buttons[i] = btn
            self.styles_table.setIndexWidget(self.styles_table.model().index(i, 4), btn)

        # Numeric settings get an up/down spin box in the Value cell itself, so they
        # can still be typed into directly as well as stepped with the arrows.
        self.style_numeric_spinboxes = {}
        for i in range(self.config_data.shape[0]):
            value_type = self.config_data.loc[i, 'value_type']
            if value_type not in ('int', 'float'):
                continue
            spin = NoWheelSpinBox() if value_type == 'int' else NoWheelDoubleSpinBox()
            spin.setMinimum(0)  # Values below 0 are not allowed
            spin.setMaximum(999999)
            spin.setValue(self.config_data.iloc[i, 2])
            spin.valueChanged.connect(numeric_value_changed(i, self.styles_table))
            self.style_numeric_spinboxes[i] = spin
            self.styles_table.setIndexWidget(self.styles_table.model().index(i, 2), spin)

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
            for t in w.all_tables():
                t.vertical_scrollbar.update()
                t.horizontal_scrollbar.update()
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

