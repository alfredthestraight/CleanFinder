import os
import platform


if platform.system() == 'Windows':
    SYSTEM_ROOT_DIR = os.environ.get('SystemDrive', 'C:') + '\\'
else:
    SYSTEM_ROOT_DIR = '/'


APP_PATH = os.getcwd()
ICONS_DIR = os.path.join(APP_PATH, 'results', 'icons')
BASE_ICONS_DIR = os.path.join(APP_PATH, 'resources', 'icons_base')
CONFIG_FILE_PATH = os.path.join(APP_PATH, 'resources', 'config.json')
DRAGGING_ICON = os.path.join(ICONS_DIR, '_dragged_items_.png')
RESULTS_PATH = os.path.join(APP_PATH, 'results')
EXT_AND_ICONS_DF_PATH = os.path.join(RESULTS_PATH, 'usable_extensions_and_icons_df')
LOG_FILE_PATH = os.path.join(RESULTS_PATH, 'log.log')
APPLICATION_DIRECTORIES = ['/Applications',
                           '/System/Applications',
                           '/System/Library/CoreServices/Applications']

# Where to start searching for icons
SYSTEM_DEFAULT_ICONS_DIR = "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/"
if not os.path.exists(SYSTEM_DEFAULT_ICONS_DIR):
    SYSTEM_DEFAULT_ICONS_DIR = SYSTEM_ROOT_DIR
