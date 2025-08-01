from typing import Callable
import pandas as pd
import numpy as np
import pickle, os, shutil
from PySide6 import QtWidgets
from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import QFileDialog, QWidget,QLineEdit, QMainWindow, QLabel, QStackedWidget
from src.utils.os_utils import get_all_item_names_in_directory, delete_item, get_file_icon, \
    copy_all_files_from_to, get_all_items_in_path, extract_extension_from_path, create_file, \
    save_nsimage_as_png, save_app_icon_in_app_icons_dir, get_app_supported_extensions_and_icons, \
    get_all_app_names_in_path, get_file_apps_info
from src.shared.locations import APP_PATH, BASE_ICONS_DIR, ICONS_DIR, EXT_AND_ICONS_DF_PATH
from src.shared.vars import conf_manager as conf, logger as logger
from src.shared.locations import APPLICATION_DIRECTORIES


fonts_dir = '/System/Library/Fonts'
default_font = 'SegoeUI.TTF'
COMMONLY_USED_EXTENSIONS = \
[
 # Text
 'txt', 'log'

 # Documents
 'doc', 'docx', 'pdf',

 # Pictures
 'gif', 'jpeg', 'jpg', 'png', 'svg', 'bmp', 'ico', 'icns', 'tiff', 'tif',

 # HTML
 'html', 'htm', 'css', 'js', 'php', 'asp', 'aspx', 'jsp', 'xhtml', 'xml',

 # Excel
 'xls', 'xlsx', 'csv', 'tsv',

 'ods', 'odt',

 'ppt', 'pptx', 'pps',

  # Audio and video
 'mp4', 'mp3', 'mkv', 'mpeg', 'mpg', 'mov', 'avi', 'flv', 'wmv', 'wav', 'wma', 'ogg', 'webm', 'm4a', 'm4v', 'flac',

  # Archives

 'rar', 'zip', '7z', 'tar', 'gz', 'bz2', 'jar',

  # Programming languages
 'py',

'json', 'xml', 'yaml', 'yml', 'toml',

'otf', 'ttf',

 ]


def get_current_user_desktop_path() -> str:
    path = os.path.join(os.path.expanduser("~"), 'Desktop')
    if os.path.exists(path):
        return path
    else:
        return None


