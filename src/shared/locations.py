import os
import platform


if platform.system() == 'Windows':
    SYSTEM_ROOT_DIR = os.environ.get('SystemDrive', 'C:') + '\\'
else:
    SYSTEM_ROOT_DIR = '/'


APP_PATH = os.getcwd()

if os.path.exists(os.path.join(APP_PATH, 'resources')):
    RESOURCES_PATH = os.path.join(APP_PATH, 'resources')
elif os.path.exists(os.path.join(APP_PATH, 'Resources', 'resources')):
    RESOURCES_PATH = os.path.join(APP_PATH, 'Resources', 'resources')
elif os.path.exists(os.path.join(APP_PATH, 'Frameworks', 'resources')):
    RESOURCES_PATH = os.path.join(APP_PATH, 'Frameworks', 'resources')


if os.path.exists(os.path.join(APP_PATH, 'results')):
    RESULTS_PATH = os.path.join(APP_PATH, 'results')
elif os.path.exists(os.path.join(APP_PATH, 'Resources', 'results')):
    RESULTS_PATH = os.path.join(APP_PATH, 'Resources', 'results')
elif os.path.exists(os.path.join(APP_PATH, 'Frameworks', 'results')):
    RESULTS_PATH = os.path.join(APP_PATH, 'Frameworks', 'results')

ICONS_DIR = os.path.join(RESULTS_PATH, 'icons')
BASE_ICONS_DIR = os.path.join(RESOURCES_PATH, 'icons_base')
CONFIG_FILE_PATH = os.path.join(RESOURCES_PATH, 'config.json')
DRAGGING_ICON = os.path.join(ICONS_DIR, '_dragged_items_.png')
EXT_AND_ICONS_DF_PATH = os.path.join(RESULTS_PATH, 'usable_extensions_and_icons_df')
LOG_FILE_PATH = os.path.join(RESULTS_PATH, 'log.log')
APPLICATION_DIRECTORIES = ['/Applications',
                           '/System/Applications',
                           '/System/Library/CoreServices/Applications']

# Where to start searching for icons
SYSTEM_DEFAULT_ICONS_DIR = "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/"
if not os.path.exists(SYSTEM_DEFAULT_ICONS_DIR):
    SYSTEM_DEFAULT_ICONS_DIR = SYSTEM_ROOT_DIR
