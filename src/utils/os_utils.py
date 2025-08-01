import pandas as pd
from pathlib import Path
import os
import shutil
import icnsutil
import datetime
import plistlib

import numpy as np
import subprocess
from send2trash import send2trash
from os import listdir
from os.path import isfile, join
import LaunchServices as ls
from Foundation import (NSURL, NSURLLocalizedTypeDescriptionKey, NSURLEffectiveIconKey,
                        NSURLIsHiddenKey)
from AppKit import NSBitmapImageRep
import io
# See other item details available in:
# https://developer.apple.com/documentation/foundation/nsurlresourcekey
from PySide6.QtCore import QDir
from PySide6.QtWidgets import QApplication, QLabel, QFrame, QItemDelegate
from PIL import Image, ImageCms
pillow_profile = ImageCms.createProfile("sRGB")

from src.shared.vars import conf_manager as conf, extensions_to_icons_mapper, logger as logger
from src.shared.locations import SYSTEM_ROOT_DIR, ICONS_DIR
from src.utils.utils import get_max_integer_suffix_among_strings_with_prefix, \
    search_all_key_paths_in_dict



"""
File & path string manipulation/extraction functions
"""


def get_last_part_in_path(path: str) -> str:
    return Path(path).name


def parent_directory(directory_path: str) -> str:
    return str(Path(directory_path).parent.absolute())


def list_all_subpaths_in_path(full_path: str) -> list[str]:
    splt_path = full_path.split(os.sep)
    splt_path = [x for x in splt_path if x != '']
    all_subpaths = [SYSTEM_ROOT_DIR + os.sep.join(splt_path[0:x])
                    for x in range(1, len(splt_path)+1)]
    return all_subpaths


def resize_and_save_png_file(png_file_path: str, new_width=30, new_height=30):
    foo = Image.open(png_file_path)
    foo = foo.resize((new_width, new_height))
    foo.save(png_file_path, quality=95)


def extract_filename_from_path(path: str, include_extension: bool = True) -> str:
    if include_extension:
        return Path(path).name
    else:
        return Path(path).stem


def extract_extension_from_path(path: str) -> str:
    if Path(path).is_dir() or '.' not in str(path):
        return ''
    path_suff = str(path).split(os.sep)[-1:][0]
    extension = path_suff.split('.')[-1:][0]
    return extension


# E.g., "...Desktop/file.txt" -> "...Desktop"
def extract_parent_path_from_path(path: str) -> str:
    return Path(path).parent.__str__()


def is_dir(path: str) -> bool:
    return Path(path).is_dir()


def get_root_dir() -> str:
    return os.path.abspath(os.sep)


def is_root(path) -> bool:
    return path == SYSTEM_ROOT_DIR


def remove_extension_from_filename(filename: str) -> str:
    stripped_filename = filename.replace('.' + extract_extension_from_path(filename), '')
    if stripped_filename == '':
        return filename
    else:
        return stripped_filename


def is_subfolder_descendant_of_folder(subfolder: str, folder: str):
    return subfolder.startswith(folder + '/')


"""
Item sizes
"""


def folder_size(path: str = '.') -> int:
    total = 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += folder_size(entry.path)
    return total


def beautify_bytes_size(size_in_bytes: int) -> str:
    if size_in_bytes < 1024:
        return size_in_bytes, "bytes", f"{size_in_bytes} bytes"
    elif size_in_bytes < 1024**2:
        return size_in_bytes/1024, "KB", f"{size_in_bytes/1024:.0f} KB"
    elif size_in_bytes < 1024**3:
        return size_in_bytes/1024**2, "MB", f"{size_in_bytes/1024**2:.1f} MB"
    else:
        return size_in_bytes/1024**3, "GB", f"{size_in_bytes/1024**3:.1f} GB"


def get_item_size_pretty(fs) -> str:
    bytes = 0
    if isinstance(fs, str):
        fs = [fs]
    for f in fs:
        if os.path.isdir(f):
            bytes = bytes + get_folder_size_bytes(f)
        else:
            bytes = bytes + os.path.getsize(f)

    return beautify_bytes_size(bytes)



