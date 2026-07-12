"""QApplication subclass that handles macOS "open file/folder" events.

Catches ``QFileOpenEvent`` (delivered when you run ``open -a CleanFinder <path>``,
pick CleanFinder in Finder's "Open With", or drag a folder onto the dock icon)
and forwards the path to a ``FileOpenRouter``, which resolves it and opens a
window via the UiWindowManager.

The routing/queuing logic lives in ``file_open_router.py`` (unit-tested); this
class is the thin Qt glue.
"""

from PySide6 import QtCore, QtWidgets

from src.non_ui_components.file_open_router import FileOpenRouter


class CleanFinderApplication(QtWidgets.QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.file_open_router = FileOpenRouter()

    def event(self, e):
        if e.type() == QtCore.QEvent.Type.FileOpen:
            self.file_open_router.handle_path(e.file())
            return True
        return super().event(e)
