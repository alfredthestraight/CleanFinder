"""Routes macOS "open file/folder" requests to the UiWindowManager.

Used for the ``open -a CleanFinder <path>`` terminal invocation (and, via the
same QFileOpenEvent, Finder's "Open With" and drag-onto-icon). macOS delivers
the open event during launch, often *before* the UI/manager exists, so paths
that arrive early are queued and flushed once the manager is set.

Pure and Qt-agnostic so it is unit-testable; the QApplication that feeds it lives
in ``src/non_ui_components/app.py``. Path resolution is shared with the macOS
Service via ``src.utils.service_path_utils.resolve_target``.
"""

from src.shared.vars import logger as logger
from src.utils import service_path_utils


class FileOpenRouter:
    def __init__(self):
        self._manager = None
        self._pending = []
        self.opened_count = 0

    def set_manager(self, manager):
        """Attach the UiWindowManager and flush any paths queued before now."""
        self._manager = manager
        pending, self._pending = self._pending, []
        for path in pending:
            self._route(path)

    def handle_path(self, path):
        """Open ``path`` now if the manager is ready, else queue it."""
        if self._manager is None:
            self._pending.append(path)
        else:
            self._route(path)

    def _route(self, path):
        resolved = service_path_utils.resolve_target(path)
        if resolved is None:
            logger.info(f"Open path: skipping missing path '{path}'")
            return
        folder, filename_to_highlight = resolved
        self._manager.open_service_target(folder, filename_to_highlight)
        self.opened_count += 1