def get_folder_size_bytes(folder_path: str) -> int:
    total_size = 0
    stack = [folder_path]
    while stack:
        current_path = stack.pop()
        try:
            scandir = os.scandir(current_path)
        except:
            print(1)
        for entry in scandir:
            try:
                if entry.is_file():
                    total_size += os.path.getsize(entry.path)
                elif entry.is_dir():
                    stack.append(entry.path)
            except:
                print(1)
    return total_size


def size_bytes_to_string(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.0f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.1f} MB"
    else:
        return f"{size_bytes/1024**3:.1f} GB"


def size_string_to_bytes(size: str) -> float:
    size_num = float(size.split(' ')[0])
    size_scale = size.split(' ')[1]
    if size_scale == 'KB':
        return size_num * 1024
    elif size_scale == 'MB':
        return size_num * 1024**2
    elif size_scale == 'GB':
        return size_num * 1024**3
    else:
        return size_num


def get_path_size(path: str):
    return Path(path).stat().st_size




"""
Items info
"""

def get_file_type(file_path: str) -> str:
    url = NSURL.fileURLWithPath_(file_path)
    return str(url.getResourceValue_forKey_error_(None, NSURLLocalizedTypeDescriptionKey, None)[1])


def is_hidden(file_path: str) -> bool:
    url = NSURL.fileURLWithPath_(file_path)
    return url.getResourceValue_forKey_error_(None, NSURLIsHiddenKey, None)[1]


def get_file_apps_info(path: str, output_uti: bool = False):
    url = NSURL.fileURLWithPath_(path)
    if url is None:
        return None, None, None
    defaultApp = ls.LSGetApplicationForURL(url, ls.kLSRolesAll, None, None)[-1]
    allApps = ls.LSCopyApplicationURLsForURL(url, ls.kLSRolesAll)
    OSStatus, infos = ls.LSCopyItemInfoForURL(url, ls.kLSRequestAllInfo, None)
    if output_uti:  # UTI from extension
        uti = None
        if infos[3] is not None:
            uti = ls.UTTypeCreatePreferredIdentifierForTag(ls.kUTTagClassFilenameExtension,
                                                           infos[3],
                                                           ls.kUTTypeData)
        if uti is None:
            # No file extension, so try OSType
            typeString = ls.UTCreateStringForOSType(infos.filetype)
            if typeString is not None:
                uti = ls.UTTypeCreatePreferredIdentifierForTag(ls.kUTTagClassOSType,
                                                               typeString,
                                                               ls.kUTTypeData)
            else:
                uti = None
        return defaultApp, allApps, uti
    else:
        return defaultApp, allApps


def is_path_an_app(path: str) -> bool:
    return Path(path).is_dir() and path[-4:].lower() == '.app'


def get_item_date_modified(path: str) -> str:
    return datetime.datetime.fromtimestamp(os.path.getctime(path)).strftime(conf.DATE_FORMAT)


def is_read_only(path: str) -> bool:
    # Check if the file or folder is readable
    readable = os.access(path, os.R_OK)
    # Check if the file or folder is writable
    writable = os.access(path, os.W_OK)

    # If it's readable but not writable, it's read-only
    if readable and not writable:
        return True
    return False


"""
Icons
"""


def get_icon_names(paths_list: list[str]) -> pd.DataFrame:
    types = {}
    for x in paths_list:
        try:
            types[x] = get_type_as_icon_string(Path(x))
        except:
            pass
    return types


def extract_extensions_and_icons(x):
    if 'CFBundleTypeIconFile' in x.keys():
        if '.icns' not in x['CFBundleTypeIconFile']:
            x['CFBundleTypeIconFile'] = x['CFBundleTypeIconFile'] + '.icns'
        return (x['CFBundleTypeExtensions'], x['CFBundleTypeIconFile'])
    else:
        return x['CFBundleTypeExtensions']


def read_CFBundleIconFile(app_path: str):
    try:
        app_plist_path = os.path.join(app_path, 'Contents', 'Info.plist')
        with open(app_plist_path, "rb") as f:
            r = plistlib.load(f)
        # icon_file_name = search_all_key_paths_in_dict(r, 'CFBundleIconFile') + '.icns'
        CFBundleIconFile = r['CFBundleIconFile']
        if CFBundleIconFile[-5:] == '.icns':
            return os.path.join(app_path, 'Contents', 'Resources', r['CFBundleIconFile'])
        else:
            return os.path.join(app_path, 'Contents', 'Resources', r['CFBundleIconFile'] + '.icns')
    except:
        return None


