import time
import os
import pickle
import numpy as np

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMainWindow
from src.shared.locations import SYSTEM_ROOT_DIR, RESULTS_PATH
from src.shared.vars import conf_manager as conf, logger as logger
from src.utils.os_utils import get_clipboard_copied_files_paths, extract_filename_from_path, \
    get_all_items_in_path, extract_parent_path_from_path, dir_
from src.utils.pasting_items import TableWithRadioButtons, PastingManager
from src.non_ui_components.user_actions import UserActionsManager
from src.ui_components.ui import ui


class PastingDelegate:
    def __init__(self, ui_manager):
        self.ui_manager = ui_manager
        self.thread_runners = []
        self.pasting_manager = PastingManager(caller=self.ui_manager)

    def paste_items_from_clipboard(self, dest_path: str, delete_source_after_paste: bool):
        copied_file_paths = get_clipboard_copied_files_paths()
        if len(copied_file_paths) == 0:
            return
        else:
            self.paste_items(dest_path, copied_file_paths, delete_source_after_paste)

    def paste_items(self, dest_path: str, copied_file_paths, delete_source_after_paste: bool,
                    rename_item_names_in_dest: list[tuple[str, str]] = []):
        source_path = extract_parent_path_from_path(copied_file_paths[0])
        logger.info(f"paste_items --> source_path = {source_path}, dest_path = {dest_path}")
        if source_path == dest_path:
            logger.info(f"source_path == dest_path")
            # Do "keep both" for all items:
            self.paste_items_via_thread(
                copied_file_paths, dest_path, delete_source_after_paste,
                item_names_to_keep_both=[extract_filename_from_path(f) for f in copied_file_paths],
                rename_item_names_in_dest=rename_item_names_in_dest)
        else:
            conflicting_items = self.get_pasting_conflicts(dest_path, copied_file_paths)
            if len(conflicting_items) > 0:
                logger.info("has conflicts")
                self.tbl = TableWithRadioButtons(self, dest_path, conflicting_items,
                                                 copied_file_paths, delete_source_after_paste)
                self.tbl.show()
            else:
                logger.info("No conflicts")
                self.paste_items_via_thread(
                    copied_file_paths, dest_path, delete_source_after_paste,
                    rename_item_names_in_dest = rename_item_names_in_dest)

    def get_pasting_conflicts(self, dest_path: str, copied_file_paths: list[str]):
        items_in_dest = get_all_items_in_path(dest_path)
        items_to_paste = [os.path.basename(x) for x in copied_file_paths]
        return [x for x in items_to_paste if x in items_in_dest]

    def paste_items_via_thread(self, copied_file_paths: list[str],
                               dest_path: str,
                               delete_source_after_paste: bool,
                               rename_item_names_in_dest: list[tuple[str, str]] = [],
                               item_names_to_keep_both: list[str] = []):
        if len(copied_file_paths) == 0:
            return

        logger.info("paste_items_via_thread")
        source_dest_pairs = [(f,
                              os.path.join(dest_path, extract_filename_from_path(f)),
                              'keep_both' if extract_filename_from_path(f) in item_names_to_keep_both else 'replace')
                             for f in copied_file_paths]

        if len(rename_item_names_in_dest)>0:
            rename_item_names_in_dest = dict(rename_item_names_in_dest)
            source_dest_pairs = [(p[0],
                                  os.path.join(dest_path,
                                               rename_item_names_in_dest.get(
                                                   extract_filename_from_path(p[1]),
                                                   extract_filename_from_path(p[1]))
                                               ),
                                  p[2])
                                 for p in source_dest_pairs]

        self.pasting_manager.paste(copied_file_paths=copied_file_paths,
                                   dest_path=dest_path,
                                   delete_source_after_paste=delete_source_after_paste,
                                   when_done=self.ui_manager.refresh_all_uis,
                                   source_dest_pairs=source_dest_pairs,
                                   )

    def safetly_kill_all_threads(self):
        self.pasting_manager.safetly_kill_all_threads()


class UiWindowManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.windows = []
        self._cut_items_names = []
        self._cut_items_path = ''
        self.historical_actions = UserActionsManager()
        self.pasting_delegate = PastingDelegate(self)

        is_ascending_per_col = {}
        for k in conf.get(['sorting', 'is_ascending_per_col']).keys():
            is_ascending_per_col[int(k)] = conf.get(['sorting', 'is_ascending_per_col', k])
        columns_sorting_order = conf.get(['sorting', 'columns_sorting_order'])
        self.default_columns_sorting_scheme = \
            self.create_columns_sorting_scheme(columns_sorting_order,
                                               is_ascending_per_col)
        self.columns_sorting_scheme_per_path = \
            self.get_columns_sorting_scheme_per_path(
                os.path.join(RESULTS_PATH, 'columns_sorting_scheme_per_path')
            )

    def save_columns_sorting_scheme_per_path(self, path: str):
        if (os.path.exists(path)
                and hasattr(self, 'columns_sorting_scheme_per_path')):
            with open(os.path.join(path, 'columns_sorting_scheme_per_path'), 'wb') as f:
                pickle.dump(self.columns_sorting_scheme_per_path, f)

    def get_columns_sorting_scheme_per_path(self,
                                            column_order_per_path_file_path: str):
        logger.info(f"UiWindowManager.get_columns_sorting_scheme_per_path")
        if os.path.exists(column_order_per_path_file_path):
            with open(column_order_per_path_file_path, 'rb') as f:
                columns_sorting_scheme_per_path = pickle.load(f)
        else:
            columns_sorting_scheme_per_path = {}
            with open(column_order_per_path_file_path, 'wb') as f:
                pickle.dump(columns_sorting_scheme_per_path, f)

        return columns_sorting_scheme_per_path

    def create_columns_sorting_scheme(self, columns_sorting_order: list[int],
                                      is_ascending_per_col: bool):
        logger.info(f"UiWindowManager.create_columns_sorting_scheme")
        columns_sorting_mapping = []
        for s in [3, 2, 1, 0]:
            columns_sorting_mapping.append((columns_sorting_order[s],
                                            is_ascending_per_col[columns_sorting_order[s]]))
        return columns_sorting_mapping

    def refresh_all_uis(self):
        for w in self.windows:
            w.file_explorer._refresh_source_data()

    def reload_keyboard_shortcuts(self):
        for w in self.windows:
            w.reload_keyboard_shortcuts()

    def remove_paths_and_subpaths_from_browsing_histories(self, paths: list[str]):
        for w in self.windows:
            w.file_explorer.browsing_history_manager.remove_paths_and_subpaths_from_history(paths)

    def paste_items_from_clipboard(self, dest_path: str, delete_source_after_paste: bool):
        self.pasting_delegate.paste_items_from_clipboard(dest_path, delete_source_after_paste)

    def paste_items(self, dest_path: str, source_paths: list[str],
                    delete_source_after_paste: bool,
                    rename_item_names_in_dest: list[tuple[str, str]] = []):
        self.pasting_delegate.paste_items(dest_path=dest_path,
                                          copied_file_paths=source_paths,
                                          delete_source_after_paste=delete_source_after_paste,
                                          rename_item_names_in_dest=rename_item_names_in_dest)

    def keep_last_action(self, action):
        self.historical_actions.add_action(action)

    def undo_last_action(self):
        logger.info("UiWindowManager.undo_last_action")
        if self.historical_actions.undo_remaining():
            self.historical_actions.undo_last()

    def redo_last_undone_action(self):
        logger.info("UiWindowManager.redo_last_undone_action")
        if self.historical_actions.redo_remaining():
            self.historical_actions.redo_last()
        else:
            print("No actions to redo")

    def select_pasted_items_where_ui_is_in_path(self, path: str, items: list[str]):
        logger.info("UiWindowManager.select_pasted_items_where_ui_is_in_path")
        for w in self.windows:
            if w.file_explorer.path == path:
                w.file_explorer.clearSelection()
                w.file_explorer.delayed_select_rows_where_items_texts_are(items)

    def switch_ordering_of_file_explorer_column(self, col_ind: int, path: str):
        logger.info("UiWindowManager.switch_ordering_of_file_explorer_column")
        current_columns_sorting_scheme = \
            self.columns_sorting_scheme_per_path.get(path, self.default_columns_sorting_scheme)

        sorting_scheme_dict = dict(current_columns_sorting_scheme)
        sorting_scheme_dict[col_ind] = 1 - sorting_scheme_dict[col_ind]
        cols_sorting_order_rev = list(sorting_scheme_dict.keys().__reversed__())

        # If the column is already the last one to be sorted by - no need to shift things around.
        # Otherwise:
        if col_ind != cols_sorting_order_rev[0]:
            col_ind_current_position = \
                np.where([x == col_ind for x in cols_sorting_order_rev])[0][0]
            cols_sorting_order_rev[1:(col_ind_current_position+1)] = \
                cols_sorting_order_rev[0:col_ind_current_position]
        cols_sorting_order_rev[0] = col_ind

        self.columns_sorting_scheme_per_path[path] = \
            [(x, sorting_scheme_dict[x]) for x in cols_sorting_order_rev[::-1]]

    def get_columns_ordering_scheme(self, path: str = None):
        if path is None:
            return self.default_columns_sorting_scheme
        else:
            return self.columns_sorting_scheme_per_path.get(path,
                                                            self.default_columns_sorting_scheme)

    @property
    def cut_items_names(self):
        return self._cut_items_names

    @cut_items_names.setter
    def cut_items_names(self, newpaths: list[str]):
        self._cut_items_names = newpaths
        for w in self.windows:
            w.file_explorer.pandasModel.cut_items = self._cut_items_names

    @property
    def cut_items_path(self):
        return self._cut_items_path

    @cut_items_path.setter
    def cut_items_path(self, path: str):
        self._cut_items_path = path
        for w in self.windows:
            w.file_explorer.pandasModel.cut_items_path = self._cut_items_path

    def cancel_cut_items(self):
        self.cut_items_names = []
        for w in self.windows:
            w.file_explorer.pandasModel.cut_items = []

    def create_new_window(self, root_dir_path: str = SYSTEM_ROOT_DIR,
                          ydim: int = conf.WINDOW_HEIGHT,
                          file_explorer_width: int = conf.FILE_EXPLORER_WIDTH,
                          left_pane_width: int = conf.LEFT_PANE_WIDTH):
        new_ui = ui(encompassing_uis_manager=self,
                    root_dir_path=root_dir_path,
                    height=ydim,
                    file_explorer_width=file_explorer_width, left_pane_width=left_pane_width,
                    columns_ordering_scheme=self.get_columns_ordering_scheme(root_dir_path))
        new_ui.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        time.sleep(0.1)
        self.windows.append(new_ui)

        if len(self.windows) > 1:
            last_window = self.windows[len(self.windows)-1].splitter
            new_x = int(np.random.normal(loc=last_window.pos().x(), scale=75, size=1)) + 400
            new_y = int(np.random.normal(loc=last_window.pos().y(), scale=75, size=1)) + 400
            try:
                new_ui.move(new_x, new_y)
            except:
                pass

        new_ui.show()

        self.timer = QTimer()
        self.timer.timeout.connect(self.when_timer_finishes)
        self.timer.start(1)

    def when_timer_finishes(self):
        self.timer.stop()
        new_ui = self.windows[len(self.windows)-1]
        new_ui._allow_structure_updates = True

    def stop_monitoring(self):
        self.listener.stop()

    def start_monitoring(self):
        self.listener.start()

    def refresh_all_configurations(self):
        for w in self.windows:
            w.config_upper_toolbar_text_and_dims()
            w.config_bottom_toolbar_text_and_dims()
            w.refresh_all_configurations()

    def show_or_hide_left_panes(self):
        for w in self.windows:
            w.subsplitter.setSizes([conf.LEFT_PANE_WIDTH, conf.FILE_EXPLORER_WIDTH])

    def on_ui_close(self, ui):
        closed_window_ind = [i for i, w in enumerate(self.windows) if id(w) == id(ui)]
        closed_window = self.windows.pop(closed_window_ind[0])
        closed_window.setFixedHeight(0)

        self.windows = [w for w in self.windows if id(w) != id(ui)]
        if len(self.windows) == 0:
            self.pasting_delegate.safetly_kill_all_threads()
            conf.save_config_to_file()
            self.save_columns_sorting_scheme_per_path(RESULTS_PATH)
            print("Bye bye")
