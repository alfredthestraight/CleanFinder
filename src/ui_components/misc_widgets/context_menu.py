from src.utils.utils import single_run_qtimer
import os
from PySide6.QtWidgets import QMenu
from src.utils.os_utils import create_file, increment_max_item_name, get_all_item_names_in_directory
from src.utils.utils import configure_context_menu, add_actions_to_context_menu
from src.utils.file_explorer_utils import change_items_names_case, open_file_as_app
from src.non_ui_components.user_actions import UserAction_CreateItem


class NewFileCreationWrapper:
    def __init__(self, uis_manager, path: str = None, filename: str = 'New_file', extension: str = ''):
        self.uis_manager = uis_manager
        self.full_file_path = increment_max_item_name(
            get_all_item_names_in_directory(path), path, filename + '.' + extension)

    def __call__(self) -> int:
        success = create_file(self.full_file_path)
        self.uis_manager.keep_last_action(UserAction_CreateItem(self.full_file_path))
        single_run_qtimer(milliseconds=200, func=lambda: self.uis_manager.refresh_all_uis())
        return success


class ContextMenuDelegate:
    
    def __init__(self, file_exp_obj):
        self.file_exp_obj = file_exp_obj

    def create_sub_context_menu(self, submenu_title: str,
                                submenu_functionalities: list[dict]):
        sub_context_menu = QMenu(self.file_exp_obj)
        configure_context_menu(sub_context_menu)
        sub_context_menu.setFixedWidth(180)
        sub_context_menu.setTitle(submenu_title)
        add_actions_to_context_menu(sub_context_menu, self.file_exp_obj, submenu_functionalities)
        return sub_context_menu

    def create_new_file_submenu(self, new_file_types: list[str] = ["txt", "xlsx", "docx"]):
        new_files_list = []
        for file_type in new_file_types:
            new_files_list.append(
                {"menu_item_name": file_type,
                 "associated_method": NewFileCreationWrapper(
                     self.file_exp_obj.encompassing_uis_manager,
                     path=self.file_exp_obj.path, extension=file_type)
                 })

        new_files_list.append(
            {"menu_item_name": "Default (no extension)",
             "associated_method": NewFileCreationWrapper(
                     self.file_exp_obj.encompassing_uis_manager,
                     path=self.file_exp_obj.path
             )})

        return self.create_sub_context_menu("  New file", new_files_list)

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

        menu = QMenu(self.file_exp_obj)
        configure_context_menu(menu)
        
        new_file_contextMenu = self.create_new_file_submenu(new_file_types)
        menu.addMenu(new_file_contextMenu)
    
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
            menu.addMenu(
                self.create_sub_context_menu(submenu_item_name, self.item_name_manipulations_list)
            )


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