def read_extensions_and_icons_from_CFBundleTypeExtensions(app_path_name: str):
    try:
        with open(os.path.join(app_path_name, 'Contents/Info.plist'), 'rb') as r:
            r = plistlib.loads(r.read(), fmt=None)
        value_data = search_all_key_paths_in_dict(r, 'CFBundleTypeExtensions')
        return [extract_extensions_and_icons(r[x[0]][x[1]]) for x in value_data]
    except:
        return []


def get_file_icon(file_path: str):
    url = NSURL.fileURLWithPath_(file_path)
    return url.getResourceValue_forKey_error_(None, NSURLEffectiveIconKey, None)


def get_type_as_icon_string(path: str) -> str:
    """
    Used to identify which icon is relevant to present next to the item
    Examples:
    '.../data.txt' -> 'txt'
    '.../myFolder' -> '_folder_'
    '.../myFile.some_strange_extension' -> '_file_'
    """
    if Path(path).is_dir():
        return conf.FOLDER_ICON_NAME
    extension = extract_extension_from_path(path)
    if extension not in set(extensions_to_icons_mapper.USABLE_EXTENSIONS_AND_ICONS_DF['extension']):
        return conf.FILE_ICON_NAME
    else:
        return extension


def nsimage_to_pil(ns_image):
    # Get NSBitmapImageRep representation of NSImage
    ns_image_data = ns_image.TIFFRepresentation()
    bitmap_image = NSBitmapImageRep.imageRepWithData_(ns_image_data)

    # Convert NSBitmapImageRep to raw bytes
    tiff_data = bitmap_image.TIFFRepresentation()

    # Use Pillow to read the TIFF bytes
    pil_image = Image.open(io.BytesIO(tiff_data))
    return pil_image


def save_nsimage_as_png(ns_image, path: str):
    pil_obj = nsimage_to_pil(ns_image)
    pil_obj = pil_obj.resize((30, 30))
    with open(path, 'wb') as f:
        pil_obj.save(f, 'PNG', icc_profile=ImageCms.ImageCmsProfile(pillow_profile).tobytes())


def save_app_icon_in_app_icons_dir(icon_full_path: str,
                                   extension: str,
                                   tmp_directory_path: str = None,
                                   delete_tmp_dir_after_completion: bool = False):
    logger.info("save_app_icon_in_app_icons_dir")
    if os.path.exists(icon_full_path):
        img = icnsutil.IcnsFile(icon_full_path)

        if tmp_directory_path is None:
            tmp_dir_path = os.path.join(ICONS_DIR, "tmp_123fadslfidasylkufydsak")
        else:
            tmp_dir_path = tmp_directory_path

        if not os.path.exists(tmp_dir_path):
            os.makedirs(tmp_dir_path)
        else:
            empty_folder(tmp_dir_path)

        img.export(tmp_dir_path, allowed_ext='png', recursive=True, convert_png=True)

        # In case of several icons under the same icns file:
        all_file_versions = [{'filename': f, 'size': get_path_size(os.path.join(tmp_dir_path, f))}
                             for f in get_all_item_names_in_directory(tmp_dir_path)]
        file_ver_df = pd.DataFrame(all_file_versions)
        file_ver_df['is_optimal_size'] = (file_ver_df['size'] > 800) & (file_ver_df['size'] < 2000)
        if file_ver_df['is_optimal_size'].sum() > 0:
            selected_file_version = file_ver_df[file_ver_df['is_optimal_size']].iloc[0, 0]
        else:
            selected_file_version = file_ver_df[file_ver_df['size'] == file_ver_df['size'].min()].\
                iloc[0, 0]

        shutil.copyfile(os.path.join(tmp_dir_path, selected_file_version),
                        os.path.join(ICONS_DIR, extension+'.png'))

    if delete_tmp_dir_after_completion and os.path.exists(tmp_dir_path):
        delete_item(tmp_dir_path)


