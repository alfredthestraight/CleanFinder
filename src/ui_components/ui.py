import os.path
from typing import Union
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, QSize, QEvent
from PySide6.QtGui import QFont, QIcon, QPixmap, QAction, QShortcut, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QVBoxLayout, QLabel, QLineEdit, QStackedWidget,
                               QSizePolicy, QHBoxLayout, QSplitter, QMenu, QWidget, QPushButton)

from src.ui_components.misc_widgets.search_box_window import SearchWindow_threaded
from src.ui_components.misc_widgets.links_table import LinksTable
from src.ui_components.misc_widgets.tree_file_explorer import TreeFileExplorer
from src.ui_components.misc_widgets.misc_widgets import CustomSizeQSplitter, CustomSizeQToolBar
from src.ui_components.misc_widgets.menu_bar import MebuBarManager
from src.ui_components.misc_widgets.dialogs_and_messages import prompt_message
from src.shared.vars import conf_manager as conf, logger as logger

from src.utils.os_utils import get_last_part_in_path, list_all_subpaths_in_path, dir_, \
    is_reachable_path, resolve_typed_path
from src.data_models import PandasModel
from src.utils.utils import get_full_icon_path, create_qaction_key_sequence, enable_home_end_keys
from src.utils.file_explorer_utils import map_shortcut_name_to_func
from src.ui_components.file_explorer_table import FileExplorerTable


# Shown at the left end of the breadcrumb when the path is too long to fit and its first
# components had to be dropped - so a shortened path never looks like the whole path.
TRUNCATION_MARKER_TEXT = "\u2026"   # a single-character ellipsis


