import os.path
from typing import Union
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, QSize, QEvent
from PySide6.QtGui import QFont, QIcon, QPixmap, QAction
from PySide6.QtWidgets import (QAbstractItemView, QVBoxLayout, QLabel, QLineEdit, QStackedWidget,
                               QSizePolicy, QHBoxLayout, QSplitter, QMenu, QWidget, QPushButton)

from src.ui_components.misc_widgets.search_box_window import SearchWindow_threaded
from src.ui_components.misc_widgets.links_table import LinksTable
from src.ui_components.misc_widgets.tree_file_explorer import TreeFileExplorer
from src.ui_components.misc_widgets.misc_widgets import CustomSizeQSplitter, CustomSizeQToolBar
from src.ui_components.misc_widgets.menu_bar import MebuBarManager
from src.shared.vars import conf_manager as conf, logger as logger

from src.utils.os_utils import get_last_part_in_path, list_all_subpaths_in_path, dir_
from src.data_models import PandasModel
from src.utils.utils import get_full_icon_path
from src.ui_components.file_explorer_table import FileExplorerTable

class TextboxNavigator(CustomSizeQToolBar):
    """
    This is the (seeming) textbox which displays the current path and allows the
    user to change it by clicking on any part of the path
    """

    class change_table_path:
        def __init__(self, path, change_path_method):
            self.path = path
            self.change_path_method = change_path_method

        def __call__(self):
            self.change_path_method(self.path, reset_path_history=False)

    def __init__(self,
                 encompassing_obj,
                 method_when_clicked_on_path_btn,
                 method_when_clicked_on_empty_area,
                 default_height=200):
        super().__init__(default_height=default_height)
        self.encompassing_obj = encompassing_obj
        self.method_when_clicked_on_path_btn = method_when_clicked_on_path_btn
        self.method_when_clicked_on_empty_area = method_when_clicked_on_empty_area
        self.default_height = default_height
        self.setStyleSheet(conf.TEXTBOX_NAVIGATOR_STYLE)
        logger.info("ui.TextboxNavigator - finished initializing")

    def update_fonts(self):
        if hasattr(self, 'toolbar_buttons'):
            for btn in self.toolbar_buttons:
                set_object_font(btn, font_size=int(conf.TEXTBOX_FONT_SIZE),
                                font_family=conf.TEXT_FONT)

    def update_path(self, path):
        self.clear_path()
        self.add_navigation_buttons_to_toolbar(path)
        
    def clear_path(self):
        if len(self.children()) == 0:
            return
        i = 0
        while i < len(self.children()):
            child = self.children()[i]
            if str(type(child).__name__) in ["QPushButton", "QLabel", "QPixmap"]:
                child.setParent(QWidget())
            else:
                i += 1

    def add_navigation_buttons_to_toolbar(self, path):
        buttons = []
        folders_in_path = list_all_subpaths_in_path(path)
        folders_in_path.append('')
        num_paths = len(folders_in_path)
        icon = QtGui.QIcon(get_full_icon_path(conf.RIGHT_ARROWHEAD_ICON_NAME))
        self.toolbar_buttons = []
        self.concat_separator_symbol(icon)
        for i, p in enumerate(folders_in_path):
            name = get_last_part_in_path(p)
            button = QPushButton(name, self)
            if i < num_paths-1:
                button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
                buttons.append(button)
                buttons[i].clicked.connect(
                    self.change_table_path(p, self.method_when_clicked_on_path_btn))
                buttons[i].setStyleSheet(conf.TEXTBOX_NAVIGATOR_BUTTON_STYLE)
                set_object_font(buttons[i], font_size=int(conf.TEXTBOX_FONT_SIZE),
                                font_family=conf.TEXT_FONT)
            else:
                # 'QSizePolicy.Policy.Expanding' makes it take up all the remaining space
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                buttons.append(button)
                buttons[i].pressed.connect(self.method_when_clicked_on_empty_area)  # pressed is similar to connect, but it doesn't wait until the mouse is released
                buttons[i].setStyleSheet(conf.TRANSPARENT_QBUTTON)
            self.addWidget(buttons[i])

            if i < num_paths-2:
                self.concat_separator_symbol(icon)

        self.toolbar_buttons = buttons

    def concat_separator_symbol(self, sep: Union[str, QIcon]):
        if isinstance(sep, str):
            label = QLabel(sep)
            self.addWidget(label)
        elif isinstance(sep, QIcon):
            icn = QLabel()
            icn.setPixmap(sep.pixmap(20))  # Set the path to your icon
            icn.setStyleSheet("padding: 5px")
            self.addWidget(icn)