def turn_extensions_and_icons_from_CFBundleTypeExtensions_to_df(extensions_and_icons_list):
    if len(extensions_and_icons_list) > 0:
        extensions_and_icons_flattened = []
        for x in extensions_and_icons_list:
            if isinstance(x, tuple):
                if len(x) == 2:
                    if len(x[0]) >= 2:
                        extensions_and_icons_flattened = \
                            extensions_and_icons_flattened + [(y, x[1]) for y in x[0]]
                    else:
                        extensions_and_icons_flattened.append((x[0][0], x[1]))
            elif isinstance(x, list):
                extensions_and_icons_flattened = (extensions_and_icons_flattened +
                                                  [(y, None) for y in x])
        df = pd.DataFrame(extensions_and_icons_flattened)
        df.columns = ['extension', 'icon']
        return df
    else:
        return pd.DataFrame(columns=['extension', 'icon'])


def get_app_supported_extensions_and_icons(app_path_name):
    extensions_and_icons = read_extensions_and_icons_from_CFBundleTypeExtensions(app_path_name)
    df = turn_extensions_and_icons_from_CFBundleTypeExtensions_to_df(extensions_and_icons)
    if df.shape[0] > 0:
        icon_exists_ind = df[df['icon'].apply(lambda x: x is not None)].index
        df.loc[icon_exists_ind, 'icon_full_path'] = \
            (df.loc[icon_exists_ind, :].
             apply(lambda x: os.path.join(app_path_name, 'Contents', 'Resources', x['icon']),
                   axis=1))
        if df.icon_full_path.dropna().shape[0] > 0:
            if len([x for x in df.icon_full_path.dropna() if 'BetterSnapTool' in x]) > 0:
                print(1)
        df.loc[icon_exists_ind, 'icon_full_path_exists'] = \
            df.loc[icon_exists_ind, 'icon_full_path'].apply(os.path.exists)
        df['app_path_name'] = app_path_name
        df.loc[:, 'icon_full_path_exists'].fillna(False, inplace=True)
        return df

    icon_path_ = read_CFBundleIconFile(app_path_name)
    if icon_path_ is not None:
        return pd.DataFrame(
                            {'extension': np.nan,
                             'icon': icon_path_.split('/')[-1],
                             'icon_full_path': icon_path_,
                             'icon_full_path_exists': icon_path_ is not None,
                             'app_path_name': app_path_name}, index=[0])

    app_name = app_path_name.split(os.sep)[-1].replace('.app', '').replace(' ', '')
    files_in_app_folder = \
        get_all_items_in_path(os.path.join(app_path_name, 'Contents/Resources'), search_type=1)
    icon_files = [x for x in files_in_app_folder if x[-5:] == '.icns']
    app_icon_file = [x for x in icon_files
                     if x[:-5].lower() == app_name.lower() or x[:-5].lower() == 'appicon']
    if len(app_icon_file) > 0:
        return pd.DataFrame(
                            {'extension': np.nan,
                             'icon': app_icon_file[0],
                             'icon_full_path': os.path.join(app_path_name, 'Contents', 'Resources',
                                                            app_icon_file[0]),
                             'icon_full_path_exists': True,
                             'app_path_name': app_path_name}, index=[0])

    return pd.DataFrame(columns=['extension', 'icon', 'icon_full_path', 'icon_full_path_exists',
                                 'app_path_name'])


"""
Copying, moving, deleting, creating
"""


def move_item_from_dir1_to_dir2(item: str, dir1: str, dir2: str):
    if os.path.exists(os.path.join(dir1, item)) and os.path.exists(dir2):
        try:
            shutil.move(os.path.join(dir1, item),
                        os.path.join(dir2, item))
            return 1
        except:
            return -1
    else:
        return -1


def delete_item(path: str):
    """ param <path> could either be relative or absolute. """
    if os.path.isfile(path) or os.path.islink(path):
        try:
            if os.path.exists(path):
                os.remove(path)  # remove the file
            success = 1
        except:
            success = -1
    elif os.path.isdir(path):
        try:
            if os.path.exists(path):
                shutil.rmtree(path)  # remove dir and all contains
            success = 1
        except:
            success = -1
    else:
        raise ValueError("file {} is not a file or dir.".format(path))
        success = -1
    return success


def empty_folder(path_to_empty: str):
    files = get_all_item_names_in_directory(path_to_empty)
    for f in files:
        os.remove(os.path.join(path_to_empty, f))