class ShrinkablePathButton(QPushButton):
    """The deepest breadcrumb button, which shortens its own text rather than disappearing.

    QToolBar lays every item out at its sizeHint and moves whatever doesn't fit into an
    overflow popup - it never squeezes an item, so a smaller minimum width changes nothing.
    In a pane too narrow even for the current folder's name that would leave the breadcrumb
    completely empty. Eliding the text shrinks the sizeHint itself, so the folder the user
    is in stays on screen, shortened as far as it has to be.
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.full_text = text

    def _chrome_width(self) -> int:
        # What the style adds around the text: padding, border, margins.
        return max(0, super().sizeHint().width()
                   - self.fontMetrics().horizontalAdvance(self.text()))

    def restore_full_text(self):
        if self.text() != self.full_text:
            self.setText(self.full_text)
            self.updateGeometry()

    def fit_text_to(self, available: int):
        """Elide the folder name to `available` pixels, or restore it if it now fits."""
        metrics = self.fontMetrics()
        room = available - self._chrome_width()
        if room >= metrics.horizontalAdvance(self.full_text):
            self.restore_full_text()
            return
        elided = metrics.elidedText(self.full_text, Qt.TextElideMode.ElideRight,
                                    max(0, room))
        if elided != self.text():
            self.setText(elided)
            self.updateGeometry()


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

    def mousePressEvent(self, event):
        """
        Treats the toolbar's own padding as empty area. The path buttons only occupy a
        short, vertically-centered strip, so the space above/below them (and the margin
        inside the border) used to swallow clicks; now it behaves like clicking past the
        last button. The path buttons consume their own presses so they never reach here,
        and the separator QLabels don't accept mouse events, so clicks on them propagate
        up to this handler. Fires on press rather than release, to match the expanding
        empty-area button which is wired to `pressed`.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.method_when_clicked_on_empty_area()
            event.accept()
            return
        super().mousePressEvent(event)

    def update_fonts(self):
        if hasattr(self, 'toolbar_buttons'):
            for btn in self.toolbar_buttons:
                set_object_font(btn, font_size=int(conf.TEXTBOX_FONT_SIZE),
                                font_family=conf.TEXT_FONT)
            # A different font size changes every button's width, so what fits changes too.
            self._fit_path_to_width()

    def update_path(self, path):
        self.clear_path()
        self.add_navigation_buttons_to_toolbar(path)
        
    def clear_path(self):
        # QToolBar.clear() drops the actions as well as the widgets they wrap. Reparenting
        # the buttons away (what this used to do) destroyed the widgets but left every
        # previous path's QWidgetActions behind, so the toolbar's action list grew with
        # each navigation and those empty slots took up room the current path needed.
        self.clear()
        self._path_segments = []
        self._component_paths = []
        self._leading_separator_action = None
        self._truncation_marker = None
        self._truncation_marker_action = None
        self.toolbar_buttons = []

    def add_navigation_buttons_to_toolbar(self, path):
        buttons = []
        folders_in_path = list_all_subpaths_in_path(path)
        folders_in_path.append('')
        num_paths = len(folders_in_path)
        icon = QtGui.QIcon(get_full_icon_path(conf.RIGHT_ARROWHEAD_ICON_NAME))
        self.toolbar_buttons = []
        # One entry per path component, in order, holding the actions that must be shown or
        # hidden together: the component's button plus the separator drawn after it. The
        # leading separator is kept out of it - it always stays.
        self._path_segments = []
        # Full path of each component, so the marker's tooltip can name what it stands for.
        self._component_paths = folders_in_path[:-1]
        # Sits in front of everything, so a truncated path reads "... > Echo > Foxtrot".
        # Hidden whenever the whole path fits (_fit_path_to_width decides).
        self._truncation_marker = QLabel(TRUNCATION_MARKER_TEXT)
        self._truncation_marker.setStyleSheet("padding: 5px")
        set_object_font(self._truncation_marker, font_size=int(conf.TEXTBOX_FONT_SIZE),
                        font_family=conf.TEXT_FONT)
        self._truncation_marker_action = self.addWidget(self._truncation_marker)
        self._truncation_marker_action.setVisible(False)
        self._leading_separator_action = self.concat_separator_symbol(icon)
        for i, p in enumerate(folders_in_path):
            name = get_last_part_in_path(p)
            # The deepest component (the folder the pane is showing) is the one that must
            # survive any width, so it gets the button that can be clipped rather than
            # dropped. See ShrinkablePathButton.
            button = (ShrinkablePathButton(name, self) if i == num_paths-2
                      else QPushButton(name, self))
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
                # It is only a click target for the empty area, so let it shrink to nothing
                # rather than reserving a button's worth of width the path could use.
                buttons[i].setMinimumWidth(0)
            action = self.addWidget(buttons[i])
            if i < num_paths-1:
                self._path_segments.append([action])

            if i < num_paths-2:
                self._path_segments[i].append(self.concat_separator_symbol(icon))

        self.toolbar_buttons = buttons
        self._fit_path_to_width()

    @staticmethod
    def _action_width(action) -> int:
        widget = action.defaultWidget() if action is not None else None
        return widget.sizeHint().width() if widget is not None else 0

    def _fit_path_to_width(self):
        """Hide leading path components until the breadcrumb fits the width it has.

        A QToolBar lays its items out left to right and lets whatever doesn't fit run off
        the right-hand edge, so a path too long for the pane used to show the root end and
        hide the deepest folders - exactly the part that says where the user actually is.
        Hiding components from the left instead keeps the current folder on screen. The
        deepest component is never hidden, even when it alone is too wide. The leading
        separator always stays, so a truncated path still opens with an arrowhead.
        """
        segments = getattr(self, '_path_segments', None)
        if not segments:
            return
        available = self.width()
        if available <= 0:
            return  # not laid out yet; resizeEvent refits once it is
        for actions in segments:
            for action in actions:
                action.setVisible(True)
        marker_action = getattr(self, '_truncation_marker_action', None)
        if marker_action is not None:
            marker_action.setVisible(False)
        deepest = segments[-1][0].defaultWidget()
        if isinstance(deepest, ShrinkablePathButton):
            # Measure against the real name; it is elided again at the end if it has to be.
            deepest.restore_full_text()

        layout = self.layout()
        spacing = layout.spacing() if layout is not None else 0
        margins = layout.contentsMargins() if layout is not None else None
        needed = (margins.left() + margins.right()) if margins is not None else 0
        needed += self._action_width(self._leading_separator_action) + spacing
        # The empty-area button after the path can shrink but not vanish, so the width it
        # insists on is not available to the path.
        filler = self.toolbar_buttons[-1] if self.toolbar_buttons else None
        if filler is not None:
            needed += filler.minimumSizeHint().width() + spacing
        segment_widths = [sum(self._action_width(a) + spacing for a in actions)
                          for actions in segments]
        needed += sum(segment_widths)

        # Never hide the last component - it is the folder the pane is showing.
        marker_width = self._action_width(marker_action) + spacing
        last_hideable = len(segments) - 1
        i = 0
        while i < last_hideable and needed > available:
            for action in segments[i]:
                action.setVisible(False)
            needed -= segment_widths[i]
            i += 1
            if i == 1:
                # The marker only appears once something is actually dropped, and it needs
                # room of its own - which may itself force one more component out.
                needed += marker_width

        if marker_action is not None and i > 0:
            marker_action.setVisible(True)
            # Name the deepest folder the marker stands for, so the hidden part is still
            # reachable information rather than just a gap.
            if i <= len(self._component_paths):
                self._truncation_marker.setToolTip(self._component_paths[i - 1])

        # Once nothing else can be given up, the current folder's name is shortened to
        # whatever room is left rather than being dropped off the toolbar entirely.
        if isinstance(deepest, ShrinkablePathButton):
            deepest.fit_text_to(max(0, available - (needed - segment_widths[-1])))

    def resizeEvent(self, event):
        # Widening or narrowing the pane changes how much of the path fits.
        super().resizeEvent(event)
        self._fit_path_to_width()

    def concat_separator_symbol(self, sep: Union[str, QIcon]):
        # Returns the QAction the toolbar wraps the separator in, so _fit_path_to_width can
        # hide a separator along with the path button it belongs to.
        if isinstance(sep, str):
            label = QLabel(sep)
            return self.addWidget(label)
        elif isinstance(sep, QIcon):
            icn = QLabel()
            icn.setPixmap(sep.pixmap(20))  # Set the path to your icon
            icn.setStyleSheet("padding: 5px")
            return self.addWidget(icn)
        return None


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
    enable_home_end_keys(textbox)
    return textbox