class ExtensionsToIconsMappingCreator:

    def __init__(self):
        self.temp_dir = os.path.join(APP_PATH, 'tmp')

    def run(self, ext_and_icons_df_path: pd.DataFrame) -> int:
        logger.info("ExtensionsToIconsMappingCreator.run")

        if not os.path.exists(self.temp_dir):
            os.mkdir(self.temp_dir)

        dirs_to_sample_for_icons = self.append_all_directories_to_sample_for_icons()
        example_files_with_unique_extensions = \
            self.get_example_files_with_unique_extensions(dirs_to_sample_for_icons)

        all_extensions_and_icons_df = self.get_all_extensions_and_icons_df()

        all_extensions_and_icons_df = \
            self.add_extensions_and_icons_based_on_existing_files(
                example_files_with_unique_extensions, all_extensions_and_icons_df
            )
        all_extensions_and_icons_df = self.filter_extensions_and_icons_df(all_extensions_and_icons_df)

        success = self.save_apps_icons(all_extensions_and_icons_df,
                                  example_files_with_unique_extensions)

        usable_extensions_and_icons_df = \
            all_extensions_and_icons_df[all_extensions_and_icons_df.icon_full_path_exists]

        with open(ext_and_icons_df_path, 'wb') as f:
            pickle.dump(usable_extensions_and_icons_df, f)

        if os.path.exists(self.temp_dir):
            delete_item(self.temp_dir)
        if os.path.exists(os.path.join(ICONS_DIR, 'tmp')):
            delete_item(os.path.join(ICONS_DIR, 'tmp'))

        return success


    def get_all_extensions_and_icons_df(self) -> pd.DataFrame:
        all_extensions_and_icons_df = \
            pd.DataFrame(columns=['extension', 'icon', 'icon_full_path', 'icon_full_path_exists',
                                  'app_path_name'])
        for app_dir in APPLICATION_DIRECTORIES:
            all_app_names = get_all_app_names_in_path(app_dir)
            all_extensions_and_icons_df = pd.concat([all_extensions_and_icons_df] +
                                                    [get_app_supported_extensions_and_icons(app)
                                                     for app in all_app_names], axis=0)
        all_extensions_and_icons_df.drop_duplicates(inplace=True)
        return all_extensions_and_icons_df


    def append_all_directories_to_sample_for_icons(self) -> list[str]:
        logger.info("installation.append_all_directories_to_sample_for_icons")
        dirs_to_sample_for_icons = []
        for dir in get_all_item_names_in_directory('/Users/'):
            if dir in ['.localized', 'Shared']:
                pass
            else:
                full_subdir_path = os.path.join('/Users', dir)
                if os.path.exists(full_subdir_path):
                    dirs_to_sample_for_icons.append(full_subdir_path)
                for subdir in ['Downloads', 'Desktop']:
                    full_subdir_path = os.path.join('/Users', dir, subdir)
                    if os.path.exists(full_subdir_path):
                        dirs_to_sample_for_icons.append(full_subdir_path)
        return dirs_to_sample_for_icons


    def get_example_files_with_unique_extensions(self, dirs_to_sample_for_icons) -> pd.DataFrame:
        """
        Basic idea is to sample multiple file extensions and register their icons
        """
        for ext in COMMONLY_USED_EXTENSIONS:
            create_file(os.path.join(self.temp_dir, 'tmp.' +  ext))

        files = []
        for folder in dirs_to_sample_for_icons + [self.temp_dir]:
            try:
                files_in_folder = get_all_items_in_path(folder, search_type=1)
            except:
                logger.info("get_example_files_with_unique_extensions - exception caught. Continuing...")
                continue
            if len(files_in_folder) == 0:
                return

            for f in files_in_folder:
                files.append(os.path.join(folder, f))

        files_df = pd.DataFrame({'filename': files})
        files_df['extension'] = files_df['filename'].apply(lambda x: extract_extension_from_path(x))
        files_df['row_num'] = files_df.groupby(['extension']).cumcount()+1
        files_df = files_df[files_df.row_num == 1]
        files_df.drop(columns=['row_num'], inplace=True)
        return files_df


    def save_apps_icons(self, exts_and_icons_df: pd.DataFrame,
                        example_files_with_unique_extensions: pd.DataFrame) -> int:
        success = 1
        tmp_icons_dir = os.path.join(ICONS_DIR, 'tmp')
        for r in exts_and_icons_df.iterrows():
            if not isinstance(r[1]['extension'], str):
                continue
            else:
                try:
                    save_app_icon_in_app_icons_dir(icon_full_path=r[1]['icon_full_path'],
                                                   extension=r[1]['extension'],
                                                   tmp_directory_path=tmp_icons_dir)
                except:
                    success = -1

        for r in example_files_with_unique_extensions.iterrows():
            if not isinstance(r[1]['filename'], str):
                continue
            else:
                try:
                    img = get_file_icon(r[1]['filename'])[1]
                    save_nsimage_as_png(img, os.path.join(ICONS_DIR, r[1]['extension']+'.png'))
                except:
                    success = -1

        return success


    def get_file_extension_and_default_app(self, file_path: str) -> pd.DataFrame:
        default_app, _ = get_file_apps_info(file_path)
        if default_app is None:
            return pd.DataFrame({'extension': None, 'app_path_name': None}, index=[0])
        default_app = str(default_app). \
                          replace('file://', '')[:-1]. \
                          replace('%20', ' ')
        extension = file_path.split('.')[-1]
        return pd.DataFrame({'extension': extension, 'app_path_name': default_app}, index=[0])


    def filter_duplicate_extensions(self, exts_and_icons_df: pd.DataFrame) -> pd.DataFrame:
        exts_and_icons_df_missing_extensions = \
            exts_and_icons_df[exts_and_icons_df.extension.isna()]
        exts_and_icons_df['tmp'] = 1
        exts_and_icons_df['tmp'] = exts_and_icons_df.groupby('extension').tmp.cumsum()
        exts_and_icons_df = exts_and_icons_df[exts_and_icons_df.tmp == 1]
        exts_and_icons_df.drop(columns=['tmp'], inplace=True)
        return pd.concat([exts_and_icons_df, exts_and_icons_df_missing_extensions], axis=0)


    def filter_invalid_extensions(self, exts_and_icons_df: pd.DataFrame) -> pd.DataFrame:
        return exts_and_icons_df[(~exts_and_icons_df.icon_full_path.isna()) &
                                 (~exts_and_icons_df.extension.isna()) &
                                 (~exts_and_icons_df.icon_full_path_exists.isna())]


    def filter_extensions_and_icons_df(self, exts_and_icons_df: pd.DataFrame) -> pd.DataFrame:
        exts_and_icons_df = self.filter_duplicate_extensions(exts_and_icons_df)
        exts_and_icons_df = self.filter_invalid_extensions(exts_and_icons_df)
        return exts_and_icons_df


    def add_extensions_and_icons_based_on_existing_files(self,
            example_files_with_unique_extensions: pd.DataFrame,
            all_extensions_and_icons_df: pd.DataFrame) -> pd.DataFrame:
        for i in range(example_files_with_unique_extensions.shape[0]):
            full_file_path, file_extension = tuple(example_files_with_unique_extensions.iloc[i, :])
            all_extensions_and_icons_df = \
                all_extensions_and_icons_df[all_extensions_and_icons_df.extension != file_extension]
            all_extensions_and_icons_df = \
                self.add_extension_to_mapping_df(full_file_path, all_extensions_and_icons_df)
        return all_extensions_and_icons_df


    def add_extension_to_mapping_df(self, file_with_extention_path: str,
                                    ext_n_icns_df: pd.DataFrame) -> pd.DataFrame:
        if '.' not in file_with_extention_path:
            return ext_n_icns_df

        extension_to_app = self.get_file_extension_and_default_app(file_with_extention_path)

        full_matches = pd.merge(ext_n_icns_df, extension_to_app,
                                on=['app_path_name', 'extension'], how='inner')
        if full_matches.shape[0] >= 1:
            # Exact match already appears in the ext_n_icns_df
            ext_n_icns_df = \
                ext_n_icns_df[ext_n_icns_df.extension != extension_to_app.extension.iloc[0]]
            new_row = pd.DataFrame(full_matches.iloc[0, :]).T
            return pd.concat([new_row, ext_n_icns_df], axis=0)

        if not extension_to_app.extension.isin(ext_n_icns_df.extension).iloc[0]:
            # Extension does not appear in ext_n_icns_df at all
            if extension_to_app.app_path_name.isin(ext_n_icns_df.app_path_name).iloc[0]:
                app_path_name = extension_to_app.app_path_name.iloc[0]
                new_row_candidates = ext_n_icns_df[ext_n_icns_df.app_path_name == app_path_name]
                new_row_candidates.extension = extension_to_app.extension.iloc[0]
                new_row = pd.DataFrame(
                    new_row_candidates.sort_values(by='icon_full_path_exists', ascending=False).iloc[0]
                ).T
                ext_n_icns_df = ext_n_icns_df[
                    (ext_n_icns_df.app_path_name != app_path_name) | (~ext_n_icns_df.extension.isna())
                ]
            else:
                nd = pd.DataFrame(np.nan, index=[0],
                                  columns=['icon', 'icon_full_path', 'icon_full_path_exists'])
                new_row = pd.concat([extension_to_app, nd], axis=1)
        else:
            # Extension appears in ext_n_icns_df, but with a different app
            existing_entries_with_app = ext_n_icns_df[
                ext_n_icns_df.app_path_name == extension_to_app.app_path_name.iloc[0]
            ]
            if existing_entries_with_app.icon_full_path_exists.fillna(False).sum() > 0:
                existing_entries_with_app = existing_entries_with_app[
                    existing_entries_with_app.icon_full_path_exists.fillna(False)
                ]
            nd = pd.DataFrame(existing_entries_with_app.
                              drop(columns=['extension', 'app_path_name']).iloc[0, :])
            new_row = pd.concat([extension_to_app, nd.T.reset_index(drop=True)],
                                axis=1).loc[:, ext_n_icns_df.columns.values]
        ext_n_icns_df = \
            ext_n_icns_df[ext_n_icns_df.extension != extension_to_app.extension.iloc[0]]
        return pd.concat([ext_n_icns_df, new_row], axis=0)