def set_object_font(obj, font_family=None, font_size=None):
    font = obj.font()
    if font_family is not None:
        font.setFamily(font_family)
    if font_size is not None:
        font.setPointSize(font_size)
    obj.setFont(font)


# https://icons8.com/icons/set/arrow
def create_pushbutton(parent, icon_path: str,
                      text: str = '', status_tip: str = '',
                      width: int = 35, height: int = 35,
                      when_triggered=lambda x: print('Button clicked')):
    icon = QIcon()
    icon.addFile(icon_path)
    pushbutton = QPushButton(icon=QIcon(icon_path), text=text, parent=parent)
    pushbutton.setStyleSheet("QPushButton{background-color : transparent; border: none}"
                             "QPushButton::pressed{background-color : lightgrey;}")
    pushbutton.setStatusTip(status_tip)
    pushbutton.clicked.connect(when_triggered)
    pushbutton.setIconSize(QSize(width, height))
    return pushbutton


# https://icons8.com/icons/set/arrow
def create_action(parent, icon_path: str,
                  text: str = '', status_tip: str = '',
                  when_triggered=lambda x: print('Button clicked')):
    icon = QIcon()
    icon.addFile(icon_path)
    button_action = QAction(icon, text, parent)
    button_action.setStatusTip(status_tip)
    button_action.triggered.connect(when_triggered)
    return button_action


def create_textbox(parent):
    textbox = QLineEdit(parent)
    textbox.setText(conf.DEFAULT_PATH)
    textbox.setFont(QFont(conf.TEXT_FONT, conf.TEXTBOX_FONT_SIZE))
    textbox.setStyleSheet(conf.TEXTBOX_STYLE)
    return textbox


def create_toolbar(parent, w: Union[int, None] = None, h: Union[int, None] = None,
                   icon_width: int = 16, icon_height: int = 16):
    toolbar = CustomSizeQToolBar(parent, w, h)
    toolbar.setIconSize(QtCore.QSize(icon_width, icon_height))
    toolbar.setStyleSheet(conf.TOOLBAR_STYLE)
    return toolbar


