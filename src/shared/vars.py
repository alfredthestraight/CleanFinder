from src.shared import locations
from src.non_ui_components.configurations_manager import ConfigurationsManager
import logging
from logging.handlers import RotatingFileHandler

threads_server = {}

conf_manager = ConfigurationsManager(locations.CONFIG_FILE_PATH)

from src.non_ui_components.extensions_to_icons_mapper import ExtensionsToIconsMapper
extensions_to_icons_mapper = ExtensionsToIconsMapper(locations.EXT_AND_ICONS_DF_PATH)


logging.basicConfig(
    level=logging.DEBUG,
    format="{asctime} - {levelname}:  {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(locations.LOG_FILE_PATH, maxBytes=5 * 1024 * 1024, backupCount=3)
    ],
)

logger = logging.getLogger(__name__)




