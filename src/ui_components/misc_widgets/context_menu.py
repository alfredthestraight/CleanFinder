import os
from PySide6.QtWidgets import QMenu
from src.utils.utils import configure_context_menu, add_actions_to_context_menu
from src.utils.file_explorer_utils import change_items_names_case, open_file_as_app


class NewFileCreationWrapper:
    def __init__(self, file_exp_obj, filename: str = 'New_file', extension: str = ''):
        self.file_exp_obj = file_exp_obj
        self._filename_with_ext = filename + '.' + extension

    def __call__(self) -> int:
        return self.file_exp_obj.create_new_file(self._filename_with_ext)


class ContextMenuDelegate:

    def __init__(self, file_exp_obj):
        self.file_exp_obj = file_exp_obj

        # Persistent, pre-configured menu containers. configure_context_menu is the
        # expensive part (stylesheet parse + frameless/translucent window flags, which
        # force native popup-window creation on macOS), so it runs once here instead of
        # on every right-click. populate_context_menu only clears and re-adds the cheap
        # actions, reusing these same menus (and their already-created native windows).
        self.main_menu = QMenu(file_exp_obj)
        configure_context_menu(self.main_menu)  # keeps setFixedWidth(150)

        self.new_file_submenu = QMenu(file_exp_obj)
        configure_context_menu(self.new_file_submenu)
        self.new_file_submenu.setFixedWidth(180)
        self.new_file_submenu.setTitle("  New file")

        self.manipulate_name_submenu = QMenu(file_exp_obj)
        configure_context_menu(self.manipulate_name_submenu)
        self.manipulate_name_submenu.setFixedWidth(180)

    def reconfigure_styles(self):
        """Re-apply menu styling after a live theme/color change. The persistent menus
        keep the stylesheet captured at construction time, so this must be called from
        FileExplorerTable.refresh_all_configurations when the config changes."""
        for menu in (self.main_menu, self.new_file_submenu, self.manipulate_name_submenu):
            configure_context_menu(menu)
        # configure_context_menu resets width to 150; restore the submenu widths.
        self.new_file_submenu.setFixedWidth(180)
        self.manipulate_name_submenu.setFixedWidth(180)

    def _repopulate_new_file_submenu(self, new_file_types: list[str]):
        # NewFileCreationWrapper captures the table's current path, so the actions are
        # rebuilt on every open even though the submenu container is reused.
        self.new_file_submenu.clear()
        new_files_list = []
        for file_type in new_file_types:
            new_files_list.append(
                {"menu_item_name": file_type,
                 "associated_method": NewFileCreationWrapper(
                     self.file_exp_obj, extension=file_type)
                 })

        new_files_list.append(
            {"menu_item_name": "Default (no extension)",
             "associated_method": NewFileCreationWrapper(self.file_exp_obj)})

        add_actions_to_context_menu(self.new_file_submenu, self.file_exp_obj, new_files_list)

    def _repopulate_manipulate_name_submenu(self, submenu_title: str):
        self.manipulate_name_submenu.clear()
        self.manipulate_name_submenu.setTitle(submenu_title)
        add_actions_to_context_menu(self.manipulate_name_submenu, self.file_exp_obj,
                                    self.item_name_manipulations_list)

    @property
    def click_on_empty_space_actions_list(self):
        return [{"menu_item_name": "New folder",
                 "associated_method": self.file_exp_obj.create_new_dir},
                {"menu_item_name": "SEP"},  # Separating line
                {"menu_item_name": "Copy current path",
                 "associated_method": self.file_exp_obj.copy_current_path_to_clipboard},
                {"menu_item_name": "Paste",
                 "associated_method": self.file_exp_obj.paste_items_from_clipboard},
                {"menu_item_name": "Zip",
                 "associated_method":
                     lambda: self.file_exp_obj.zip_items(
                         self.file_exp_obj.currently_selected_filename_indices
                     )},
                {"menu_item_name": "Open path in terminal",
                 "associated_method": self.file_exp_obj.open_path_in_terminal},
                ]

    @property
    def item_name_manipulations_list(self):
        return [{"menu_item_name": "Add prefix/suffix",
                 "associated_method": self.file_exp_obj.add_prefix_or_suffix_to_items_names},
                {"menu_item_name": "Replace text in name(s)",
                 "associated_method": self.file_exp_obj.replace_substring_in_items_names},
                {"menu_item_name": "Delete text from name(s)",
                 "associated_method": self.file_exp_obj.delete_substring_from_items_names},
                {"menu_item_name": "To lowerchase",
                 "associated_method": change_items_names_case(self.file_exp_obj, 'lower')},
                {"menu_item_name": "To UPPERCASE",
                 "associated_method": change_items_names_case(self.file_exp_obj, 'upper')}]

    @property
    def copy_cut_paste_actions_list(self):
        return [{"menu_item_name": "SEP"},  # Separating line
                {"menu_item_name": "Copy",
                 "associated_method": self.file_exp_obj.copy_selected_items_to_clipboard},
                {"menu_item_name": "Copy full path",
                 "associated_method": self.file_exp_obj.copy_item_path_to_clipboard},
                {"menu_item_name": "Cut",
                 "associated_method": self.file_exp_obj.cut_item},
                {"menu_item_name": "Paste",
                 "associated_method": self.file_exp_obj.paste_items_from_clipboard}]

    def append_to_context_menu(self, menu: QMenu, actions_list: list[dict]):
        add_actions_to_context_menu(menu, self.file_exp_obj, actions_list)

    def populate_context_menu(self, clicked_on_empty_space: bool,
                              clicked_item_name: str,
                              items_list: list[str],
                              new_file_types: list[str] = ["txt", "xlsx", "docx"]):

        menu = self.main_menu
        menu.clear()

        self._repopulate_new_file_submenu(new_file_types)
        menu.addMenu(self.new_file_submenu)

        clicked_on_app = False
        if len(items_list) == 1:
            if items_list[0][-4:].lower() == '.app':
                clicked_on_app = True
    
        if clicked_on_empty_space:
            self.append_to_context_menu(menu, self.click_on_empty_space_actions_list)
    
        else:
            """ Functions bulk #1 - new dir / open with """
            actions_list = [{"menu_item_name": "New folder",
                             "associated_method": self.file_exp_obj.create_new_dir},
                            {"menu_item_name": "SEP"}]  # Separating line
            if len(items_list) == 1:
                actions_list.append({"menu_item_name": "Open",
                                     "associated_method": self.file_exp_obj.open_item_from_context_menu})
            self.append_to_context_menu(menu, actions_list)


            """ Functions bulk #2 - open with / open as app """
            if len(items_list) == 1:
                if clicked_on_app:
                    actions_list = [{"menu_item_name": "Open as app",
                                     "associated_method": open_file_as_app(items_list[0])}]
                else:
                    item_full_path = os.path.join(self.file_exp_obj.path, clicked_item_name)
                    actions_list = [{"menu_item_name": "Open with",
                                     "associated_method": \
                                         lambda: self.file_exp_obj.open_file_with_specified_app(item_full_path)}]
                self.append_to_context_menu(menu, actions_list)


            """ Functions bulk #3 - remove / rename """
            actions_list = [{"menu_item_name": "Delete",
                             "associated_method": self.file_exp_obj.remove_items},
                            {"menu_item_name": "SEP"},  # Separating line
                            {"menu_item_name": "Rename",
                             "associated_method": self.file_exp_obj.rename_item}]
            self.append_to_context_menu(menu, actions_list)


            """ Functions bulk #4 - string manipulation """
            submenu_item_name = "  Manipulate name" + ("" if len(items_list) == 1 else "s")
            self._repopulate_manipulate_name_submenu(submenu_item_name)
            menu.addMenu(self.manipulate_name_submenu)


            """ Functions bulk #5 - cut / copy / paste / zip / properties """
            actions_list = self.copy_cut_paste_actions_list + \
                           [{"menu_item_name": "Zip",
                             "associated_method": lambda: self.file_exp_obj.zip_items(
                                 self.file_exp_obj.currently_selected_filename_indices)},
                            {"menu_item_name": "SEP"},  # Separating line
                            {"menu_item_name": "Properties",
                             "associated_method": self.file_exp_obj.open_properties}
                            ]
            self.append_to_context_menu(menu, actions_list)

        return menu