class ui(QtWidgets.QMainWindow):

    def __init__(self, encompassing_uis_manager, root_dir_path,
                 height, file_explorer_width, left_pane_width,
                 columns_ordering_scheme=None, parent=None):
        super().__init__(parent)
        logger.info("ui initialization")
        self.file_explorer_width = file_explorer_width
        self.left_pane_width = left_pane_width
        self.height = height

        self._allow_structure_updates = False

        self.encompassing_uis_manager = encompassing_uis_manager
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setStyleSheet("""QSplitter{border:  1px solid blue;}""")

        logger.info("ui.configure_splitter")
        self.configure_splitter()

        """
         Top area: toolar + stacked_widget (containing both textbox-navigator and textbox)
        """
        logger.info("ui - init top area")
        self.generate_top_toolbar()
        self.generate_textbox_navigator()

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.textbox_navigator)
        self.stacked_widget.addWidget(self.textbox)
        self.toolbar.addWidget(self.stacked_widget)

        self.subsplitter = QSplitter(Qt.Orientation.Horizontal, parent=self.splitter)

        # setSizePolicy
        self.subsplitter.splitterMoved.connect(self.update_structure)

        # Create a vertical line separating the subsplitter from the rest of the splitter
        self.subsplitter.setHandleWidth(0)
        self.subsplitter.setStyleSheet(
            """QSplitter::handle:vertical{background-color: lightgrey; height: 0px;}""")


        """
         Left pane: Favorites + Tree
        """
        logger.info("ui - init left pane")
        hght = conf.WINDOW_HEIGHT - (conf.TOP_TOOLBAR_HEIGHT + conf.BOTTOM_TOOLBAR_HEIGHT)
        self.trees_subsplitter = \
            CustomSizeQSplitter(type=Qt.Orientation.Vertical, parent=self.subsplitter,
                                default_height=hght)
        self.trees_subsplitter.setStyleSheet(
            """QSplitter{background-color : """ + conf.LEFT_PANE_BACKGROUND_COLOR + """;}""")

        self.generate_favorites_area()
        self.favorites_area = QVBoxLayout(self.trees_subsplitter)
        if conf.SHOW_FAVORITES_TITLE:
            self.favorites_area.addWidget(self.favs_table_view_header)
        else:
            self.empty_widget = QWidget()
            self.empty_widget.setFixedHeight(25)
            self.favorites_area.addWidget(self.empty_widget)
        self.favorites_area.addLayout(self.favs_table_view_layout)
        self.favorites_area.addStretch(1)

        self.tree_area = QVBoxLayout(self.trees_subsplitter)
        # self.tree_area = QVBoxLayout()
        self.tree = TreeFileExplorer(parent=self.trees_subsplitter, encompassing_ui=self)
        self.tree.expandAll()
        self.tree_area.addWidget(self.tree)


        """
         Right pane: File explorer
        """
        logger.info("ui - init right pane")
        self.file_explorer_layout = QVBoxLayout(self.subsplitter)
        self.pandasModel = PandasModel(datapath=root_dir_path,
                                       columns_ordering_scheme=columns_ordering_scheme)
        hght = height-(conf.TOP_TOOLBAR_HEIGHT + conf.BOTTOM_TOOLBAR_HEIGHT)
        self.file_explorer = FileExplorerTable(self.pandasModel, parent=self.subsplitter,
                                               root_dir_path=root_dir_path,
                                               xdim=file_explorer_width,
                                               ydim=hght, encompassing_ui=self)
        self.file_explorer_layout.addWidget(self.file_explorer)



        """
         Bottom area: bottom toolbar
        """
        logger.info("ui - init bottom area")
        self.generate_bottom_toolbar()
        self.config_bottom_toolbar_text_and_dims()


        self.textbox_navigator.update_path(self.path)

        self.setAcceptDrops(True)
        self.splitter.setAcceptDrops(True)
        self.subsplitter.setAcceptDrops(True)
        self.file_explorer.viewport().setAcceptDrops(True)

        self.installEventFilter(self)

        self.setCentralWidget(self.splitter)

        logger.info("ui - setting dimensions")
        self.subsplitter.setStretchFactor(left_pane_width/file_explorer_width, 1)
        self.trees_subsplitter.resize(self.trees_subsplitter.sizeHint())
        self.file_explorer.resize(self.file_explorer.sizeHint())
        self.file_explorer.setFocus()

        # Must come in the end (otherwise may be overridden)
        self.set_ui_sizes()

        logger.info("ui - initialization finished")

        # Moved here (UI object) for Sequoia 15.3:
        self.menubar_manager = MebuBarManager(self)  # Takes care of menu bar requests
        logger.info("Starting app - populate_menubar_and_connect_triggers")



    @property
    def path(self):
        return self.file_explorer.path

    def change_path(self, newpath: str, reset_path_history: bool = True):
        self.file_explorer.change_path(newpath, reset_path_history=reset_path_history)

    def sizeHint(self):
        return QSize(self.left_pane_width + self.file_explorer_width + 50, self.height)

    def configure_splitter(self):
        self.splitter.setWindowTitle(get_last_part_in_path(conf.DEFAULT_PATH))
        # Take care of the horizontal lines separating the different widgets within the subsplitter
        self.splitter.setHandleWidth(5)  # The gap size between the textbox and the table
        self.splitter.setStyleSheet(conf.GAP_BETWEEN_TOOLBAR_AND_BELOW_STYLE)

    def generate_top_toolbar(self):
        self.toolbar = create_toolbar(parent=self.splitter)
        # Buttons (can appear stand-alone, in a menubar, etc...)
        up_button = create_action(self, icon_path=get_full_icon_path(conf.UP_ICON_NAME),
                                  when_triggered=self.go_to_parent_dir)
        # Push-buttons
        back_pushbutton    = create_pushbutton(self, icon_path=get_full_icon_path(conf.BACKWARD_ICON_NAME), width=20, height=20, when_triggered=self.go_to_previous_path)
        self.down_button   = create_pushbutton(self, icon_path=get_full_icon_path(conf.DOWN_ICON_NAME), when_triggered=self.show_browsing_history)
        forward_pushbutton = create_pushbutton(self, icon_path=get_full_icon_path(conf.FORWARD_ICON_NAME), width=20, height=20, when_triggered=self.go_to_next_path)

        self.toolbar.addWidget(back_pushbutton)
        self.toolbar.addWidget(forward_pushbutton)
        self.toolbar.addWidget(self.down_button)
        self.toolbar.addAction(up_button)


    def generate_textbox_navigator(self):
        self.textbox = create_textbox(self.toolbar)
        self._textbox_event_filter = self.textboxEventFilter(self)   # Custom event class (pt. 1)
        self.textbox.installEventFilter(self._textbox_event_filter)  # Custom event class (pt. 1)

        self.textbox_navigator = \
            TextboxNavigator(encompassing_obj=self,
                             method_when_clicked_on_path_btn=self.change_path,
                             method_when_clicked_on_empty_area=self.expose_input_textbox,
                             default_height=conf.TOP_TOOLBAR_HEIGHT)

        self.config_upper_toolbar_text_and_dims()
        # Behind the textbox navigator there's an actual textbox


    def config_upper_toolbar_text_and_dims(self):
        set_object_font(self.textbox, font_size=int(conf.TEXTBOX_FONT_SIZE),
                        font_family=conf.TEXT_FONT)
        fm = self.textbox.fontMetrics()
        height = conf.TEXTBOX_FONT_SIZE
        self.toolbar.setFixedHeight(height + 28)
        self.textbox_navigator.setFixedHeight(height + 20)
        self.textbox.setFixedHeight(height + 20)
        self.textbox_navigator.update_fonts()


    def config_bottom_toolbar_text_and_dims(self):
        set_object_font(self.bottom_label, font_size=int(conf.BOTTOM_TEXT_FONT_SIZE),
                        font_family=conf.TEXT_FONT)
        fm = self.textbox.fontMetrics()
        height = conf.BOTTOM_TEXT_FONT_SIZE
        self.bottom_toolbar.setFixedHeight(height + 12)


    def generate_favorites_area(self):
        # The "Bookmarks" row
        if conf.SHOW_FAVORITES_TITLE:
            self.favs_table_view_header = LinksTable({"Name": [conf.FAVORITES_TITLE],
                                                      "Path": [None],
                                                      "icon_full_path": [get_full_icon_path("_quick_access_")]},
                                                      row_height=conf.FAVORITES_ROW_HEIGHT + 12)
            self.favs_table_view_header.setStyleSheet(conf.FAVORITES_TABLE_STYLE)
            self.favs_table_view_header.setFixedHeight(int(round(self.favs_table_view_header.rowHeight(0), 0)))
            self.favs_table_view_header.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        # The actual favorites table
        self.favs_table_view_layout = QHBoxLayout()
        self.favs_table_view = LinksTable(conf.BASIC_FAVORITES_DICT,
                                          row_height=conf.FAVORITES_ROW_HEIGHT,
                                          spacer_column_indent=4)
        self.favs_table_view.setStyleSheet(conf.FAVORITES_TABLE_STYLE)
        num_rows = min([5, self.favs_table_view.table.rowCount(0)])
        max_hght = int(round(num_rows * self.favs_table_view.rowHeight(0) * 3.0, 0))
        self.favs_table_view.setMaximumHeight(max_hght)
        # NOTE: replacing setMaximumHeight wih setFixedHeight will keep all look the same, but
        # then the tree below self.favs_table_view will not be able to expand and collapse. It
        # will only be able to expand in one step, completely covering the self.favs_table_view
        # widget
        self.favs_table_view.clicked.connect(self.favs_table_clicked)
        self.favs_table_view_layout.addWidget(self.favs_table_view)


    def generate_bottom_toolbar(self):
        self.bottom_toolbar = create_toolbar(parent=self.splitter, h=conf.BOTTOM_TOOLBAR_HEIGHT)
        self.bottom_toolbar.setStyleSheet(conf.BOTTOM_TOOLBAR_STYLE)
        self.bottom_label = QLabel('')
        self.bottom_label.setWordWrap(True)
        self.bottom_label.setFixedHeight(conf.BOTTOM_TEXT_FONT_SIZE)
        self.bottom_label.setStyleSheet(conf.BOTTOM_TOOLBAR_TEXT_STYLE)  # Top, Right, Bottom, Left
        self.bottom_toolbar.addWidget(self.bottom_label)

    def reload_keyboard_shortcuts(self):
        self.file_explorer.initialize_all_key_sequences()

    def dragEnterEvent(self, event):
        # Accept the drag if the event contains text
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if type(event.source()).__name__ == "LinksTable":
            event.ignore()
            return
        # Handle the drop event
        if event.mimeData().hasText():
            item_text = event.mimeData().text()
            self.list_widget.addItem(item_text)
            event.accept()
        else:
            event.ignore()


    def closeEvent(self, a0):
        self.on_close()
        super(ui, self).closeEvent(a0)


    def eventFilter(self, source, event):
        qtype = event.type()
        if (qtype == QtCore.QEvent.Type.Resize):
            self.update_structure()
        return super().eventFilter(source, event)


    def update_structure(self):
        self.file_explorer.adapt_width_of_last_column()
        self.update_structure_in_config()

    def path_changed(self, new_path: str, reset_tree_selection: bool):
        if reset_tree_selection:
            self.tree.clearSelection()
        self.textbox.setText(new_path)
        self.textbox_navigator.update_path(new_path)
        self.splitter.setWindowTitle(get_last_part_in_path(new_path))
        self.refresh_bottom_toolbar_text()

    def refresh_bottom_toolbar_text(self, num_items_selected: int = None,
                                    size_of_items_selected: int = None):
        if num_items_selected is None:
            self.bottom_label.setText('')
        else:
            if num_items_selected == 1:
                items_str = ' item,  '
            else:
                items_str = ' items,  '
            self.bottom_label.setText(str(num_items_selected) + items_str + size_of_items_selected)


    def expose_input_textbox(self):
        self.textbox.selectAll()
        self.stacked_widget.setCurrentWidget(self.textbox)
        self.textbox.setFocus()

    def hide_input_textbox(self):
        self.textbox.setText(self.path)
        self.stacked_widget.setCurrentWidget(self.textbox_navigator)


    class textboxEventFilter(QtCore.QObject):
        def __init__(self, encompassing_ui):
            super().__init__()
            self.encompassing_ui = encompassing_ui

        def eventFilter(self, source, event):
            if (event.type() == QEvent.Type.KeyPress):
                if (event.key() == Qt.Key.Key_Escape):
                    self.encompassing_ui.hide_input_textbox()
                elif (event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return):
                    if os.path.exists(self.encompassing_ui.textbox.text()):
                        try:
                            self.encompassing_ui.change_path(self.encompassing_ui.textbox.text())
                            self.encompassing_ui.hide_input_textbox()
                        except:
                            pass
            elif event.type() == QtCore.QEvent.Type.FocusOut:
                self.encompassing_ui.hide_input_textbox()

            return super().eventFilter(source, event)

    def show_browsing_history(self):
        logger.info("ui.show_browsing_history")
        self.history_list_widget = QMenu(self)
        self.history_links = []
        for i, p in enumerate(self.file_explorer.browsing_history_manager.paths[1:]):
            self.history_links.append(QAction(text=p, parent=self))
            self.history_links[i].triggered.connect(
                lambda checked, path=p: self.selected_path_from_browsing_history(path)
            )
            self.history_list_widget.addAction(self.history_links[i])
        pos = self.down_button.mapToGlobal(self.down_button.rect().bottomLeft())
        self.history_list_widget.exec(pos)

    def selected_path_from_browsing_history(self, path: str):
        logger.info(">> ui.selected_path_from_browsing_history")
        self.change_path(path, reset_path_history=False)

    def go_to_parent_dir(self):
        self.file_explorer.go_to_parent_dir()

    def go_to_previous_path(self):
        self.file_explorer.go_to_previous_path()

    def go_to_next_path(self):
        self.file_explorer.go_to_next_path()

    def create_new_dir(self):
        self.file_explorer.create_new_dir()

    def on_selectionChanged(self, selected, deselected):
        self.file_explorer.on_selectionChanged(selected, deselected)

    def favs_table_clicked(self, index):
        logger.info(">> ui.favs_table_clicked")
        self.favs_table_view.clearSelection()
        target_path = self.favs_table_view.path_at_row(index.row())
        self.change_path(target_path, reset_path_history=False)

    def launch_search_window(self):
        logger.info("ui.launch_search_window")
        self.search_window = SearchWindow_threaded(self.path, self)
        self.search_window.show()

    def set_ui_sizes(self):
        self.resize(conf.LEFT_PANE_WIDTH+conf.FILE_EXPLORER_WIDTH, conf.WINDOW_HEIGHT)
        self.subsplitter.setSizes([conf.LEFT_PANE_WIDTH, conf.FILE_EXPLORER_WIDTH])
        # If user resizes the entire window, the left pane will not be resized:
        self.subsplitter.setStretchFactor(0, 0)
        self.subsplitter.setStretchFactor(1, 1)

    def refresh_all_configurations(self):
        logger.info("ui.refresh_all_configurations")
        if conf.SHOW_FAVORITES_TITLE:
            self.favs_table_view_header.setStyleSheet(conf.FAVORITES_TABLE_STYLE)
        self.favs_table_view.setStyleSheet(conf.FAVORITES_TABLE_STYLE)
        self.toolbar.setStyleSheet(conf.TOOLBAR_STYLE)
        self.textbox.setStyleSheet(conf.TEXTBOX_STYLE)
        self.textbox_navigator.setStyleSheet(conf.TEXTBOX_NAVIGATOR_STYLE)
        self.tree.setStyleSheet(conf.TREE_STYLE)
        for btn in self.textbox_navigator.toolbar_buttons:
            btn.setStyleSheet(conf.TEXTBOX_NAVIGATOR_BUTTON_STYLE)
        self.bottom_toolbar.setStyleSheet(conf.BOTTOM_TOOLBAR_STYLE)
        self.bottom_label.setMaximumHeight(conf.BOTTOM_TEXT_FONT_SIZE)
        self.bottom_label.setStyleSheet(conf.BOTTOM_TOOLBAR_TEXT_STYLE)  # Top, Right, Bottom, Left
        self.file_explorer.refresh_all_configurations()

    def update_structure_in_config(self):
        logger.info("ui.update_structure_in_config")
        if self._allow_structure_updates:
            conf.set_attr("WINDOW_HEIGHT", self.splitter.height())
            conf.set_attr("FILE_EXPLORER_WIDTH", self.file_explorer.width())
            conf.set_attr("LEFT_PANE_WIDTH", self.subsplitter.sizes()[0])
            conf.set_attr("BOTTOM_TOOLBAR_HEIGHT", self.bottom_toolbar.height())
            conf.set_attr("FILE_EXPLORER_COL_WIDTH_1", self.file_explorer.columnWidth(0))
            conf.set_attr("FILE_EXPLORER_COL_WIDTH_2", self.file_explorer.columnWidth(1))
            conf.set_attr("FILE_EXPLORER_COL_WIDTH_3", self.file_explorer.columnWidth(2))
            conf.set_attr("FILE_EXPLORER_COL_WIDTH_4", self.file_explorer.columnWidth(3))

    def on_close(self):
        self.encompassing_uis_manager.on_ui_close(self)

    def keyPressEvent(self, e):
        self.file_explorer.keyPressEvent(e)
