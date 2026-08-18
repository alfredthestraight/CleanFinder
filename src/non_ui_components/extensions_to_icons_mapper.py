import os
import pickle
import pandas as pd


class ExtensionsToIconsMapper:
    """
    Used to map file extension to icon and icon paths
    """

    def __init__(self, mapping_df_path: str):
        self.mapping_df_path = mapping_df_path
        self.read_usable_extensions_from_disk()

    def read_usable_extensions_from_disk(self):
        if os.path.exists(self.mapping_df_path):
            with open(self.mapping_df_path, 'rb') as f:
                self._mapping_df = pickle.load(f)
        else:
            self._mapping_df = \
                pd.DataFrame(columns=['extension',
                                      'icon',
                                      'icon_full_path',
                                      'icon_full_path_exists',
                                      'app_path_name'])

    @property
    def USABLE_EXTENSIONS_AND_ICONS_DF(self) -> pd.DataFrame:
        return self._mapping_df

    def mapping_row_for_app(self, app_path: str) -> pd.DataFrame:
        """
        The row to record for `app_path` - its best icon if it has one, and otherwise a row
        with no icon at all. Some installed apps offer nothing to show (no document types,
        no icon file the scan can find), and the app still has to be remembered as the one
        that opens this file type.
        """
        from src.utils.os_utils import get_app_supported_extensions_and_icons
        app_extensions_and_icons_df = get_app_supported_extensions_and_icons(app_path)
        rows_with_an_icon = \
            app_extensions_and_icons_df[app_extensions_and_icons_df.icon_full_path_exists.eq(True)]
        if rows_with_an_icon.shape[0] > 0:
            return pd.DataFrame(rows_with_an_icon.iloc[0, :]).T
        if app_extensions_and_icons_df.shape[0] > 0:
            return pd.DataFrame(app_extensions_and_icons_df.iloc[0, :]).T
        return pd.DataFrame({'extension': None,
                             'icon': None,
                             'icon_full_path': None,
                             'icon_full_path_exists': False,
                             'app_path_name': app_path}, index=[0])

    def set_default_app_for_extension(self, file_path: str, app_path: str):
        """
        file_path --> file with the required extensions
        app_path --> the app that will be used to open files with extensions
        """
        from src.utils.os_utils import extract_extension_from_path
        new_row = self.mapping_row_for_app(app_path)

        file_extension = extract_extension_from_path(file_path)
        if file_extension in self._mapping_df.extension.values:
            self._mapping_df = self._mapping_df[
                self._mapping_df.extension != file_extension
            ]

        new_row.extension = file_extension
        self._mapping_df = pd.concat([self._mapping_df, new_row], axis=0)

        with open(self.mapping_df_path, 'wb') as f:
            pickle.dump(self._mapping_df, f)

    def extension_has_existing_icon(self, extension: str):
        if extension not in self._mapping_df.extension.values:
            return False
        else:
            return self._mapping_df[self._mapping_df.extension == extension].\
                icon_full_path_exists.iloc[0]

    def get_icon_path_for_extension(self, extension: str):
        return self._mapping_df[self._mapping_df.extension == extension].icon_full_path.iloc[0]

    def get_default_app_for_extension(self, extension: str):
        if not extension or extension not in self._mapping_df.extension.values:
            return None
        app = self._mapping_df[self._mapping_df.extension == extension].app_path_name.iloc[0]
        if pd.isna(app):
            return None
        return app