class InstallationThread(QThread):
    """
    Uses a thread to create the extensions to icons mapping & to copy the default font to the
    machine's fonts directory
    """

    finished = Signal(int)  # Signal emitted when copying is complete

    def __init__(self, should_reset_file_path: str):
        super().__init__()
        self.currently_running = False
        self.should_reset_file_path = should_reset_file_path

    def run(self):
        ext_to_icon_map_creator = ExtensionsToIconsMappingCreator()
        success = ext_to_icon_map_creator.run(EXT_AND_ICONS_DF_PATH)
        if success < 0:
            self.finished.emit(success)
        try:
            shutil.move(os.path.join(os.getcwd(), 'resources', default_font),
                        os.path.join(fonts_dir, default_font))
        except:
            pass
        try:
            shutil.move(os.path.join(os.getcwd(), 'resources', default_font),
                        os.path.join(fonts_dir, 'Supplemental', default_font))
        except:
            pass
        self.make_should_reset_false(self.should_reset_file_path)
        copy_all_files_from_to(BASE_ICONS_DIR, ICONS_DIR)
        self.finished.emit(success)

    def make_should_reset_false(self, should_reset_file_path: str):
        if os.path.exists(should_reset_file_path):
            f = open(should_reset_file_path, "w")
            f.write("0")    # Write inside file
            f.close()


