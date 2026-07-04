# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

CleanFinder is a macOS desktop file manager (PySide6/Qt), styled after the Windows 10 file explorer, meant to be cleaner and more customizable than Finder. Entry point is `CleanFinder.py`. Tested informally on Sonoma; "a bit buggy" on Sequoia.

## Setup

The project's venv is at `/Users/roi.granot/PycharmProjects/CleanFinderVenv` (not inside this repo).

```
pip install --upgrade pip
pip install Foundation==0.1.0a0.dev1
# Then rename the two "foundation" site-packages folders to "Foundation" (capital F):
#   .../site-packages/foundation -> Foundation
#   .../site-packages/foundation-0.1.0a0.dev1.dist-info -> Foundation-...
pip install -r requirements.txt
```

Key deps: PySide6 (Qt UI), pandas/numpy (file-explorer-table backing store), pyobjc/Foundation (macOS integration), send2trash, icnsutil, pillow.

## Running

```
python CleanFinder.py
```

On first run (governed by `should_reset.txt` containing `"1"`), an `InstallationUiWidget` (`src/installation.py`) runs a setup flow before the main app starts; setting that file's contents back to `"1"` forces the installation flow again. `results/` (logs, generated icons, cached config) is created on demand next to wherever the app's working directory resolves to — see the docstring at the top of `CleanFinder.py` for the script-vs-bundled-app working-directory logic (matters for py2app/Nuitka/PyInstaller builds).

## Tests

Tests use `unittest`, not pytest (pytest is not installed in the venv). Run from the repo root so `src` resolves as a package:

```
python3 -m unittest tests.utils.test_utils -v
```

Note: several tests in `tests/utils/test_utils.py` currently fail/error (they `patch('os_utils.X', ...)` instead of `patch('src.utils.os_utils.X', ...)`, and one assertion is stale) — this is pre-existing breakage, not something to silently "fix" as a side effect of unrelated work.

## Packaging

Built with PyInstaller (see `CleanFinder.spec`):

```
pyinstaller --noconfirm --windowed --name="CleanFinder" --icon="resources/black_binder.icns" \
    --add-data "resources:resources" CleanFinder.py
```

py2app and Nuitka were also tried; README.md documents several environment-specific gotchas with both (Foundation/foundation casing, setuptools version, full-project Nuitka compilation not working — only `nuitka --module` per file does).

## Architecture

### Layering

- `src/shared/` — cross-cutting globals, created once at import time and shared everywhere:
  - `vars.py`: instantiates the single `conf_manager` (config), `extensions_to_icons_mapper`, `logger`, and the `threads_server` dict. Most modules do `from src.shared.vars import conf_manager as conf, logger`.
  - `locations.py`: all filesystem paths (resources dir, results dir, icons dir, config file, log file, OS-dependent root dir).
- `src/non_ui_components/` — logic that doesn't directly subclass Qt widgets (though some still inherit `QWidget`/`QMainWindow` for signal/slot plumbing):
  - `configurations_manager.py` (`ConfigurationsManager`): loads `resources/config.json` into ~50 plain attributes (colors, fonts, column indices, grid style, window dims) consumed throughout the UI layer. Changing visual/behavioral config means editing this file's schema and `resources/config.json` together. **Recipe for a new option**: add the key to `default_config` and `resources/config.json`; load it in `upload_all_configurations_from_json` (use `.get(key, default)` so pre-existing config files don't `KeyError`); for a Y/N boolean add a `@property`+setter that maps `'Y'/'y'`→`True` (see `SHOW_FAVORITES_TITLE`), for a color add it to `rgb_attribute_names`; add the key to the validation whitelist in `_update_individual_attribute`; and list it in `get_user_styles_config()` to make it editable live in the **Edit → Edit configurations** dialog (which persists via `set_attr` → saved on last-window-close). Options added this way include `DUAL_PANE_MODE` (Y/N) and `LEFT_PANE_SEPARATOR_COLOR` (rgb, the line between the left pane and the pane area).
  - `uis_manager.py` (`UiWindowManager`): the top-level controller. Owns the list of open windows (`self.windows`, each a `ui` instance — multiple Finder-style windows can be open at once), the undo/redo stack (`UserActionsManager`), cut/copy state shared across windows, and per-path column-sorting schemes persisted via pickle to `results/columns_sorting_scheme_per_path`. Also contains `PastingDelegate`, which resolves copy/move conflicts (prompts "keep both" via `TableWithRadioButtons` when names collide) before delegating to `PastingManager`.
  - `user_actions.py`: undo/redo as a command pattern — `UserAction` subclasses (`MoveFile`, `CreateItem`, `CopyPasteItem`, `RenameItem`, `MoveFilesUsingThread`, `CopyPasteItemsUsingThread`) each implement `undo()`/`redo()`; `UserActionsManager` holds the stacks. Long-running file ops (paste/move via threads) re-invoke `uis_manager.paste_items(...)` on undo/redo rather than touching the filesystem directly.
  - `extensions_to_icons_mapper.py`, `servers.py` (`ThreadsUiServer` — lets background `QThread`s pop up progress bars/message boxes on the UI thread via a dict of callables).
