"""macOS "Open in CleanFinder" Service provider (pyobjc glue).

Registers a Services provider so any app's Services submenu (and Finder's
right-click) shows "Open in CleanFinder", acting on the selected file(s)/
folder(s). Per-item behavior: one new window each; a folder opens itself; a file
opens its parent folder with the file highlighted.

The pure path-resolution logic lives in ``src.utils.service_path_utils`` and is
unit-tested there. This module is the thin, untestable-without-a-bundle glue:
reading the pasteboard and routing to the ``UiWindowManager`` on the main
thread.

NOTE: Services only appear for an app registered with Launch Services (the built
``.app``), not when running ``python CleanFinder.py``. The provider still
registers fine as a script; the menu item just won't show.
"""

import objc
from Foundation import NSObject
from AppKit import (NSApplication, NSURL, NSUpdateDynamicServices,
                    NSPasteboardURLReadingFileURLsOnlyKey)

from src.shared.vars import logger as logger
from src.utils import service_path_utils


def _paths_from_pasteboard(pboard):
    """Extract local filesystem paths from a Services NSPasteboard."""
    options = {NSPasteboardURLReadingFileURLsOnlyKey: True}
    urls = pboard.readObjectsForClasses_options_([NSURL], options) or []
    paths = []
    for url in urls:
        path = url.path()
        if path:
            paths.append(str(path))
    return paths


class CleanFinderServiceProvider(NSObject):
    """NSObject exposing the ``openInCleanFinder:userData:error:`` service."""

    def initWithUiManager_(self, ui_manager):
        self = objc.super(CleanFinderServiceProvider, self).init()
        if self is None:
            return None
        self._ui_manager = ui_manager
        return self

    @objc.typedSelector(b"v@:@@o^@")
    def openInCleanFinder_userData_error_(self, pboard, userData, error):
        try:
            paths = _paths_from_pasteboard(pboard)
        except Exception as e:
            logger.error(f"Open in CleanFinder: failed to read pasteboard: {e}")
            return None

        for path in paths:
            try:
                resolved = service_path_utils.resolve_target(path)
                if resolved is None:
                    logger.info(f"Open in CleanFinder: skipping missing path '{path}'")
                    continue
                folder, filename_to_highlight = resolved
                self._ui_manager.open_service_target(folder, filename_to_highlight)
            except Exception as e:
                logger.error(f"Open in CleanFinder: failed to open '{path}': {e}")

        return None


def register_open_in_cleanfinder_service(ui_manager):
    """Register the Services provider on the shared NSApplication.

    Returns the provider instance; the caller MUST keep a reference to it so it
    is not garbage-collected while registered.
    """
    provider = CleanFinderServiceProvider.alloc().initWithUiManager_(ui_manager)
    NSApplication.sharedApplication().setServicesProvider_(provider)
    NSUpdateDynamicServices()
    logger.info("Registered 'Open in CleanFinder' macOS Service provider")
    return provider