def create_toolbar(parent, w: Union[int, None] = None, h: Union[int, None] = None,
                   icon_width: int = 16, icon_height: int = 16):
    toolbar = CustomSizeQToolBar(parent, w, h)
    toolbar.setIconSize(QtCore.QSize(icon_width, icon_height))
    toolbar.setStyleSheet(conf.TOOLBAR_STYLE)
    return toolbar


class Pane:
    """
    Groups the per-pane widgets so a single `ui` window can hold one or more
    file-explorer panes side by side. Each pane owns its own data model, table,
    and a breadcrumb navigator + editable path textbox (which live in the shared
    top toolbar, on the same row as the navigation buttons).
    """
    def __init__(self):
        self.model = None            # PandasModel
        self.table = None            # FileExplorerTable
        self.navigator = None        # TextboxNavigator (breadcrumb)
        self.textbox = None          # QLineEdit (editable path input)
        self.event_filter = None     # textboxEventFilter for `textbox`
        self.stacked_widget = None   # toggles navigator <-> textbox
        self.top_toolbar = None      # per-pane top band holding stacked_widget
        self.column = None           # QWidget stacking top_toolbar over the table


# Keymap actions that must keep working while the left pane (favorites list / folder
# tree) has the keyboard focus. They all act on the window, or on the active pane as a
# whole, so they mean something even though the left pane holds no file selection.
# Actions that DO need a file selection - copy, cut, permanently-delete, enter,
# show-in-Finder, open-in-terminal, context menu, and the Shift+arrow / Shift+Home/End
# selection-extension keys - are deliberately absent: from the left pane they would have
# nothing to act on, and binding them there would also steal the arrow keys the tree and
# the favorites list navigate with.
LEFT_PANE_ACTIONS = ("NEW_WINDOW", "UP", "BACK", "FORWARD", "PASTE_FROM_CLIPBOARD",
                     "SELECT_ALL", "LAUNCH_FIND_WINDOW", "UNDO_LAST_ACTION",
                     "REDO_LAST_UNDONE_ACTION", "JUMP_TO_PATH_TEXTBOX", "CLOSE_WINDOW",
                     # Pane cycling fires from the whole left pane, the folder tree
                     # included: clicking a tree folder leaves focus there, and Tab has to
                     # get out of it. The tree is not a stop in the cycle - see
                     # _cycle_pane_focus.
                     "SWITCH_PANE_FOCUS", "SWITCH_PANE_FOCUS_BACKWARDS")


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
         Main horizontal split: [ left column | file-explorer pane(s) ].
         Each column carries its own top band (buttons over the sidebar, a breadcrumb
         over each table), so every top band lines up on one row and each breadcrumb
         stays directly above its own table column as the splitter is dragged.
        """
        logger.info("ui - init main split")
        self.subsplitter = QSplitter(Qt.Orientation.Horizontal, parent=self.splitter)
        self.subsplitter.splitterMoved.connect(self.update_structure)
        self.subsplitter.setHandleWidth(1)
        self.subsplitter.setStyleSheet(self._left_pane_separator_style())


        """
         Left column: navigation buttons on top, Favorites + Tree below
        """
        logger.info("ui - init left column")
        self.left_column = QWidget()
        # Paint the left column itself with the left-pane color so the 4px strip
        # above the toolbar (exposed by the toolbar's margin-top) blends in rather
        # than showing the default window background. Scoped by object name so it
        # doesn't cascade onto child widgets.
        self.left_column.setObjectName("leftColumn")
        self.left_column.setStyleSheet(self._left_column_background_style())
        self.left_column_layout = QVBoxLayout(self.left_column)
        self.left_column_layout.setContentsMargins(0, 0, 0, 0)
        self.left_column_layout.setSpacing(0)

        self.generate_top_toolbar()
        self.left_column_layout.addWidget(self.toolbar)

        hght = conf.WINDOW_HEIGHT - (conf.TOP_TOOLBAR_HEIGHT + conf.BOTTOM_TOOLBAR_HEIGHT)
        self.trees_subsplitter = \
            CustomSizeQSplitter(type=Qt.Orientation.Vertical, parent=self.left_column,
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
        self.tree = TreeFileExplorer(parent=self.trees_subsplitter, encompassing_ui=self)
        self.tree.expandAll()
        self.tree_area.addWidget(self.tree)

        self.left_column_layout.addWidget(self.trees_subsplitter)
        self.subsplitter.addWidget(self.left_column)


        """
         Right area: one or two file-explorer panes side by side, each a column of
         [ breadcrumb navigator | table ].
        """
        logger.info("ui - init right area (panes)")
        self.panes = []
        self._active_pane_index = 0
        self.panes_splitter = QSplitter(Qt.Orientation.Horizontal, parent=self.subsplitter)
        self.panes_splitter.setHandleWidth(5)
        # Light grey vertical separating line between the two panes (dual-pane mode).
        # The handle stays 5px wide for easy dragging; only a 1px line is drawn.
        self.panes_splitter.setStyleSheet(
            "QSplitter::handle:horizontal{background-color: transparent;"
            " border-left: 1px solid lightgrey;}")
        self.panes_splitter.splitterMoved.connect(self.update_structure)
        hght = height-(conf.TOP_TOOLBAR_HEIGHT + conf.BOTTOM_TOOLBAR_HEIGHT)
        num_panes = 2 if conf.DUAL_PANE_MODE else 1
        for _ in range(num_panes):
            pane = self._create_pane(root_dir_path, columns_ordering_scheme,
                                     file_explorer_width, hght)
            self.panes.append(pane)
            self.panes_splitter.addWidget(pane.column)



        """
         Bottom area: bottom toolbar
        """
        logger.info("ui - init bottom area")
        self.config_upper_toolbar_text_and_dims()
        self.generate_bottom_toolbar()
        self.config_bottom_toolbar_text_and_dims()



        # The window-level and active-pane-level shortcuts are part of the configurable
        # keymap and are registered on every FileExplorerTable via
        # initialize_all_key_sequences. They must also fire when the left pane has focus,
        # so bind them there too (see LEFT_PANE_ACTIONS).
        self.reload_left_pane_shortcuts()
        # shortcut2 = QShortcut(QKeySequence("Ctrl+Alt+Home"), self)
        # shortcut2.activated.connect(self.expose_input_textbox)
        

        for pane in self.panes:
            pane.navigator.update_path(pane.table.path)
        # Titled from the pane's real path rather than conf.DEFAULT_PATH, since a window
        # can be opened at an arbitrary root (e.g. `open -a CleanFinder <path>`).
        self.update_window_title(self.panes[0].table.path)

        self.setAcceptDrops(True)
        self.splitter.setAcceptDrops(True)
        self.subsplitter.setAcceptDrops(True)

        self.installEventFilter(self)

        self.setCentralWidget(self.splitter)

        logger.info("ui - setting dimensions")
        self.subsplitter.setStretchFactor(left_pane_width/file_explorer_width, 1)
        self.trees_subsplitter.resize(self.trees_subsplitter.sizeHint())
        for pane in self.panes:
            pane.table.resize(pane.table.sizeHint())
        self.panes[0].table.setFocus()

        # Must come in the end (otherwise may be overridden)
        self.set_ui_sizes()

        logger.info("ui - initialization finished")

        # Moved here (UI object) for Sequoia 15.3:
        self.menubar_manager = MebuBarManager(self)  # Takes care of menu bar requests
        logger.info("Starting app - populate_menubar_and_connect_triggers")



    @property
    def file_explorer(self):
        """The active pane's table. Keeps 'act on the current table' semantics for
        all the shared controls (toolbar buttons, tree, favorites, keyboard)."""
        return self.panes[self._active_pane_index].table

    @property
    def active_pane(self):
        return self.panes[self._active_pane_index]

    def all_tables(self):
        return [p.table for p in self.panes]

    def _pane_of(self, table):
        for p in self.panes:
            if p.table is table:
                return p
        return self.active_pane

    def set_active_pane(self, pane):
        try:
            self._active_pane_index = self.panes.index(pane)
        except ValueError:
            return
        # Reflect the newly-active pane in the shared window chrome
        self.update_window_title(pane.table.path)
        self.refresh_bottom_toolbar_text(pane.table)

    def set_active_pane_by_table(self, table):
        if not getattr(self, 'panes', None):
            return
        self.set_active_pane(self._pane_of(table))

    @property
    def path(self):
        return self.file_explorer.path

    def _cycle_pane_focus(self, direction: int):
        # direction = 1: forward (favorites -> pane(s) -> favorites),
        # direction = -1: backward. Cycles across the favorites pane and every table pane.
        targets = [self.favs_table_view] + self.all_tables()
        # Default 0 = the favorites position. Nothing else in the left pane is a stop in
        # the cycle, so pressing the key while the folder tree has focus enters the cycle
        # as if the user were standing on the favorites list: forward to the first pane,
        # backward to the last one. The tree is never landed on.
        idx = 0
        for i, t in enumerate(targets):
            if t.hasFocus():
                idx = i
                break
        nxt = targets[(idx + direction) % len(targets)]
        if nxt is not self.favs_table_view:
            self.favs_table_view.clearSelection()
        nxt.setFocus()

    def switch_table_focus(self):
        self._cycle_pane_focus(1)

    def switch_table_focus_backwards(self):
        self._cycle_pane_focus(-1)

    def left_pane_shortcut_widgets(self):
        # The focusable widgets of the left pane: the favorites list and the folder tree.
        tree = getattr(self, 'tree', None)
        return [w for w in (self.favs_table_view, tree) if w is not None]

    def _active_pane_shortcut_handler(self, action_name: str):
        """Build the handler for one left-pane shortcut.

        map_shortcut_name_to_func returns a method bound to the table it is given, so
        resolving it here, at bind time, would freeze the shortcut onto whichever pane
        happened to be active while the window was being built. The returned lambda looks
        self.file_explorer up when the key is actually pressed instead, so the shortcut
        always acts on the pane that is active by then - which matters because clicking a
        bookmark or a tree folder navigates the active pane but leaves focus in the left
        pane, and that active pane can change in between.

        The lambda takes no arguments on purpose: QAction.triggered emits a bool as its
        first argument, and a one-argument lambda would receive that bool.
        """
        return lambda: map_shortcut_name_to_func(self.file_explorer, action_name)()

    def reload_left_pane_shortcuts(self):
        """Re-bind, from the current keymap, the shortcuts that must keep working while the
        left pane has focus.

        initialize_all_key_sequences registers the whole keymap on every FileExplorerTable,
        but the left-pane widgets are not tables, so a shortcut pressed there reaches no
        action at all - the user would have to click into a table first. The window-level
        and active-pane-level actions (LEFT_PANE_ACTIONS) are therefore bound here a second
        time, on every focusable left-pane widget. Tagged actions are cleared first so
        keymap reloads don't accumulate stale duplicates.
        """
        left_pane_widgets = self.left_pane_shortcut_widgets()
        for widget in left_pane_widgets:
            for act in list(widget.actions()):
                if act.property("is_left_pane_shortcut"):
                    widget.removeAction(act)
        shortcuts = conf.get("keyboard_shortcuts")
        for action_name in LEFT_PANE_ACTIONS:
            handler = self._active_pane_shortcut_handler(action_name)
            for widget in left_pane_widgets:
                for key_sequence in shortcuts.get(action_name, []):
                    action = create_qaction_key_sequence(widget, key_sequence, handler)
                    action.setProperty("is_left_pane_shortcut", True)

    def change_path(self, newpath: str, reset_path_history: bool = True):
        self.file_explorer.change_path(newpath, reset_path_history=reset_path_history)

    def sizeHint(self):
        num_panes = len(self.panes) if hasattr(self, 'panes') else 1
        return QSize(self.left_pane_width + num_panes * self.file_explorer_width + 50,
                     self.height)

    def update_window_title(self, path: str):
        """
        Titles the window after the folder it is showing, so each open window is
        distinguishable in the Dock/Mission Control previews and the window menu.
        Must be set on the QMainWindow itself: this used to be set on `self.splitter`,
        but setCentralWidget() reparents the splitter, and a non-top-level widget's
        windowTitle never reaches the native window - leaving every window titled with
        the app name. `Path('/').name` is empty, so the root dir falls back to its
        separator rather than an empty title.
        """
        self.setWindowTitle(get_last_part_in_path(path) or path)

    def configure_splitter(self):
        # Take care of the horizontal lines separating the different widgets within the subsplitter
        self.splitter.setHandleWidth(5)  # The gap size between the textbox and the table
        self.splitter.setStyleSheet(conf.GAP_BETWEEN_TOOLBAR_AND_BELOW_STYLE)

    def _left_pane_separator_style(self):
        # The vertical line separating the left pane from the breadcrumbs/table.
        # subsplitter is horizontal, so its handle is styled via ::handle:horizontal.
        return ("QSplitter::handle:horizontal{background-color: "
                + conf.LEFT_PANE_SEPARATOR_COLOR + ";}")

    def _left_column_background_style(self):
        # Backs the left column widget with the left-pane color (object-name scoped
        # so it doesn't cascade to children).
        return ("QWidget#leftColumn{background-color: "
                + conf.LEFT_PANE_BACKGROUND_COLOR + ";}")

    def generate_top_toolbar(self):
        self.toolbar = create_toolbar(parent=self.left_column)
        # The left column's button toolbar belongs to the left pane, so back it
        # with the left-pane color instead of the shared file-explorer toolbar color.
        self.toolbar.setStyleSheet(conf.LEFT_TOOLBAR_STYLE)
        # Buttons (can appear stand-alone, in a menubar, etc...)
        # up_button = create_action(self, icon_path=get_full_icon_path(conf.UP_ICON_NAME), when_triggered=self.go_to_parent_dir)
        up_button = create_pushbutton(self, icon_path=get_full_icon_path(conf.UP_ICON_NAME), width=20, height=20, when_triggered=self.go_to_parent_dir)
        # Push-buttons
        back_pushbutton    = create_pushbutton(self, icon_path=get_full_icon_path(conf.BACKWARD_ICON_NAME), width=20, height=20, when_triggered=self.go_to_previous_path)
        self.down_button   = create_pushbutton(self, icon_path=get_full_icon_path(conf.DOWN_ICON_NAME), when_triggered=self.show_browsing_history)
        forward_pushbutton = create_pushbutton(self, icon_path=get_full_icon_path(conf.FORWARD_ICON_NAME), width=20, height=20, when_triggered=self.go_to_next_path)

        # Leading spacer to nudge the nav buttons right (transparent, so the toolbar's
        # left-pane background shows through). Tweak the width to change the offset.
        left_spacer = QWidget()
        left_spacer.setFixedWidth(5)
        left_spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.toolbar.addWidget(left_spacer)
        self.toolbar.addWidget(back_pushbutton)
        self.toolbar.addWidget(forward_pushbutton)
        self.toolbar.addWidget(self.down_button)
        # self.toolbar.addAction(up_button)
        self.toolbar.addWidget(up_button)


    def _build_navigator(self, pane):
        # Breadcrumb navigator wired to act on THIS pane: clicking a path button
        # navigates the pane (and makes it active); clicking the empty area exposes
        # the pane's editable textbox.
        def navigate(path, reset_path_history=True):
            self.set_active_pane(pane)
            pane.table.change_path(path, reset_path_history=reset_path_history)

        return TextboxNavigator(encompassing_obj=self,
                                method_when_clicked_on_path_btn=navigate,
                                method_when_clicked_on_empty_area=lambda: self.expose_input_textbox(pane),
                                default_height=conf.TOP_TOOLBAR_HEIGHT)

    def _create_pane(self, root_dir_path, columns_ordering_scheme, xdim, ydim):
        pane = Pane()
        pane.model = PandasModel(datapath=root_dir_path,
                                 columns_ordering_scheme=columns_ordering_scheme)
        pane.table = FileExplorerTable(pane.model, parent=self.panes_splitter,
                                       root_dir_path=root_dir_path,
                                       xdim=xdim, ydim=ydim, encompassing_ui=self)

        pane.textbox = create_textbox(self)
        pane.event_filter = self.textboxEventFilter(self, pane)
        pane.textbox.installEventFilter(pane.event_filter)
        pane.navigator = self._build_navigator(pane)

        # Behind the breadcrumb navigator there's an actual editable textbox.
        pane.stacked_widget = QStackedWidget()
        pane.stacked_widget.addWidget(pane.navigator)
        pane.stacked_widget.addWidget(pane.textbox)

        # Each pane is a column of [ breadcrumb toolbar | table ]. The per-pane top
        # toolbar sits at the same height as the left column's button toolbar, so all
        # top bands align on one row, and the breadcrumb stays directly above its table.
        pane.top_toolbar = create_toolbar(parent=self)
        pane.top_toolbar.addWidget(pane.stacked_widget)

        pane.column = QWidget()
        col_layout = QVBoxLayout(pane.column)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(0)
        col_layout.addWidget(pane.top_toolbar)
        col_layout.addWidget(pane.table)

        pane.table.viewport().setAcceptDrops(True)
        return pane


    def config_upper_toolbar_text_and_dims(self):
        height = conf.TEXTBOX_FONT_SIZE
        self.toolbar.setFixedHeight(height + 28)
        for pane in self.panes:
            # Match the left column's button toolbar height so every top band aligns
            pane.top_toolbar.setFixedHeight(height + 28)
            set_object_font(pane.textbox, font_size=int(conf.TEXTBOX_FONT_SIZE),
                            font_family=conf.TEXT_FONT)
            pane.navigator.setFixedHeight(height + 20)
            pane.textbox.setFixedHeight(height + 20)
            pane.stacked_widget.setFixedHeight(height + 20)
            pane.navigator.update_fonts()


    def config_bottom_toolbar_text_and_dims(self):
        set_object_font(self.bottom_label, font_size=int(conf.BOTTOM_TEXT_FONT_SIZE),
                        font_family=conf.TEXT_FONT)
        height = conf.BOTTOM_TEXT_FONT_SIZE
        self.bottom_toolbar.setFixedHeight(height + 12)


    def generate_favorites_area(self):
        # The "Bookmarks" row
        if conf.SHOW_FAVORITES_TITLE:
            self.favs_table_view_header = LinksTable({"Name": [conf.FAVORITES_TITLE],
                                                      "Path": [None],
                                                      "icon_full_path": [get_full_icon_path(conf.FAVORITES_ICON)]},
                                                      row_height=conf.FAVORITES_ROW_HEIGHT + 12)
            # Nudge the icon + text right by a few pixels. spacer_column_indent works only
            # in whole space-characters (too coarse), and setViewportMargins gets wiped by
            # QTableView.updateGeometries -- so add left padding on the item itself, which
            # shifts both the icon and the text and survives geometry recalcs.
            self.favs_table_view_header.setStyleSheet(
                conf.FAVORITES_TABLE_STYLE + "QTableView::item { padding-left: 6px; }")
            self.favs_table_view_header.setFixedHeight(int(round(self.favs_table_view_header.rowHeight(0), 0)))
            self.favs_table_view_header.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        # The actual favorites table
        self.favs_table_view_layout = QHBoxLayout()
        self.favs_table_view = LinksTable(conf.BASIC_FAVORITES_DICT,
                                          row_height=conf.FAVORITES_ROW_HEIGHT,
                                          spacer_column_indent=4,
                                          encompassing_ui=self)
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

        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self.favs_table_view)
        shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        shortcut.activated.connect(self.on_enter_pressed_on_favorites_table)


    def generate_bottom_toolbar(self):
        self.bottom_toolbar = create_toolbar(parent=self.splitter, h=conf.BOTTOM_TOOLBAR_HEIGHT)
        self.bottom_toolbar.setStyleSheet(conf.BOTTOM_TOOLBAR_STYLE)
        self.bottom_label = QLabel('')
        self.bottom_label.setWordWrap(True)
        self.bottom_label.setFixedHeight(conf.BOTTOM_TEXT_FONT_SIZE)
        self.bottom_label.setStyleSheet(conf.BOTTOM_TOOLBAR_TEXT_STYLE)  # Top, Right, Bottom, Left
        self.bottom_toolbar.addWidget(self.bottom_label)

    def reload_keyboard_shortcuts(self):
        for t in self.all_tables():
            t.initialize_all_key_sequences()
        self.reload_left_pane_shortcuts()

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
        for t in self.all_tables():
            t.adapt_width_of_last_column()
        self.update_structure_in_config()

    def path_changed(self, source_table, new_path: str, reset_tree_selection: bool):
        pane = self._pane_of(source_table)
        # Always keep the originating pane's own breadcrumb + textbox in sync
        pane.navigator.update_path(new_path)
        pane.textbox.setText(new_path)
        # Shared chrome (tree selection, window title, bottom bar) tracks the active pane
        if source_table is self.file_explorer:
            if reset_tree_selection:
                self.tree.clearSelection()
            self.update_window_title(new_path)
            self.refresh_bottom_toolbar_text(source_table)

    def refresh_bottom_toolbar_text(self, source_table=None, num_items_selected: int = None,
                                    size_of_items_selected: int = None):
        # Only the active pane drives the shared bottom status bar
        if source_table is not None and source_table is not self.file_explorer:
            return
        if num_items_selected is None:
            self.bottom_label.setText('')
        else:
            if num_items_selected == 1:
                items_str = ' item,  '
            else:
                items_str = ' items,  '
            self.bottom_label.setText(str(num_items_selected) + items_str + size_of_items_selected)


    def expose_input_textbox(self, pane=None):
        if pane is None:
            pane = self.active_pane
        self.set_active_pane(pane)
        pane.textbox.selectAll()
        pane.stacked_widget.setCurrentWidget(pane.textbox)
        pane.textbox.setFocus()

    def hide_input_textbox(self, pane):
        pane.textbox.setText(pane.table.path)
        pane.stacked_widget.setCurrentWidget(pane.navigator)

    def jump_to_path_textbox(self):
        # Bound to the JUMP_TO_PATH_TEXTBOX keyboard shortcut (fires on the focused
        # table, so the active pane is the right one to expose).
        self.expose_input_textbox(self.active_pane)


    class textboxEventFilter(QtCore.QObject):
        def __init__(self, encompassing_ui, pane):
            super().__init__()
            self.encompassing_ui = encompassing_ui
            self.pane = pane

        def eventFilter(self, source, event):
            if (event.type() == QEvent.Type.KeyPress):
                if (event.key() == Qt.Key.Key_Escape):
                    self.encompassing_ui.hide_input_textbox(self.pane)
                    self.pane.table.setFocus()
                elif (event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return):
                    # resolve_typed_path expands a leading '~' and tolerates stray
                    # whitespace, so "~/Library" navigates like "/Users/<me>/Library".
                    target_path = resolve_typed_path(self.pane.textbox.text())
                    if target_path is not None:
                        try:
                            self.pane.table.change_path(target_path)
                            self.encompassing_ui.hide_input_textbox(self.pane)
                            # Return focus to this pane's table so arrow / Tab keys respond
                            self.pane.table.setFocus()
                        except:
                            pass
            elif event.type() == QtCore.QEvent.Type.FocusOut:
                self.encompassing_ui.hide_input_textbox(self.pane)

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

    def on_enter_pressed_on_favorites_table(self):
        if self.favs_table_view.hasFocus():
            index = self.favs_table_view.currentIndex()
            if index.isValid():
                self.favs_table_clicked(index)

    def favs_table_clicked(self, index):
        logger.info(">> ui.favs_table_clicked")
        self.favs_table_view.clearSelection()
        target_path = self.favs_table_view.path_at_row(index.row())
        # A bookmark can point at a volume that is no longer mounted, or at one whose
        # server has gone away without the mount being torn down. The latter answers
        # stat() only after a multi-minute kernel timeout, which would freeze the
        # window, so refuse to navigate rather than block on it.
        if not is_reachable_path(target_path):
            logger.warning("favs_table_clicked: '" + str(target_path) + "' is unreachable")
            prompt_message("Unavailable location",
                           "'" + str(target_path) + "' is not available.\n"
                           "The volume may be disconnected or no longer responding.")
            return
        self.change_path(target_path, reset_path_history=False)

    def launch_search_window(self):
        logger.info("ui.launch_search_window")
        self.search_window = SearchWindow_threaded(self.path, self)
        self.search_window.show()

    def set_ui_sizes(self):
        num_panes = len(self.panes)
        self.resize(conf.LEFT_PANE_WIDTH + num_panes * conf.FILE_EXPLORER_WIDTH,
                    conf.WINDOW_HEIGHT)
        self.subsplitter.setSizes([conf.LEFT_PANE_WIDTH,
                                   num_panes * conf.FILE_EXPLORER_WIDTH])
        # If user resizes the entire window, the left pane will not be resized:
        self.subsplitter.setStretchFactor(0, 0)
        self.subsplitter.setStretchFactor(1, 1)
        if num_panes > 1:
            self.panes_splitter.setSizes([conf.FILE_EXPLORER_WIDTH] * num_panes)

    def refresh_all_configurations(self):
        logger.info("ui.refresh_all_configurations")
        if conf.SHOW_FAVORITES_TITLE:
            # Keep the left-padding nudge on the item (see generate_favorites_area).
            self.favs_table_view_header.setStyleSheet(
                conf.FAVORITES_TABLE_STYLE + "QTableView::item { padding-left: 3px; }")
            # Pick up a newly chosen bookmarks icon without reopening the window. Addressed by
            # column name because this one-row table has no spacer column, so icon_full_path
            # sits at a different position than it does in the favorites table below it.
            header_model = self.favs_table_view_header.table
            header_model._data.loc[0, 'icon_full_path'] = get_full_icon_path(conf.FAVORITES_ICON)
            header_model.layoutChanged.emit()
        self.favs_table_view.setStyleSheet(conf.FAVORITES_TABLE_STYLE)
        self.toolbar.setStyleSheet(conf.LEFT_TOOLBAR_STYLE)
        self.left_column.setStyleSheet(self._left_column_background_style())
        self.subsplitter.setStyleSheet(self._left_pane_separator_style())
        self.tree.setStyleSheet(conf.TREE_STYLE)
        for pane in self.panes:
            pane.top_toolbar.setStyleSheet(conf.TOOLBAR_STYLE)
            pane.textbox.setStyleSheet(conf.TEXTBOX_STYLE)
            pane.navigator.setStyleSheet(conf.TEXTBOX_NAVIGATOR_STYLE)
            for btn in pane.navigator.toolbar_buttons:
                btn.setStyleSheet(conf.TEXTBOX_NAVIGATOR_BUTTON_STYLE)
            pane.table.refresh_all_configurations()
        self.bottom_toolbar.setStyleSheet(conf.BOTTOM_TOOLBAR_STYLE)
        self.bottom_label.setMaximumHeight(conf.BOTTOM_TEXT_FONT_SIZE)
        self.bottom_label.setStyleSheet(conf.BOTTOM_TOOLBAR_TEXT_STYLE)  # Top, Right, Bottom, Left

    def update_structure_in_config(self):
        logger.info("ui.update_structure_in_config")
        if self._allow_structure_updates:
            # Persist column/window widths from the first (left) pane so the two
            # panes don't fight over the shared FILE_EXPLORER_* config keys.
            table0 = self.panes[0].table
            conf.set_attr("WINDOW_HEIGHT", self.splitter.height())
            conf.set_attr("FILE_EXPLORER_WIDTH", table0.width())
            conf.set_attr("LEFT_PANE_WIDTH", self.subsplitter.sizes()[0])
            conf.set_attr("BOTTOM_TOOLBAR_HEIGHT", self.bottom_toolbar.height())
            conf.set_attr("FILE_EXPLORER_COL_WIDTH_1", table0.columnWidth(0))
            conf.set_attr("FILE_EXPLORER_COL_WIDTH_2", table0.columnWidth(1))
            conf.set_attr("FILE_EXPLORER_COL_WIDTH_3", table0.columnWidth(2))
            conf.set_attr("FILE_EXPLORER_COL_WIDTH_4", table0.columnWidth(3))

    def on_close(self):
        self.encompassing_uis_manager.on_ui_close(self)

    def keyPressEvent(self, e):
        self.file_explorer.keyPressEvent(e)