- `src/ui_components/` — the Qt widget tree:
  - `ui.py` (`ui` class, subclasses `QMainWindow`): one instance per open file-explorer window. Owns the left-pane sidebar (favorites/quick-access tree) and **one or two file-explorer panes side by side**. A `Pane` (helper class in this file) bundles a `PandasModel`, a `FileExplorerTable`, and a breadcrumb `TextboxNavigator` + editable path textbox. The layout is column-based: `subsplitter` splits `[left_column | panes_splitter]`, where `left_column` = `[nav buttons | sidebar]` and each pane is a column `[breadcrumb toolbar | table]` — so every top band lines up on one row and each breadcrumb stays directly above its own table. Dual vs single is chosen by `conf.DUAL_PANE_MODE`, read at window construction (so toggling it applies to newly-opened windows, not already-open ones). **`ui.file_explorer` is a property returning the _active_ pane's table** (the last-focused one, tracked via `FileExplorerTable.focusInEvent` → `ui.set_active_pane_by_table`); shared controls (toolbar back/forward/up buttons, tree/favorites clicks, bottom status bar, editable path box) all act on the active pane. Use `ui.all_tables()` to reach every pane's table, and `ui.active_pane` for the active `Pane`.
  - `file_explorer_table.py` (`FileExplorerTable`, subclasses `QTableView`): the actual file listing — drag/drop, selection, context menu wiring, in-place rename. Calls back into its `encompassing_ui` passing `self` (e.g. `path_changed(self, ...)`, `refresh_bottom_toolbar_text(self, ...)`) so the window can route updates to the correct pane.
  - `misc_widgets/`: dialogs (`dialogs_and_messages.py`), context menu (`context_menu.py` — `ContextMenuDelegate`, pre-built once at construction time and repopulated cheaply on each right-click), properties window (`properties_window.py`), search box (`search_box_window.py`), the favorites/tree-view sidebar (`tree_file_explorer.py`, `links_table.py`), menu bar (`menu_bar.py`), keyboard shortcut config (`shortcut_keys_configuration.py`).
- `src/utils/` — stateless helpers, deliberately UI-agnostic so they're usable from threads:
  - `os_utils.py`: filesystem primitives (path math, trash, copy/move, building the pandas DataFrame of a directory's contents, icon resolution).
  - `pasting_items.py`: threaded copy/move engine (`PastingManager`) plus the `TableWithRadioButtons` conflict-resolution dialog.
  - `file_explorer_utils.py`, `utils.py`: general formatting/icon-path helpers.
- `src/data_models.py`: Qt model classes wrapping pandas DataFrames for `QAbstractTableModel`-based views — `PandasModelBase`/`PandasModel` back the main file table (sorting, drag/drop, cut/grey-out rendering, icon decoration by file type), `MiscItemsTable` backs the favorites sidebar, `SimplePandasModel`/`SimplePandasModel2` are lighter-weight variants used elsewhere (e.g. properties window).

### Data flow for a typical operation

UI widget (e.g. `FileExplorerTable` context menu) → calls into `UiWindowManager` (passed down at window-construction time as `encompassing_uis_manager`) → manager mutates shared state (cut/copy buffers, undo stack) and/or delegates to `PastingDelegate`/`PastingManager` for actual filesystem work on a background thread → on completion, `refresh_all_uis()` re-pulls `PandasModel` data from disk for **every table in every open window** (`for w in windows: for t in w.all_tables(): ...`), so changes propagate across all windows and both panes. The manager's fan-out loops (refresh, cut/copy broadcast, browsing-history cleanup, paste-selection) all iterate `w.all_tables()` rather than a single `w.file_explorer`.

### Config and persistence

- `resources/config.json` is the editable config source of truth; `ConfigurationsManager` (`src/shared/vars.py: conf`) is the in-memory typed view of it, read everywhere as `conf.SOME_ATTR`.
- `should_reset.txt` is a one-byte sentinel file (`"1"` or not) controlling whether the installation flow runs on next launch.
- `results/` holds runtime-generated state: `log.log` (rotating file handler), `icons/` (generated icon cache), and `columns_sorting_scheme_per_path` (pickled per-directory column sort order).

## Gotchas

- **Qt `triggered` signal**: `QAction.triggered` emits `checked: bool` as its first argument. Any lambda connected via `action.triggered.connect(fn)` must be **zero-arg** (`lambda: ...`) — a lambda with a parameter (even one with a default) will receive `False` instead of the intended value. All existing lambdas in `context_menu.py` follow this zero-arg pattern. (This is why the `JUMP_TO_PATH_TEXTBOX` shortcut binds to zero-arg `ui.jump_to_path_textbox`, not directly to the pane-taking `expose_input_textbox`.)
- **`ui.file_explorer` is the _active_ pane's table, not a fixed widget**: with dual-pane there are 1–2 tables per window. Iterate `w.all_tables()` when an operation must touch every pane; use `w.file_explorer` only when you mean "the currently focused pane".
- **Per-table keyboard shortcuts must be `WidgetWithChildrenShortcut`**: shortcuts are `QAction`s added to each `FileExplorerTable` via `create_qaction_key_sequence` (`src/utils/utils.py`). With two panes registering identical keys in one window, the default `WindowShortcut` context makes Qt see an *ambiguous shortcut overload* and fire none of them — so that helper sets `WidgetWithChildrenShortcut`, which also correctly routes each shortcut to whichever pane has focus.

## Adding a keyboard shortcut

For the step-by-step recipe (action-name mapping, `config.json` + `default_config` entries, the auto-populated config dialog) and its gotchas (`triggered` emits `bool`; close windows via `.close()` not `on_close()`), see [docs/adding-a-keyboard-shortcut.md](docs/adding-a-keyboard-shortcut.md).

## Adding a context-menu item

For the step-by-step recipe (declare a menu-item dict in `ContextMenuDelegate`, implement a zero-arg handler on `FileExplorerTable`, choose the empty-space / single-vs-multi / `.app` branch, add a submenu) and its gotchas (`triggered` emits `bool`; menus are built once and only actions are rebuilt; new submenus must be added to `reconfigure_styles`), see [docs/adding-a-context-menu-item.md](docs/adding-a-context-menu-item.md).
