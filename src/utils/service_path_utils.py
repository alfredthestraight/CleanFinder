"""Pure, UI-agnostic helpers for the "Open in CleanFinder" macOS Service.

Kept free of Qt and pyobjc so the path-resolution logic is unit-testable and
usable from anywhere. The pyobjc glue lives in
``src/non_ui_components/macos_services.py``.
"""

import os
from typing import Optional, Tuple


def resolve_target(path: str) -> Optional[Tuple[str, Optional[str]]]:
    """Resolve a selected path to the window CleanFinder should open.

    Returns ``(folder_to_open, filename_to_highlight)`` where:
      - a directory resolves to ``(that_directory, None)`` (open it, nothing to
        highlight);
      - a file resolves to ``(parent_directory, filename)`` (open the parent and
        highlight the file);
      - a path that does not exist resolves to ``None`` (nothing to open).
    """
    if not os.path.exists(path):
        return None

    normalized = os.path.normpath(path)
    if os.path.isdir(normalized):
        return normalized, None

    return os.path.dirname(normalized), os.path.basename(normalized)
