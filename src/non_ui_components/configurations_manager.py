from typing import Union
import os.path
import json
import datetime
from src.shared.locations import ICONS_DIR, BASE_ICONS_DIR


def is_string_rgb(s):
    if type(s) != str:
        return False
    s = s.lower()
    if s[0:4] != 'rgb(':
        return False
    if s[-1:] != ')':
        return False
    colors = s.replace('rgb(', '').replace(')', '').replace(' ', '').split(',')
    if len(colors) != 3:
        return False
    if not all([x.isnumeric() for x in colors]):
        return False
    if not all([int(x) >= 0 for x in colors]):
        return False
    if not all([int(x) <= 255 for x in colors]):
        return False
    return True


class ConfigurationsManager:

    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self.upload_all_configurations_from_json(self.config_file_path)

    def upload_all_configurations_from_json(self, config_file_path):

        if os.path.exists(config_file_path):
            self.config = json.load(open(config_file_path))
            self.config_file_path = config_file_path
        else:
            self.config = self.default_config
            self.config_file_path = config_file_path
            self.save_config_to_file()

        self.FILENAME_COLUMN_INDEX = 0
        self.FILETYPE_COLUMN_INDEX = 3
        self.IS_FOLDER_COLUMN_INDEX = 8

        self.FILE_EXPLORER_TABLE_GRID_TYPE = None
        self.FILE_EXPLORER_TABLE_GRID_TYPE_NAME = 'no_grid'
        if self.FILE_EXPLORER_TABLE_GRID_TYPE_NAME == 'no_grid':
            self.FILE_EXPLORER_TABLE_GRID = False
            self.FILE_EXPLORER_TABLE_GRID_LINES_BETWEEN = False
            self.FILE_EXPLORER_TABLE_GRID_ROUNDED = False
        elif self.FILE_EXPLORER_TABLE_GRID_TYPE_NAME == 'rows_rounded_rectangles':
            self.FILE_EXPLORER_TABLE_GRID = True
            self.FILE_EXPLORER_TABLE_GRID_LINES_BETWEEN = False
            self.FILE_EXPLORER_TABLE_GRID_ROUNDED = True
        elif self.FILE_EXPLORER_TABLE_GRID_TYPE_NAME == 'full_grid_rectangles':
            self.FILE_EXPLORER_TABLE_GRID = True
            self.FILE_EXPLORER_TABLE_GRID_LINES_BETWEEN = True
            self.FILE_EXPLORER_TABLE_GRID_ROUNDED = False
        elif self.FILE_EXPLORER_TABLE_GRID_TYPE_NAME == 'full_grid_rounded_rectangles':
            self.FILE_EXPLORER_TABLE_GRID = True
            self.FILE_EXPLORER_TABLE_GRID_LINES_BETWEEN = True
            self.FILE_EXPLORER_TABLE_GRID_ROUNDED = True
        elif self.FILE_EXPLORER_TABLE_GRID_TYPE_NAME == 'rows_rectangles':
            self.FILE_EXPLORER_TABLE_GRID = True
            self.FILE_EXPLORER_TABLE_GRID_LINES_BETWEEN = False
            self.FILE_EXPLORER_TABLE_GRID_ROUNDED = False
        

        self.SHOW_HIDDEN_ITEMS = self.config["SHOW_HIDDEN_ITEMS"]

        colors = self.config["colors"]
        self.FILE_EXPLORER_HEADER_COLOR = colors["FILE_EXPLORER_HEADER_COLOR"]
        self.FILE_EXPLORER_BACKGROUND_COLOR = colors["FILE_EXPLORER_BACKGROUND_COLOR"]
        self.FILE_EXPLORER_ALTERNATE_BACKGROUND_COLOR = colors["FILE_EXPLORER_ALTERNATE_BACKGROUND_COLOR"]
        self.TOOLBAR_BACKGROUND_COLOR = colors["TOOLBAR_BACKGROUND_COLOR"]
        self.LEFT_PANE_BACKGROUND_COLOR = colors["LEFT_PANE_BACKGROUND_COLOR"]
        self.BOTTOM_STRIP_COLOR = colors["BOTTOM_STRIP_COLOR"]

        self.FILE_EXPLORER_GRID_THICKNESS = self.config["FILE_EXPLORER_GRID_THICKNESS"]
        
        (self.FILE_EXPLORER_GRID_COLOR_R,
         self.FILE_EXPLORER_GRID_COLOR_G,
         self.FILE_EXPLORER_GRID_COLOR_B) = \
            self.rgb_string_into_tuple(colors["FILE_EXPLORER_GRID_COLOR"])

        self.BOTTOM_STRIP_TEXT_COLOR = self.config["fonts"]["font_colors"]["BOTTOM_STRIP_TEXT_COLOR"]

        (self.FILE_EXPLORER_ROW_HOVER_R,
         self.FILE_EXPLORER_ROW_HOVER_G,
         self.FILE_EXPLORER_ROW_HOVER_B) = \
            self.rgb_string_into_tuple(colors["FILE_EXPLORER_ROW_HOVER_COLOR"])
        
        (self.FILE_EXPLORER_DRAGGED_ROW_HOVER_R,
         self.FILE_EXPLORER_DRAGGED_ROW_HOVER_G,
         self.FILE_EXPLORER_DRAGGED_ROW_HOVER_B) = \
            self.rgb_string_into_tuple(colors["FILE_EXPLORER_DRAGGED_ROW_HOVER_COLOR"])


        ##
        # Fonts
        ##
        self.TEXT_FONT = self.config["fonts"]["TEXT_FONT"]  #'Segoe UI' / 'SF Pro' / 'Skia'

        font_sizes = self.config["fonts"]["font_sizes"]
        self.BOTTOM_TEXT_FONT_SIZE = font_sizes["BOTTOM_TEXT_FONT_SIZE"]
        self.TEXT_FONT_SIZE = font_sizes["TEXT_FONT_SIZE"]
        self.HEADER_TEXT_FONT_SIZE = font_sizes["HEADER_TEXT_FONT_SIZE"]
        self.TEXTBOX_FONT_SIZE = font_sizes["TEXTBOX_FONT_SIZE"]
        self.TEXT_FONT_SIZE = font_sizes["TEXT_FONT_SIZE"]
        
        font_colors = self.config["fonts"]["font_colors"]
        self.BASE_GREY_COLOR = font_colors["BASE_GREY_COLOR"]
        self.WINDOWS_FILE_EXPLORER_BLUE = font_colors["WINDOWS_FILE_EXPLORER_BLUE"]
        self.FILE_EXPLORER_FONT_COLOR_OTHER_COLS_R, self.FILE_EXPLORER_FONT_COLOR_OTHER_COLS_G, self.FILE_EXPLORER_FONT_COLOR_OTHER_COLS_B = \
            self.rgb_string_into_tuple(font_colors["FILE_EXPLORER_FONT_COLOR_OTHER_COLS"])
        
        self.FILE_EXPLORER_FONT_COLOR = font_colors["FILE_EXPLORER_FONT_COLOR"]
        self.LEFT_PANE_FONT_COLOR = font_colors["LEFT_PANE_FONT_COLOR"]
        self.FILE_EXPLORER_HEADER_FONT_COLOR = font_colors["FILE_EXPLORER_HEADER_FONT_COLOR"]
        
        font_row_heights = self.config["fonts"]["font_row_heights"]
        self.FILE_EXPLORER_ROW_HEIGHT = font_row_heights["FILE_EXPLORER_ROW_HEIGHT"]
        self.FAVORITES_ROW_HEIGHT = font_row_heights["FAVORITES_ROW_HEIGHT"]
        self.TREE_ROW_HEIGHT = font_row_heights["TREE_ROW_HEIGHT"]
        
        self.DATE_FORMAT = self.config["DATE_FORMAT"]
        

        
        
        self.FAVORITES_TITLE = self.config["FAVORITES_TITLE"]
        self.FILE_EXPLORER_FILENAME_COL_NAME = self.config["FILE_EXPLORER_FILENAME_COL_NAME"]
        self.SELECTION_COLOR = colors["selection_colors"]["SELECTION_COLOR"]
        self.FILE_EXPLORER_SELECTION_FONT_COLOR = colors["selection_colors"]["FILE_EXPLORER_SELECTION_FONT_COLOR"]
        self.FILE_EXPLORER_TEXT_COLOR_OTHER_COLS = colors["selection_colors"]["FILE_EXPLORER_TEXT_COLOR_OTHER_COLS"]
        
        
        self.SCROLLBAR_COLOR = self.config["scrollbar"]["SCROLLBAR_COLOR"]
        self.SCROLLBAR_BACKGROUND_COLOR = self.config["scrollbar"]["SCROLLBAR_BACKGROUND_COLOR"]
        self.SCROLLBAR_THICKNESS = self.config["scrollbar"]["SCROLLBAR_THICKNESS"]


        self.WINDOW_WIDTH = self.config["WINDOW_WIDTH"]
        self.WINDOW_HEIGHT = self.config["WINDOW_HEIGHT"]
        self.TOP_TOOLBAR_HEIGHT = self.config["TOP_TOOLBAR_HEIGHT"]
        self.BOTTOM_TOOLBAR_HEIGHT = self.config["BOTTOM_TOOLBAR_HEIGHT"]
        self.DEFAULT_PATH = self.config['DEFAULT_PATH']
        self.EXTENSION_ICONS_DIR = os.path.join(ICONS_DIR, 'extension_icons')
        self.FILE_EXPLORER_ALTERNATING_ROW_COLORS = self.config["FILE_EXPLORER_ALTERNATING_ROW_COLORS"]
        self.FILE_EXPLORER_SHOW_ROW_NUMBERS = self.config["FILE_EXPLORER_SHOW_ROW_NUMBERS"]
        self.FILE_EXPLORER_WIDTH = self.config['FILE_EXPLORER_WIDTH']
        self.LEFT_PANE_WIDTH = self.config['LEFT_PANE_WIDTH']
        self.FILE_EXPLORER_COL_WIDTH_1 = self.config['FILE_EXPLORER_COL_WIDTH_1']
        self.FILE_EXPLORER_COL_WIDTH_2 = self.config['FILE_EXPLORER_COL_WIDTH_2']
        self.FILE_EXPLORER_COL_WIDTH_3 = self.config['FILE_EXPLORER_COL_WIDTH_3']
        self.FILE_EXPLORER_COL_WIDTH_4 = self.config['FILE_EXPLORER_COL_WIDTH_4']
        self.BACKWARD_ICON_NAME = self.config["icons"]["BACKWARD_ICON_NAME"]
        self.FORWARD_ICON_NAME = self.config["icons"]["FORWARD_ICON_NAME"]
        self.UP_ICON_NAME = self.config["icons"]["UP_ICON_NAME"]
        self.DOWN_ICON_NAME = self.config["icons"]["DOWN_ICON_NAME"]
        self.RIGHT_ARROWHEAD_ICON_NAME = self.config["icons"]["RIGHT_ARROWHEAD_ICON_NAME"]
        self.FOLDER_ICON_NAME = self.config["icons"]["FOLDER_ICON_NAME"]
        self.FILE_ICON_NAME = self.config["icons"]["FILE_ICON_NAME"]
        self.FAVORITES_ICON = self.config["icons"]['FAVORITES_ICON']
        self.FAVORITES_DESKTOP_ICON = self.config["icons"]['FAVORITES_DESKTOP_ICON']
        self.FAVORITES_DOWNLOADS_ICON = self.config["icons"]['FAVORITES_DOWNLOADS_ICON']
        self.FAVORITES_DOCUMENTS_ICON = self.config["icons"]['FAVORITES_DOCUMENTS_ICON']
        self.BASIC_FAVORITES_DICT = self.config["BASIC_FAVORITES_DICT"]
        self.NEW_FOLDER_NAME_TEMPLATE = self.config["NEW_FOLDER_NAME_TEMPLATE"]
        self.PAGE_DOWN_UP_NUM_ROWS = self.config["PAGE_DOWN_UP_NUM_ROWS"]
        self.DEFAULT_TEXT_INDENT = self.config["DEFAULT_TEXT_INDENT"]




        self.rgb_attribute_names = ["SCROLLBAR_COLOR"
                                    , "SCROLLBAR_BACKGROUND_COLOR"
                                    , "BASE_GREY_COLOR"
                                    , "FILE_EXPLORER_FONT_COLOR"
                                    , "FILE_EXPLORER_FONT_COLOR_OTHER_COLS"
                                    , "FILE_EXPLORER_HEADER_FONT_COLOR"
                                    , "LEFT_PANE_FONT_COLOR"
                                    , "WINDOWS_FILE_EXPLORER_BLUE"
                                    , "SELECTION_COLOR"
                                    , "FILE_EXPLORER_SELECTION_FONT_COLOR"
                                    , "FILE_EXPLORER_TEXT_COLOR_OTHER_COLS"
                                    , "FILE_EXPLORER_ROW_HOVER_COLOR"
                                    , "FILE_EXPLORER_DRAGGED_ROW_HOVER_COLOR"
                                    , "LEFT_PANE_BACKGROUND_COLOR"
                                    , "FILE_EXPLORER_HEADER_COLOR"
                                    , "FILE_EXPLORER_BACKGROUND_COLOR"
                                    , "FILE_EXPLORER_ALTERNATE_BACKGROUND_COLOR"
                                    , "TOOLBAR_BACKGROUND_COLOR"
                                    , "FILE_EXPLORER_GRID_COLOR"]

        self.rgb_attribute_rgb_categories = ["FILE_EXPLORER_FONT_COLOR_OTHER_COLS",
                                             "FILE_EXPLORER_GRID_COLOR",
                                             "FILE_EXPLORER_ROW_HOVER_COLOR",
                                             "FILE_EXPLORER_DRAGGED_ROW_HOVER_COLOR"]

        self.FOLDERS_ALWAYS_ABOVE_FILES = self.config["FOLDERS_ALWAYS_ABOVE_FILES"]
        self.SHOW_FAVORITES_TITLE = self.config["SHOW_FAVORITES_TITLE"]


    # Y/N features
    @property
    def FOLDERS_ALWAYS_ABOVE_FILES(self):
        return self._FOLDERS_ALWAYS_ABOVE_FILES

    @FOLDERS_ALWAYS_ABOVE_FILES.setter
    def FOLDERS_ALWAYS_ABOVE_FILES(self, value):
        if value in ['Y', 'y']:
            self._FOLDERS_ALWAYS_ABOVE_FILES = True
        else:
            self._FOLDERS_ALWAYS_ABOVE_FILES = False

    @property
    def SHOW_FAVORITES_TITLE(self):
        return self._SHOW_FAVORITES_TITLE

    @SHOW_FAVORITES_TITLE.setter
    def SHOW_FAVORITES_TITLE(self, value):
        if value in ['Y', 'y']:
            self._SHOW_FAVORITES_TITLE = True
        else:
            self._SHOW_FAVORITES_TITLE = False

    @property
    def SHOW_HIDDEN_ITEMS(self):
        return self._SHOW_HIDDEN_ITEMS

    @SHOW_HIDDEN_ITEMS.setter
    def SHOW_HIDDEN_ITEMS(self, value):
        if value in ['Y', 'y']:
            self._SHOW_HIDDEN_ITEMS = True
        else:
            self._SHOW_HIDDEN_ITEMS = False

    @property
    def FILE_EXPLORER_SHOW_ROW_NUMBERS(self):
        return self._FILE_EXPLORER_SHOW_ROW_NUMBERS

    @FILE_EXPLORER_SHOW_ROW_NUMBERS.setter
    def FILE_EXPLORER_SHOW_ROW_NUMBERS(self, value):
        if value in ['Y', 'y']:
            self._FILE_EXPLORER_SHOW_ROW_NUMBERS = True
        else:
            self._FILE_EXPLORER_SHOW_ROW_NUMBERS = False

    @property
    def FILE_EXPLORER_ALTERNATING_ROW_COLORS(self):
        return self._FILE_EXPLORER_ALTERNATING_ROW_COLORS

    @FILE_EXPLORER_ALTERNATING_ROW_COLORS.setter
    def FILE_EXPLORER_ALTERNATING_ROW_COLORS(self, value):
        if value in ['Y', 'y']:
            self._FILE_EXPLORER_ALTERNATING_ROW_COLORS = True
        else:
            self._FILE_EXPLORER_ALTERNATING_ROW_COLORS = False


    @property
    def default_config(self):
        return {
            "DEFAULT_PATH": os.path.expanduser("~/Desktop"),
            "FILE_EXPLORER_ALTERNATING_ROW_COLORS": 'N',
            "FILE_EXPLORER_SHOW_ROW_NUMBERS": "N",
            "FOLDERS_ALWAYS_ABOVE_FILES": "Y",
            "SHOW_HIDDEN_ITEMS": "N",
            "scrollbar": {
                "SCROLLBAR_COLOR": "rgb(200, 207, 210)",
                "SCROLLBAR_BACKGROUND_COLOR": "rgb(250, 250, 250)",
                "SCROLLBAR_THICKNESS": 10
            },
            "fonts": {
                "TEXT_FONT": "Helvetica",
                "font_sizes": {
                    "BOTTOM_TEXT_FONT_SIZE": 12,
                    "TEXT_FONT_SIZE": 14,
                    "HEADER_TEXT_FONT_SIZE": 13,
                    "TEXTBOX_FONT_SIZE": 13,
                },
                "font_colors": {
                    "BASE_GREY_COLOR": "rgb(236, 236, 236)",
                    "FILE_EXPLORER_FONT_COLOR": "rgb(1, 1, 1)",
                    "FILE_EXPLORER_FONT_COLOR_OTHER_COLS": "rgb(130, 130, 130)",
                    "FILE_EXPLORER_HEADER_FONT_COLOR": "rgb(107, 114, 123)",
                    "LEFT_PANE_FONT_COLOR": "rgb(0, 0, 0)",
                    "WINDOWS_FILE_EXPLORER_BLUE": "rgb(25, 118, 214)",
                    "BOTTOM_STRIP_TEXT_COLOR": "rgb(100, 100, 100)"
                },
                "font_row_heights": {
                    "FILE_EXPLORER_ROW_HEIGHT": 22,
                    "FAVORITES_ROW_HEIGHT": 28,
                    "TREE_ROW_HEIGHT": 25
                }
              },
            "colors": {
                "selection_colors": {
                    "SELECTION_COLOR": "rgb(206, 232, 255)",
                    "FILE_EXPLORER_SELECTION_FONT_COLOR": "rgb(1, 1, 1)",
                    "FILE_EXPLORER_TEXT_COLOR_OTHER_COLS": "rgb(130, 130, 130)"
                },
                "FILE_EXPLORER_ROW_HOVER_COLOR": "rgb(240, 240, 240)",
                "FILE_EXPLORER_DRAGGED_ROW_HOVER_COLOR": "rgb(140, 200, 240)",
                "LEFT_PANE_BACKGROUND_COLOR": "rgb(255, 255, 255)",
                "FILE_EXPLORER_HEADER_COLOR": "rgb(255, 255, 255)",
                "FILE_EXPLORER_BACKGROUND_COLOR": "rgb(255, 255, 255)",
                "FILE_EXPLORER_ALTERNATE_BACKGROUND_COLOR": "rgb(255, 255, 255)",
                "TOOLBAR_BACKGROUND_COLOR": "rgb(255, 255, 255)",
                "FILE_EXPLORER_GRID_COLOR": "rgb(220, 220, 220)",
                "BOTTOM_STRIP_COLOR": "rgb(255, 255, 255)",
            },
            "DATE_FORMAT": "%Y/%m/%d %H:%M",
            "icons": {
                "BACKWARD_ICON_NAME": "_back_arrow_",
                "FORWARD_ICON_NAME": "_forward_arrow_",
                "UP_ICON_NAME": "_up_arrow_",
                "DOWN_ICON_NAME": "_down_arrowhead_",
                "RIGHT_ARROWHEAD_ICON_NAME": "_right_arrowhead_",
                "FOLDER_ICON_NAME": "_folder_",
                "FILE_ICON_NAME": "_file_",
                "FAVORITES_ICON": "_quick_access_",
                "FAVORITES_DESKTOP_ICON": "_desktop_",
                "FAVORITES_DOWNLOADS_ICON": "_downloads_",
                "FAVORITES_DOCUMENTS_ICON": "_document_"
            },
            "BASIC_FAVORITES_DICT": {
                "Name": [
                    "Desktop",
                    "Downloads",
                    "Documents"
                ],
                "Path": [
                    os.path.expanduser("~/Desktop"),
                    os.path.expanduser("~/Downloads"),
                    os.path.expanduser("~/Documents")
                ],
                "icon_full_path": [
                    os.path.join(ICONS_DIR, "_desktop_.png"),
                    os.path.join(ICONS_DIR, "_downloads_.png"),
                    os.path.join(ICONS_DIR, "_document_.png")
                ]
            },
            "NEW_FOLDER_NAME_TEMPLATE": "New Folder",
            "PAGE_DOWN_UP_NUM_ROWS": 10,
            "DEFAULT_TEXT_INDENT": 1,
            "FAVORITES_TITLE": "Bookmarks",
            "SHOW_FAVORITES_TITLE": "Y",
            "FILE_EXPLORER_FILENAME_COL_NAME": "Name",
            "keyboard_shortcuts": {
                "NEW_WINDOW": [
                    "Ctrl+N",
                    "Alt+N"
                ],
                "UP": [
                    "Ctrl+Up",
                    "Alt+Up"
                ],
                "ENTER": [
                    "Ctrl+Down",
                    "Alt+Down"
                ],
                "BACK": [
                    "Alt+Left",
                    "Ctrl+Left"
                ],
                "FORWARD": [
                    "Alt+Right",
                    "Ctrl+Right"
                ],
                "COPY_SELECTED_ITEMS_TO_CLIPBOARD": [
                    "Alt+C",
                    "Ctrl+C"
                ],
                "CUT": [
                    "Alt+X",
                    "Ctrl+X"
                ],
                "PASTE_FROM_CLIPBOARD": [
                    "Alt+V",
                    "Ctrl+V"
                ],
                "SELECT_ALL": [
                    "Alt+A",
                    "Ctrl+A"
                ],
                "EXTEND_SELECTION_UPWARDS": [
                    "Shift+Up"
                ],
                "EXTEND_SELECTION_DOWNWARDS": [
                    "Shift+Down"
                ],
                "PERMANENTLY_DELETE": [
                    "Shift+Del"
                ],
                "LAUNCH_FIND_WINDOW": [
                    "Alt+F",
                    "Ctrl+F"
                ],
                "UNDO_LAST_ACTION": [
                    "Alt+Z",
                    "Ctrl+Z"
                ],
                "REDO_LAST_UNDONE_ACTION": [
                    "Alt+Y",
                    "Ctrl+Y"
                ],
                "SELECT_ALL_UNTIL_END": [
                      "Shift+End"
                ],
                "SELECT_ALL_UNTIL_START": [
                      "Shift+Home"
                ]
            },
            "sorting": {
                "is_ascending_per_col": {
                    "0": 0,
                    "1": 1,
                    "2": 1,
                    "3": 0
                },
                "columns_sorting_order": [3, 0, 1, 2]
            },
            "FILE_EXPLORER_GRID_THICKNESS": 1,
            "WINDOW_WIDTH": 798,
            "WINDOW_HEIGHT": 758,
            "TOP_TOOLBAR_HEIGHT": 200,
            "BOTTOM_TOOLBAR_HEIGHT": 200,
            "FILE_EXPLORER_WIDTH": 692,
            "LEFT_PANE_WIDTH": 203,
            "FILE_EXPLORER_COL_WIDTH_1": 273,
            "FILE_EXPLORER_COL_WIDTH_2": 174,
            "FILE_EXPLORER_COL_WIDTH_3": 90,
            "FILE_EXPLORER_COL_WIDTH_4": 140
        }


    def get(self, k: str):
        if isinstance(k, str):
            if hasattr(self, k):
                return getattr(self, k)
            else:
                return self.config[k]
        elif isinstance(k, list):
            return self.access_dict_by_keys_path(self.config, k)


    def restore_default_keymap(self):
        from src.utils.os_utils import copy_all_files_from_to
        self.config['keyboard_shortcuts'] = self.default_config['keyboard_shortcuts']
        copy_all_files_from_to(BASE_ICONS_DIR, ICONS_DIR)


    # Updates both the config (dictionary) and the individual attribute if one exists
    # (e.g., self.DEFAULT_PATH)
    def set_attr(self, att: Union[str, list[str]], new_att_value):
        if isinstance(att, str):
            self._update_individual_attribute(att, new_att_value)
        else:
            self._update_individual_attribute(att[len(att)-1], new_att_value)

        self.update_config_dict(att, new_att_value)


    def _update_individual_attribute(self, att: str, new_att_value):
        if att == 'DEFAULT_PATH':
            if not os.path.exists(new_att_value):
                pass
        elif att in ['FILE_EXPLORER_SHOW_ROW_NUMBERS', 'FILE_EXPLORER_ALTERNATING_ROW_COLORS',
                     'FOLDERS_ALWAYS_ABOVE_FILES', 'SHOW_HIDDEN_ITEMS', 'SHOW_FAVORITES_TITLE']:
            if new_att_value not in ['Y', 'y', 'N', 'n']:
                pass
        elif att == 'DATE_FORMAT':
            try:
                datetime.datetime.today().strftime(str(new_att_value))
            except:
                pass
        elif att in self.rgb_attribute_names:
            if not is_string_rgb(new_att_value):
                pass

        if att in self.rgb_attribute_rgb_categories:
            rgb_colors = self.rgb_string_into_tuple(new_att_value)
            setattr(self, att + '_R', rgb_colors[0])
            setattr(self, att + '_G', rgb_colors[1])
            setattr(self, att + '_B', rgb_colors[2])

        elif hasattr(self, att):
            setattr(self, att, new_att_value)


    def update_config_dict(self, k: Union[str, list[str]], value):
        if isinstance(k, str):
            self.config[k] = value
        elif isinstance(k, list):
            if len(k) == 1:
                self.config[k[0]] = value
            elif len(k) == 2:
                self.config[k[0]][k[1]] = value
            elif len(k) == 3:
                self.config[k[0]][k[1]][k[2]] = value
            elif len(k) == 4:
                self.config[k[0]][k[1]][k[2]][k[3]] = value
            elif len(k) == 5:
                self.config[k[0]][k[1]][k[2]][k[3]][k[4]] = value
            elif len(k) == 6:
                self.config[k[0]][k[1]][k[2]][k[3]][k[4]][k[5]] = value
            elif len(k) == 7:
                self.config[k[0]][k[1]][k[2]][k[3]][k[4]][k[5]][k[6]] = value
            elif len(k) == 8:
                self.config[k[0]][k[1]][k[2]][k[3]][k[4]][k[5]][k[6]][k[7]] = value


    def revert_back_to_default_config(self):
        self.config = self.default_config
        self.save_config_to_file()
        self.upload_all_configurations_from_json(self.config_file_path)

    def save_config_to_file(self):
        json.dump(self.config, open(self.config_file_path, "w"), indent = 6)

    def access_dict_by_keys_path(self, d, keys_path: list[str]):
        d_pointer = d
        for k in keys_path:
            d_pointer = d_pointer[k]
        return d_pointer

    def rgb_string_into_tuple(self, rgb_string):
        return tuple(map(int, rgb_string.strip()[4:-1].split(',')))

    def get_user_styles_config(self):
        user_styles = [
            {"config_keys_path": ["DEFAULT_PATH"], "display_text": "Default path when opening new window"},
            {"config_keys_path": ["DATE_FORMAT"], "display_text": "Date format"},
            {"config_keys_path": ["SHOW_HIDDEN_ITEMS"], "display_text": "Show hidden items"},
            {"config_keys_path": ["NEW_FOLDER_NAME_TEMPLATE"], "display_text": "New folder name template"},
            {"config_keys_path": ["PAGE_DOWN_UP_NUM_ROWS"], "display_text": "Num rows up/down when clicking page-up / page-down"},
            {"config_keys_path": ["FOLDERS_ALWAYS_ABOVE_FILES"], "display_text": "Alywas show folders above files"},
            {"config_keys_path": ["SHOW_FAVORITES_TITLE"], "display_text": "Show bookmarks title row"},


            {"config_keys_path": ["fonts", "TEXT_FONT"], "display_text": "Font"},
            {"config_keys_path": ["fonts", "font_sizes", "TEXT_FONT_SIZE"], "display_text": "Table font size"},
            {"config_keys_path": ["fonts", "font_sizes", "HEADER_TEXT_FONT_SIZE"], "display_text": "Table header font size"},
            {"config_keys_path": ["fonts", "font_sizes", "TEXTBOX_FONT_SIZE"], "display_text": "Path textbox font size"},

            {"config_keys_path": ["fonts", "font_colors", "FILE_EXPLORER_FONT_COLOR"], "display_text": "Table font color - 1st column"},
            {"config_keys_path": ["fonts", "font_colors", "FILE_EXPLORER_FONT_COLOR_OTHER_COLS"], "display_text": "Table font color -  columns 2 to 4"},
            {"config_keys_path": ["fonts", "font_colors", "FILE_EXPLORER_HEADER_FONT_COLOR"], "display_text": "Table header font color"},
            {"config_keys_path": ["colors", "selection_colors", "SELECTION_COLOR"], "display_text": "Table selection color"},
            {"config_keys_path": ["colors", "selection_colors", "FILE_EXPLORER_SELECTION_FONT_COLOR"], "display_text": "Table selection font color - 1st column"},
            {"config_keys_path": ["colors", "selection_colors", "FILE_EXPLORER_TEXT_COLOR_OTHER_COLS"], "display_text": "Table selection font color - columns 2 to 4"},
            {"config_keys_path": ["colors", "FILE_EXPLORER_ROW_HOVER_COLOR"], "display_text": "Table row hover color"},
            {"config_keys_path": ["colors", "FILE_EXPLORER_DRAGGED_ROW_HOVER_COLOR"], "display_text": "Table dragged row hover color"},
            {"config_keys_path": ["colors", "FILE_EXPLORER_HEADER_COLOR"], "display_text": "Table header color"},
            {"config_keys_path": ["colors", "FILE_EXPLORER_BACKGROUND_COLOR"], "display_text": "Table background color"},
            {"config_keys_path": ["colors", "BOTTOM_STRIP_COLOR"], "display_text": "Bottom strip color"},
            {"config_keys_path": ["fonts", "font_colors", "BOTTOM_STRIP_TEXT_COLOR"], "display_text": "Bottom strip font color"},
            {"config_keys_path": ["fonts", "font_sizes", "BOTTOM_TEXT_FONT_SIZE"], "display_text": "Bottom strip font size"},
            {"config_keys_path": ["colors", "BOTTOM_STRIP_COLOR"], "display_text": "Bottom strip color"},
            {"config_keys_path": ["FILE_EXPLORER_ALTERNATING_ROW_COLORS"], "display_text": "Use alternating row colors in table"},
            {"config_keys_path": ["FILE_EXPLORER_SHOW_ROW_NUMBERS"], "display_text": "Show line numbers in table"},
            {"config_keys_path": ["colors", "FILE_EXPLORER_ALTERNATE_BACKGROUND_COLOR"], "display_text": "Table alternate background color"},

            {"config_keys_path": ["colors", "LEFT_PANE_BACKGROUND_COLOR"], "display_text": "Left pane background color"},
            {"config_keys_path": ["fonts", "font_colors", "LEFT_PANE_FONT_COLOR"], "display_text": "Left pane font color"},
            {"config_keys_path": ["fonts", "font_row_heights", "FILE_EXPLORER_ROW_HEIGHT"], "display_text": "Table row height"},
            {"config_keys_path": ["fonts", "font_row_heights", "FAVORITES_ROW_HEIGHT"], "display_text": "Favorites row height"},
            {"config_keys_path": ["fonts", "font_row_heights", "TREE_ROW_HEIGHT"], "display_text": "Tree row height"},
            {"config_keys_path": ["colors", "TOOLBAR_BACKGROUND_COLOR"], "display_text": "Toolbar background color"},

            {"config_keys_path": ["scrollbar", "SCROLLBAR_COLOR"],
             "display_text": "Scrollbar color"},

            {"config_keys_path": ["scrollbar", "SCROLLBAR_THICKNESS"],
             "display_text": "Scrollbar thickness"},
        ]

        user_styles = [{'config_keys_path': s['config_keys_path'],
                        'Feature': s['display_text'],
                        'Value': self.access_dict_by_keys_path(self.config, s['config_keys_path']),
                        'value_type': type(self.access_dict_by_keys_path(self.config, s['config_keys_path'])).__name__
                        } for s in user_styles]

        return user_styles

    @property
    def FILE_EXPLORER_HEADER_STYLE(self):
        return """
            QHeaderView::section {
                background-color: """ + self.FILE_EXPLORER_HEADER_COLOR + """;
                border: none;
                font-family: '""" + self.TEXT_FONT + """';
                font-size: """+str(self.HEADER_TEXT_FONT_SIZE)+"""px;
                color: """ + self.FILE_EXPLORER_HEADER_FONT_COLOR + """;       /* Font color */
                padding-left: 5px;                                        /* Text indentation */
            }
            QHeaderView::section::first {
                padding-left: 7px;                                        /* Text indentation */
            }
            QHeaderView::section::middle {
                border-left: 1px solid rgb(200, 200, 200);
            }
            QHeaderView::section::last {
                border-left: 1px solid rgb(200, 200, 200);
            }
            """

    @property
    def FILE_EXPLORER_ROWS_STYLE(self):
        return """QHeaderView{background-color: transparent;
                              color: """ + self.FILE_EXPLORER_HEADER_FONT_COLOR + """;       /* Font color */
                }
                QHeaderView::section{background-color: transparent; 
                border-top: none; border-bottom: none;
                padding-left: 5px;}
                """

    @property
    def TABLE_CONTEXT_MENU_STYLE(self):
        return """
            QMenu {
                background: """ + self.BASE_GREY_COLOR + """;
                border: 1px solid lightgrey;
                border-radius: 4px;
                padding-top: 7px;
                padding-bottom: 7px;
                padding-left: 3px;
                padding-right: 3px;
            }
            QMenu::item:selected{
                background-color: rgb(0, 85, 127);    /* Color when hovered-on */
                color: rgb(255,255,255);              /* Font color when hovered-on */
            }
            QMenu::item {
                height: 20px;                         /* Row height */
                margin-left: 2px;
                margin-right: 5px;
                margin-top: 1px;
            }
            QMenu::right-arrow {
                height: 6px;
            }
            """

    @property
    def FAVORITES_TABLE_STYLE(self):
        return """
            QTableView {
              background-color: """ + self.LEFT_PANE_BACKGROUND_COLOR + """;         /* Overall background color, across the entire tree area */
              color: """ + self.LEFT_PANE_FONT_COLOR + """;                          /* Font color */
              selection-color: """ + self.LEFT_PANE_FONT_COLOR + """;                /* Font color when selecting row */
              selection-background-color: """ + self.SELECTION_COLOR + """;          /* Selected row color */
              font-family: '""" + self.TEXT_FONT + """';
            }
            """


    @property
    def GAP_BETWEEN_TOOLBAR_AND_BELOW_STYLE(self):
        return """
            QSplitter{background-color: white;}
            QSplitter::handle:vertical{
                background-color: """ + self.TOOLBAR_BACKGROUND_COLOR + """;
                width: 0px;
                height: 0px;
            }
            """


    @property
    def TREE_STYLE(self):
        return """
            QTreeView {
              background: """ + self.LEFT_PANE_BACKGROUND_COLOR + """;               /* Overall background color, across the entire tree area */
              color: """ + self.LEFT_PANE_FONT_COLOR + """;                          /* Font color */
              selection-color: """ + self.LEFT_PANE_FONT_COLOR + """;                /* Font color when selecting row */
              selection-background-color: """ + self.SELECTION_COLOR + """;          /* Selected row color */
              border: none;
              padding-bottom: 10px;
              font-size: """+str(self.HEADER_TEXT_FONT_SIZE)+"""px;
              font-family: '""" + self.TEXT_FONT + """';
            }
            """

    @property
    def TRANSPARENT_QBUTTON(self):
        return """
                QPushButton{
                    border: none;
                    background-color: transparent;
                    color: black;   /* Font color */
                }
                QPushButton:pressed {
                    background-color: transparent;
                    color: transparent;   /* Font color */
                }
            """


    @property
    def TOOLBAR_STYLE(self):
        return """
            QToolBar{border: 1px solid transparent;
            background-color: """ + self.TOOLBAR_BACKGROUND_COLOR + """;
            margin-top: 4px;
            padding: -1px;
            };
            """


    @property
    def TEXTBOX_STYLE(self):
        return """
            QLineEdit{background-color: rgb(255,255,255);
            border:  1px solid lightgrey;
            padding-top: -6px;
            padding-left: 16px;
            margin-top: 4px
            };"""


    @property
    def TEXTBOX_NAVIGATOR_STYLE(self):
        return """
            QToolBar {
            background-color: rgb(255,255,255);
            padding-top: 1px;
            padding-bottom: 0px;
            border:  1px solid lightgrey;
            spacing: 0px;
            }
            QToolButton {
                margin: -6px;
                padding: """+ str(int((self.TEXTBOX_FONT_SIZE - 8) * 0.51)) +""", 0;           /* Top, Bottom (can change padding differentially) */
                border: none;
            }
            """
    # font-size: """ + str(TEXTBOX_FONT_SIZE) + """pt;
    # font-family: '""" + TEXT_FONT + """';

    @property
    def TEXTBOX_NAVIGATOR_BUTTON_STYLE(self):
        return """
                QPushButton{
                    border: none;
                    background-color: transparent;
                    padding-right: 0px;
                    padding-left: 0px;
                    padding-top: 0px;
                    padding-bottom: 0px;
                    color: black;   /* Font color */
                }
                QPushButton:pressed {
                    background-color: """ + self.WINDOWS_FILE_EXPLORER_BLUE + """;   /* Background color when pressed */
                    color: rgb(255,255,255);   /* Font color */
                }
            """


    @property
    def RENAME_TEXTBOX_STYLE(self):
        return """
            QLineEdit{
            color: """ + self.FILE_EXPLORER_SELECTION_FONT_COLOR + """;          /* Font color */
            background-color : white;
            selection-background-color: rgb(230, 230, 230);
            border:  1px solid lightgrey;
            margin-top: -5px;
            margin-bottom: -5px;
            font-weight: 100;
            };
            """


    @property
    def FILE_EXPLORER_STYLE(self):
        return """
                QTableView{background-color: """ + self.FILE_EXPLORER_BACKGROUND_COLOR + """;
                alternate-background-color: """ + self.FILE_EXPLORER_ALTERNATE_BACKGROUND_COLOR + """;
                selection-background-color: """ + self.SELECTION_COLOR + """;               /* Selected row color */
                color: """ + self.FILE_EXPLORER_FONT_COLOR + """;                           /* Font color */
                font-family: '""" + self.TEXT_FONT + """';                                  /* Replaced by self.setFont in FileExplorerTable.py */
                font-size: """ + str(self.TEXT_FONT_SIZE) + """px;
                gridline-color: transparent;
                padding-left: 0px;
                font-weight: 100;
                margin-right: 10px;
                }
                
                QTableView::item::selected{
                    selection-color: """ + self.FILE_EXPLORER_SELECTION_FONT_COLOR + """;   /* Selected row - font color */
                }
                QScrollBar::handle:vertical{
                    border-radius: 4px;
                    border-color: rgba(216, 216, 216, 75%);
                    border-width: 1px;
                    border-style: solid;
                    background-color: rgba(216, 216, 216, 75%);
                    min-height: 25px;
                    }
                """

    @property
    def VERTICAL_SCROLLBAR_STYLE(self):
        return """
            QScrollBar:vertical{border: none; background-color: rgb(255,255,255); width: """ + str(self.SCROLLBAR_THICKNESS) + """px; margin: 0px 0 0px 0; border-radius: 1px; background-color: """ + self.SCROLLBAR_BACKGROUND_COLOR + """; }
            QScrollBar::handle:vertical {background: """ + self.SCROLLBAR_COLOR + """; min-width: 20px;}
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {border: 0px solid transparent; height:0px; width: 0px;}
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical{margin: 0px 0px 0px 0px; height: 1px;}  /* Removes the little bottom and top arrow buttons */
            """

    @property
    def HORIZONTAL_SCROLLBAR_STYLE(self):
        return  """
            QScrollBar:horizontal{border: none; background-color: rgb(255,255,255); height: """ + str(self.SCROLLBAR_THICKNESS) + """px; margin: 0px 0 0px 0; border-radius: 1px; background-color: """ + self.SCROLLBAR_BACKGROUND_COLOR + """;}
            QScrollBar::handle:horizontal {background: """ + self.SCROLLBAR_COLOR + """; min-height: 20px;}
            QScrollBar::up-arrow:horizontal, QScrollBar::down-arrow:horizontal {border: 0px solid transparent; height:0px; width: 0px;}
            QScrollBar::sub-line:horizontal, QScrollBar::add-line:horizontal{margin: 0px 0px 0px 0px; width: 1px;}   /* Removes the little bottom and top arrow buttons */
            """

    @property
    def BOTTOM_TOOLBAR_STYLE(self):
        return """QToolBar{background-color: """ + self.BOTTOM_STRIP_COLOR + """;
        border-top: 1px solid transparent;}
        """

    @property
    def BOTTOM_TOOLBAR_TEXT_STYLE(self):
        return """QLabel {border: none;
                background-color: transparent;
                font-family: """ + self.TEXT_FONT + """;
                padding: 0px 0px 0px 10px;
                color: """ + self.BOTTOM_STRIP_TEXT_COLOR + """;}
                """