def copy_all_files_from_to(source_dir: str, target_dir: str, override: bool = True):
    if not os.path.exists(source_dir):
        return -1

    # Create the target directory if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)
    success = 1
    # Copy each file from the source to the target directory
    for file_name in os.listdir(source_dir):
        full_file_path = os.path.join(source_dir, file_name)

        target_item_path = os.path.join(target_dir, file_name)
        if os.path.exists(target_item_path):
            if override:
                try:
                    os.remove(target_item_path)
                except:
                    return -1
            else:
                continue

        # Only copy files (skip subdirectories)
        if os.path.isfile(full_file_path):
            try:
                shutil.copy(full_file_path, target_dir)
            except:
                return -1

    return success


def copy_item_to_dir(item_full_path: str, dest_dir: str, override: bool = True):
    if os.path.exists(item_full_path) and os.path.exists(dest_dir):
        item_name = extract_filename_from_path(item_full_path)
        if not override and os.path.exists(os.path.join(dest_dir, item_name)):
            return 0
        try:
            if os.path.isdir(item_full_path):
                logger.info("copy_item_to_dir (True): " + item_full_path + " " + dest_dir)
                shutil.copytree(item_full_path, os.path.join(dest_dir, item_name))
            else:
                logger.info("copy_item_to_dir (True): " + item_full_path + " " + dest_dir)
                shutil.copy(item_full_path, os.path.join(dest_dir, item_name))
            return 1
        except:
            return -1
    else:
        return -1


def copy_item(item_full_path: str, dest_item_full_path: str):
    if item_full_path == dest_item_full_path:
        return 0
    if os.path.exists(item_full_path):
        try:
            if os.path.isdir(item_full_path):
                logger.info("copy_item (True): " + item_full_path + " " + item_full_path)
                shutil.copytree(item_full_path, dest_item_full_path)
            else:
                logger.info("copy_item (True): " + item_full_path + " " + item_full_path)
                shutil.copy(item_full_path, dest_item_full_path)
            return 1
        except:
            return -1
    else:
        return -1


def copy_and_paste_item(item_full_path: str,
                        dest_item_full_path: str = None,
                        dest_path_excluding_filename: str = None):

    if dest_item_full_path is None and dest_path_excluding_filename is None:
        raise ValueError("Both dest_item_full_path and dest_path_excluding_filename are None.")
        return

    if dest_item_full_path is not None:
        if item_full_path == dest_item_full_path:
            return 0
        return copy_item(item_full_path, dest_item_full_path)
    else:
        return copy_item_to_dir(item_full_path, dest_path_excluding_filename)


def get_clipboard_copied_files_paths():
    logger.info(f"get_clipboard_copied_files_paths")
    clipboard = QApplication.clipboard()
    copied_file_paths = []
    if clipboard.mimeData().hasUrls():
        urls = [x for x in clipboard.mimeData().urls()]
        copied_file_paths = [url.toString().replace('file://', '').replace('%20', '')
                             for url in urls]
    return copied_file_paths


def move_to_trash(item_path: str):
    if os.path.exists(item_path):
        send2trash(item_path)
        return 1
    else:
        return -1


def create_file(full_file_path: str):
    try:
        open(full_file_path, 'a').close()
        return 1
    except:
        return -1



"""
Misc
"""


def dir_(obj, substring: str = '') -> pd.DataFrame:
    returned_values = [x for x in dir(obj) if substring in x]
    return pd.DataFrame(columns=returned_values).columns.values


def get_all_item_names_in_directory(directory_path: str) -> pd.DataFrame:
    p = Path(directory_path)
    files_in_directory = []
    for x in p.iterdir():
        files_in_directory.append(x.name)
    return files_in_directory


def get_all_app_names_in_path(path: str) -> list[str]:
    all_app_names = get_all_items_in_path(path, search_type=2)
    return [os.path.join(path, i) for i in all_app_names if i[-4:] == '.app']


def rename_file_or_dir(path_to_file_or_dir: str, new_name: str):
    new_path = os.path.join(os.sep.join(path_to_file_or_dir.split(os.sep)[:-1]), new_name)
    os.rename(path_to_file_or_dir, new_path)