class InstallationUiWidget(QMainWindow):

    def __init__(self, should_reset_file_path: str, on_ok_callback: Callable):
        super().__init__()
        self.on_ok_callback = on_ok_callback
        self.w = QWidget()
        self.setWindowTitle("Setup")

        self.installing_now_w = self.create_installing_now_widget()
        self.installation_complete_w = self.create_installation_complete_widget()

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.installing_now_w)
        self.stacked_widget.addWidget(self.installation_complete_w)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.stacked_widget)
        self.w.setLayout(layout)
        self.setCentralWidget(self.stacked_widget)

        self.thread = InstallationThread(should_reset_file_path)
        self.thread.finished.connect(self.show_installation_complete_ui)

    def run_installation(self):
        if not self.thread.currently_running:
            self.thread.currently_running = True
            self.thread.start()

    def create_installing_now_widget(self):
        installing_now = QWidget()
        installing_now_text = QLabel(installing_now)
        installing_now_text.setText("Installing. This may take a few minutes...")
        return installing_now

    def create_installation_complete_widget(self):
        installation_complete = QWidget()
        overall_layout = QtWidgets.QVBoxLayout()
        selection_layout = QtWidgets.QHBoxLayout()

        self.user_msg = QLabel(self)
        self.user_msg.setText("Please select a default root directory (you could change this at a later\ntime via the settings)")
        self.user_msg.setStyleSheet("QLabel { color : rgb(50, 50, 50);}")
        overall_layout.addWidget(self.user_msg)

        path_selection_btn = QtWidgets.QPushButton(self)
        desktop_path = get_current_user_desktop_path()
        self.text_input = QLineEdit(self)
        if desktop_path is not None:
            self.text_input.setText(desktop_path)
        else:
            self.text_input.setPlaceholderText("/MyPath")
        path_selection_btn.setText("Select")
        self.text_input.setStyleSheet("QLineEdit {background-color : white;}")

        self.accept_btn = QtWidgets.QPushButton(self)
        self.accept_btn.setText("Use selected path")
        self.accept_btn.setFixedWidth(150)
        self.accept_btn.setStyleSheet("QPushButton {background-color: rgb(0, 150, 250);"
                                      "border-color: white; color: white;}")

        selection_layout.addWidget(path_selection_btn)
        selection_layout.addWidget(self.text_input)
        overall_layout.addLayout(selection_layout)
        overall_layout.addWidget(self.accept_btn)

        path_selection_btn.clicked.connect(self.select_folder)
        self.accept_btn.clicked.connect(self.accept)

        installation_complete.setLayout(overall_layout)

        return installation_complete

    def show_installation_complete_ui(self):
        logger.info("show_installation_complete_ui")
        self.stacked_widget.setCurrentWidget(self.installation_complete_w)

    def select_folder(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.Directory)
        file_dialog.setOption(QFileDialog.Option.ShowDirsOnly)
        file_dialog.setDirectory(self.text_input.text())
        folder = file_dialog.getExistingDirectory()
        if os.path.exists(folder):
            self.text_input.setText(folder)
            self.accept_btn.setEnabled(True)

    def accept(self):
        logger.info("InstallationUiWidget.Accept")
        selected_path = self.text_input.text()
        if not os.path.exists(selected_path):
            self.user_msg.setText("Selected path does not exist. Please select a valid path")
        else:
            conf.set_attr('DEFAULT_PATH', selected_path)
            conf.save_config_to_file()
            self.on_ok_callback()
            self.close()

    def reject(self):
        pass
