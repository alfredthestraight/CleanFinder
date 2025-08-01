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

    def set_default_app_for_extension(self, file_path: str, app_path: str):
        """
        file_path --> file with the required extensions
        app_path --> the app that will be used to open files with extensions
        """
        from src.utils.os_utils import get_app_supported_extensions_and_icons
        app_extensions_and_icons_df = get_app_supported_extensions_and_icons(app_path)
        if app_extensions_and_icons_df.icon_full_path_exists.sum() == 0:
            new_row = app_extensions_and_icons_df.iloc[0, :]
        else:
            new_row = app_extensions_and_icons_df[app_extensions_and_icons_df.icon_full_path_exists].iloc[0, :]
        new_row = pd.DataFrame(new_row).T

        file_extension = file_path.split('.')[-1]
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
