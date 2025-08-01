from typing import Callable, Union
import itertools
import os

from PIL import Image

from PySide6 import QtCore
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from src.shared.vars import conf_manager as conf, logger as logger
from src.shared.locations import ICONS_DIR


def flatten_list_of_lists(lst):
    return list(itertools.chain(*lst))


def traverse_dict_as_tree(d: dict, prefix: str = None):
    dict_items = []
    for k in d.keys():
        if isinstance(d[k], dict):
            dict_items = dict_items + list(traverse_dict_as_tree(d[k], prefix=k))
        else:
            dict_items.append([prefix, k, d[k]])
    return dict_items


def search_all_key_paths_in_dict(d: dict, target_key: str, current_path: str = None):
    if current_path is None:
        current_path = []
    paths = []
    if isinstance(d, dict):
        for key, value in d.items():
            new_path = current_path + [key]
            if key == target_key:
                paths.append(new_path)
            paths.extend(search_all_key_paths_in_dict(value, target_key, new_path))
    elif isinstance(d, list):
        for index, item in enumerate(d):
            new_path = current_path + [index]
            paths.extend(search_all_key_paths_in_dict(item, target_key, new_path))
    return paths


class single_run_qtimer():
    def __init__(self, milliseconds: int, func: Callable, **args):
        logger.info("single_run_qtimer")
        self.func = func
        self.timer = QTimer()
        self.timer.timeout.connect(self.when_timer_finishes)
        self.timer.start(milliseconds)
        self.args = args
        self.is_alive = True

    def when_timer_finishes(self):
        logger.info("single_run_qtimer: when_timer_finishes")
        self.func(**self.args)
        self.timer.stop()

    def stop_timer(self):
        logger.info("single_run_qtimer: stop_timer")
        self.timer.stop()
        self.is_alive = False


def convert_incs_to_png(icns_file_path: str, output_file_path: str = None):
    if icns_file_path[-5:] != '.icns':
        return -1
    if output_file_path is None:
        output_file_path = icns_file_path[:-5] + '.png'
    try:
        Image.open(icns_file_path).save(output_file_path)
        success = 1
    except:
        success = -1
    return success


def get_full_icon_path(icon_file_name: str, extention: str = 'png'):
    path = os.path.join(ICONS_DIR, icon_file_name) + '.' + extention
    if os.path.exists(path):
        return path
    else:
        return None


def get_max_integer_suffix_among_strings_with_prefix(str_list: list[str], prefix: str) -> Union[int, None]:
    logger.info("get_max_integer_suffix_among_strings_with_prefix")
    suff = None
    prefix_len = len(prefix.lower())
    prefix_lower = prefix.lower()

    all_suffices_with_template_prefix = \
        [s.lower().replace(prefix.lower(), '')
         for s in str_list
         if s[0:prefix_len].lower() == prefix_lower]

    if len(all_suffices_with_template_prefix) > 0:
        current_newfolder_numeric_suffices = [int(x)
                                              for x in all_suffices_with_template_prefix
                                              if x.strip().isdigit()]
        if len(current_newfolder_numeric_suffices) >= 1:
            suff = max(current_newfolder_numeric_suffices)

    return suff


def get_full_path_from_index(index) -> str:
    if index.data() == index.model().rootPath():
        return index.data()
    return os.path.join(get_full_path_from_index(index.parent()), index.data())


def is_legal_key_sequence(key_seq: str) -> bool:
    tmp_action = QAction()
    tmp_action.setShortcut(QKeySequence(key_seq))
    keys_set = set(tmp_action.shortcut().toString().lower().split("+"))
    return len(keys_set.difference(set(key_seq.lower().split("+")))) == 0


def create_qaction_key_sequence(obj, key_sequence: str, when_triggered: Callable):
    newTableAction = QAction(obj)
    newTableAction.setShortcut(QKeySequence(key_sequence))
    newTableAction.triggered.connect(when_triggered)
    obj.addAction(newTableAction)


def map_key_to_new_row_num(key_id: int, caller_widget) -> int:
    is_currently_selected = len(caller_widget.selectedIndexes()) > 0
    if is_currently_selected:
        current_row = caller_widget.selectedIndexes()[0].row()

    if key_id == QtCore.Qt.Key.Key_Up:        # Up arrow
        if is_currently_selected:
            return current_row - 1
        else:
            return None
    elif key_id == QtCore.Qt.Key.Key_Down:    # Down arrow
        if is_currently_selected:
            return current_row + 1
        else:
            return 0
    elif key_id == QtCore.Qt.Key.Key_Home:    # Home
        return 0
    elif key_id == QtCore.Qt.Key.Key_End:     # End
        last_row = caller_widget.model()._data.shape[0]-1
        return last_row
    elif key_id == QtCore.Qt.Key.Key_PageUp:  # PageUp
        if is_currently_selected:
            new_row = current_row - conf.PAGE_DOWN_UP_NUM_ROWS
            return max([new_row, 0])
        else:
            return 0
    elif key_id == QtCore.Qt.Key.Key_PageDown:  # PageDown
        last_row = caller_widget.model()._data.shape[0]-1
        if is_currently_selected:
            new_row = current_row + conf.PAGE_DOWN_UP_NUM_ROWS
            return min([new_row, last_row])
        else:
            max([last_row, conf.PAGE_DOWN_UP_NUM_ROWS])
    else:
        return None


def configure_context_menu(menu):
    menu.setStyleSheet(conf.TABLE_CONTEXT_MENU_STYLE)
    menu.setFixedWidth(150)
    # Make it rounded:
    menu.setWindowFlags(Qt.WindowType.Popup |
                        Qt.WindowType.FramelessWindowHint |
                        Qt.WindowType.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def add_actions_to_context_menu(menu, widget, actions_list):
    for action_dict in actions_list:
        if action_dict["menu_item_name"] == "SEP":
            menu.addSeparator()
            continue
        action = QAction("  " + action_dict["menu_item_name"], widget)
        action.triggered.connect(action_dict["associated_method"])
        menu.addAction(action)


class SinglePathQFileSystemWatcherWithContextManager(QFileSystemWatcher):

    def __init__(self, path: str):
        self.path = path
        super(SinglePathQFileSystemWatcherWithContextManager, self).__init__()

    def __enter__(self):
        self.removePath(self.path)

    def __exit__(self, exception_type, exception_value, traceback):
        self.addPath(self.path)