def get_dataframe_of_file_names_in_directory(directory_path: str) -> pd.DataFrame:
    if not os.path.exists(directory_path):
        return pd.DataFrame({conf.FILE_EXPLORER_FILENAME_COL_NAME: [],
                             'Date modified': [],
                             'Size': [],
                             'Type': [],
                             'file_type': [],
                             'size_raw': [],
                             'extension_n_char': [],
                             'date_modified_raw': [],
                             'is_folder': [],
                             'is_hidden': [],
                             })
    p = Path(directory_path)
    file_name = []
    date_modified = []
    date_modified_raw = []
    size_string = []
    size_raw = []
    types = []
    type_icons = []
    extension_n_char = []
    is_folder_ = []
    is_hidden_ = []
    for x in p.iterdir():
        new_path = os.path.join(directory_path, x.name)
        try:
            file_name_ = x.name
            date_modified_ = get_item_date_modified(new_path)
            type_icon = get_type_as_icon_string(Path(new_path))
            type_ = get_file_type(new_path)
            size_ = Path(new_path).stat().st_size
            ext_n_char_ = len(extract_extension_from_path(Path(new_path)))
            date_modified_raw_ = os.path.getctime(new_path)

            is_folder_.append(Path(new_path).is_dir())
            file_name.append(file_name_)
            date_modified.append(date_modified_)
            types.append(type_)
            if type_ == 'Folder':
                size_string.append("--")
            else:
                size_string.append(size_bytes_to_string(size_))
            type_icons.append(type_icon)
            extension_n_char.append(ext_n_char_)
            size_raw.append(size_)
            date_modified_raw.append(date_modified_raw_)
            is_hidden_.append(is_hidden(new_path))
        except:
            pass
    df = pd.DataFrame({conf.FILE_EXPLORER_FILENAME_COL_NAME: file_name,
                       'Date modified': date_modified,
                       'Size': size_string,
                       'Type': types,
                       'file_type': type_icons,
                       'size_raw': size_raw,
                       'extension_n_char': extension_n_char,
                       'date_modified_raw': date_modified_raw,
                       'is_folder': is_folder_,
                       'is_hidden': is_hidden_,
                       })
    if conf.SHOW_HIDDEN_ITEMS or df.shape[0] == 0:
        return df
    else:
        return df[[not i for i in is_hidden_]]


def get_all_items_in_path(path: str, search_type: int = 0, extension: str = None):
    """
    search_type==0: all
    search_type==1: files only
    search_type==2: folders only
    """
    all_items = []
    if os.path.exists(path):
        all_items = [f for f in listdir(path)]
    if search_type == 1:
        all_items = [f for f in all_items if isfile(join(path, f))]
        if extension is not None:
            all_items = [f for f in all_items if f.endswith(extension)]
    if search_type == 2:
        all_items = [f for f in all_items if not isfile(join(path, f))]
    return all_items


def run_file_in_terminal(item_path: str, app_name: str = None):
    if chr(92) in item_path:
        item_path = item_path.replace(" ", chr(92) + " ")
    logger.info(f"run_file_in_terminal {item_path}, {app_name}")
    try:
        if app_name is None:
            success = os.system(f"open '{item_path}'")
        else:
            success = os.system(f"open -a '{app_name}' '{item_path}'")
        return success
    except:
        return -1


def open_application(app_path: str) -> int:
    """
    Opens an application from the /Applications folder on macOS.

    :param app_name: The name of the application (e.g., 'Safari', 'TextEdit').
    """
    try:
        subprocess.run(["open", app_path], check=True)
        return 1
    except subprocess.CalledProcessError as e:
        return -1


# E.g, if path contains items named "New folder", "New folder 2" --> output "New folder 3"
def increment_max_item_name(all_item_names_in_path: list[str], path: str, item_name: str):
    filename_no_ext = remove_extension_from_filename(item_name)
    item_exension = extract_extension_from_path(item_name)
    exension_len = len(item_exension)
    filename_len = len(filename_no_ext)
    similar_filenames = \
        [remove_extension_from_filename(x)
         for x in all_item_names_in_path
         if extract_extension_from_path(x) == item_exension]
    similar_filenames = \
        [x for x in similar_filenames if x[:filename_len] == filename_no_ext]
    max_suffix = \
        get_max_integer_suffix_among_strings_with_prefix(similar_filenames, filename_no_ext)
    full_item_exension = '.' + item_exension if exension_len >= 1 else item_exension
    if max_suffix is None:
        if len(similar_filenames) == 0:
            return os.path.join(path, filename_no_ext + full_item_exension)
        else:
            return os.path.join(path, filename_no_ext + " 2" + full_item_exension)
    else:
        return os.path.join(path, filename_no_ext + " " + str(max_suffix+1) + full_item_exension)
