import os.path
from src.utils.os_utils import move_item_from_dir1_to_dir2, move_to_trash, copy_item_to_dir, \
    extract_parent_path_from_path, extract_filename_from_path, create_file, is_dir, extract_extension_from_path
from abc import ABC, abstractmethod



class UserAction(ABC):
    def __init__(self, action_name):
        self.action_name = action_name

    @abstractmethod
    def undo(self):
        pass

    @abstractmethod
    def redo(self):
        pass

    # def undo_available(self):
    #     return True
    #
    # def redo_available(self):
    #     return True
    #
    # def cannot_undo_reason(self):
    #     return ""
    #
    # def cannot_redo_reason(self):
    #     return ""


class UserActionsManager(ABC):
    def __init__(self):
        self.actions = []
        self.actions_undone = []
        self.actions_redone = []

    def add_action(self, action):
        self.actions.append(action)
        self.actions_redone = []

    def undo_remaining(self):
        return len(self.actions) > 0

    def redo_remaining(self):
        return len(self.actions_undone) > 0

    def undo_last(self):
        if self.actions:
            last_action = self.actions.pop()
            # if not last_action.undo_available():
            #     prompt_message(title_text=f"Cannot undo",
            #                    message_text=last_action.cannot_undo_reason())
            # else:
            last_action.undo()
            self.actions_undone.append(last_action)

    def redo_last(self):
        if self.actions_undone:
            last_action = self.actions_undone.pop()
            # if not last_action.redo_available():
            #     prompt_message(title_text=f"Cannot redo",
            #                    message_text=last_action.cannot_redo_reason())
            # else:
            last_action.redo()
            self.actions.append(last_action)


class UserAction_MoveFile(UserAction):
    def __init__(self, filename, source_path, destination_path):
        super().__init__('Move_file')
        self.filename = filename
        self.source_path = source_path
        self.destination_path = destination_path

    def undo(self):
        if (os.path.exists(os.path.join(self.destination_path, self.filename)) and
                not os.path.exists(os.path.join(self.source_path, self.filename))):
            move_item_from_dir1_to_dir2(self.filename, self.source_path, self.dest_path)

    def redo(self):
        if (os.path.exists(os.path.join(self.source_path, self.filename)) and
                not os.path.exists(os.path.join(self.destination_path, self.filename))):
            move_item_from_dir1_to_dir2(self.filename, self.dest_path, self.source_path)


class UserAction_CreateItem(UserAction):
    def __init__(self, item_full_path):
        super().__init__('Create_item')
        self.item_full_path = item_full_path
        self.is_dir = is_dir(item_full_path)

    def undo(self):
        if os.path.exists(self.item_full_path):
            move_to_trash(self.item_full_path)

    def redo(self):
        if not os.path.exists(self.item_full_path):
            if self.is_dir:
                os.mkdir(self.item_full_path)
            else:
                create_file(self.item_full_path)



class UserAction_CopyPasteItem(UserAction):
    def __init__(self, filename, source_path, dest_path):
        super().__init__('Paste_item')
        self.filename = filename
        self.source_path = source_path
        self.dest_path = dest_path

    def undo(self):
        if os.path.exists(os.path.join(self.dest_path, self.filename)):
            move_to_trash(os.path.join(self.dest_path, self.filename))

    def redo(self):
        if (os.path.exists(os.path.join(self.source_path, self.filename)) and
                not os.path.exists(os.path.join(self.dest_path, self.filename))):
            copy_item_to_dir(os.path.join(self.source_path, self.filename),
                             self.dest_path)


class UserAction_RenameItem(UserAction):
    def __init__(self, path, prev_name, new_name):
        super().__init__('Rename_item')
        self.prev_name = os.path.join(path, prev_name)
        self.new_name = os.path.join(path, new_name)

    def undo(self):
        if not os.path.exists(self.prev_name):
            os.rename(self.new_name, self.prev_name)
        else:
            print("Item with that name already exists")

    def redo(self):
        if not os.path.exists(self.new_name):
            os.rename(self.prev_name, self.new_name)
        else:
            print("Item with that name already exists")



class UserAction_MoveFilesUsingThread(UserAction):
    def __init__(self, source_destination_pairs, uis_manager):
        super().__init__('move_items_using_file_explorer_thread')
        self.source_destination_pairs = source_destination_pairs
        self.uis_manager = uis_manager
        self.threads = []

    def undo(self):
        dest_items = [x[1] for x in self.source_destination_pairs]

        # In case the item was renamed during the move operation, we need to rename it back
        rename_item_names_in_dest = [
            (extract_filename_from_path(x[1]), extract_filename_from_path(x[0]))
            for x in self.source_destination_pairs
            if extract_filename_from_path(x[0]) != extract_filename_from_path(x[1])
        ]

        self.uis_manager.\
            paste_items(dest_path=extract_parent_path_from_path(self.source_destination_pairs[0][0]),
                        source_paths=dest_items,
                        delete_source_after_paste=True,
                        rename_item_names_in_dest=rename_item_names_in_dest)

    def redo(self):
        src_items = [x[0] for x in self.source_destination_pairs]
        self.uis_manager.\
            paste_items(dest_path=extract_parent_path_from_path(self.source_destination_pairs[0][1]),
                        source_paths=src_items,
                        delete_source_after_paste=True)

class UserAction_CopyPasteItemsUsingThread(UserAction):
    def __init__(self, source_destination_pairs, uis_manager):
        super().__init__('paste_items_using_file_explorer_thread')
        self.source_destination_pairs = source_destination_pairs
        self.dest_path = extract_parent_path_from_path(self.source_destination_pairs[0][1])
        self.uis_manager = uis_manager
        self.threads = []

    def undo(self):
        for item_path in [item[1] for item in self.source_destination_pairs]:
            if os.path.exists(item_path):
                move_to_trash(item_path)

    def redo(self):
        src_items = [x[0] for x in self.source_destination_pairs]
        self.uis_manager.\
            paste_items(dest_path=self.dest_path, source_paths=src_items,
                        delete_source_after_paste=False)



# class UserAction_RenameItem(UserAction):
#     def __init__(self, path: str, prev_to_new_name_map: tuple[str, str]):
#         super().__init__('Rename_item')
#         # self.prev_to_new_name_map = prev_to_new_name_map
#         self.path = path
#         self.prev_to_new_name_map = \
#             [(os.path.join(path, x[0]), os.path.join(path, x[1]))
#              for x in prev_to_new_name_map]
#
#     def undo_available(self):
#         items_cannot_rename = [x[1] for x in self.prev_to_new_name_map if os.path.exists(x[0])]
#         return len(items_cannot_rename) == 0
#
#     def redo_available(self):
#         items_cannot_rename = [x[0] for x in self.prev_to_new_name_map if os.path.exists(x[1])]
#         return len(items_cannot_rename) == 0
#
#     def cannot_undo_reason(self):
#         items_cannot_rename = [x[1] for x in self.prev_to_new_name_map if os.path.exists(x[0])]
#         return f"Cannot undo rename since items with previous name already exist in path {self.path})"
#
#     def cannot_redo_reason(self):
#         items_cannot_rename = [x[0] for x in self.prev_to_new_name_map if os.path.exists(x[1])]
#         return f"Cannot undo rename since items with previous name already exist in path {self.path}"
#
#     def undo(self):
#         for m in self.prev_to_new_name_map:
#             os.rename(m[1], m[0])
#
#
#     def redo(self):
#         for m in self.prev_to_new_name_map:
#             os.rename(m[0], m[1])

