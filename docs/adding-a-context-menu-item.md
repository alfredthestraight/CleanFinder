# Recipe: adding a new context-menu item

How to add an item to the right-click context menu of a file-explorer pane (e.g. "Open",
"Zip", "Properties"). Menu items are plain dicts declared in `ContextMenuDelegate`
(`src/ui_components/misc_widgets/context_menu.py`); their handlers are methods on
`FileExplorerTable` (`src/ui_components/file_explorer_table.py`). Follow these steps in order.

## How it fits together

- The delegate builds three persistent `QMenu` containers **once** in `__init__` (styling via
  `configure_context_menu` is the expensive part). On every right-click,
  `populate_context_menu` (context_menu.py:119) only `clear()`s the menu and re-adds cheap
  `QAction`s — so **never stash per-click state on the delegate**.
- An item is a dict: `{"menu_item_name": "<label>", "associated_method": <zero-arg callable>}`.
  The sentinel `{"menu_item_name": "SEP"}` inserts a separator.
- `add_actions_to_context_menu` (`src/utils/utils.py:182`) turns each dict into a
  `QAction("  " + name, widget)` and does `action.triggered.connect(associated_method)`. The
  two-space prefix is the label's left padding — no icons, no shortcut text are supported.

## Steps

1. **Declare the item** — add a dict in the right place in `context_menu.py`, chosen by where
   the item should appear:
   - **Right-click on empty space** → append to `click_on_empty_space_actions_list`
     (property, L74).
   - **Right-click on an item** → add to one of the "Functions bulk #1–#5" blocks inside
     `populate_context_menu` (L139-191). Gate single-selection-only items on
     `len(items_list) == 1`, mirroring the existing "Open" (L143-145) and "Open path in
     terminal" (L184-188) items.
   - **Name-manipulation submenu** → add to `item_name_manipulations_list` (property, L92).
   - Insert `{"menu_item_name": "SEP"}` where you want a separating line.

   ```python
   {"menu_item_name": "My action",
    "associated_method": self.file_exp_obj.my_action},
   ```

2. **Implement the handler** — add a **zero-arg** method on `FileExplorerTable`
   (`file_explorer_table.py`), referenced from the delegate as `self.file_exp_obj.my_action`:
   ```python
   def my_action(self):
       ...  # self.path, self.selected_items_paths, etc. are available here
   ```
   To pass captured data, wrap the call in a **zero-arg** `lambda:` — as done for `zip_items`
   (context_menu.py:84-86) and `open_file_with_specified_app` (L157-158) — or use a small
   callable object like `NewFileCreationWrapper` (context_menu.py:8), `change_items_names_case`,
   or `open_file_as_app` (both in `src/utils/file_explorer_utils.py`).

3. **(Only if adding a whole new submenu)** In `ContextMenuDelegate.__init__`, create a new
   `QMenu`, run `configure_context_menu` on it, and `setFixedWidth(180)`. Add a
   `_repopulate_<name>_submenu` method (see `_repopulate_manipulate_name_submenu`, L67), call
   `menu.addMenu(self.<submenu>)` in `populate_context_menu`, **and add the new menu to the loop
   in `reconfigure_styles` (L43)** so it restyles on a live theme change.

That's it — `populate_context_menu` picks up the new dict on the next right-click; no
registration or config entry is needed.

## Patterns available

- **Separators:** the `{"menu_item_name": "SEP"}` sentinel.
- **Submenus:** persistent `QMenu` + a `_repopulate_*` method (see the "New file" and
  "Manipulate name(s)" submenus).
- **`.app` special-casing:** `clicked_on_app` (L130-133) — e.g. show "Open as app" vs
  "Open with".
- **Single-vs-multi pluralization:** e.g. the submenu title `submenu_item_name` at L172.
- **Not supported:** menu-item icons and per-item shortcut text — labels are plain text only.

## Gotchas (see also CLAUDE.md → Gotchas)

- **`triggered` emits a `bool`.** `QAction.triggered` passes `checked: bool` as its first
  argument. Any `lambda` in `associated_method` must be **zero-arg** (`lambda: ...`) or it
  receives `False` instead of your intended value; capture data in the closure. A bare bound
  method taking only `self` is fine.
- **Menus are built once; only actions are rebuilt.** `__init__` creates the `QMenu`s; every
  right-click just `clear()`s and re-adds `QAction`s. Don't hold per-click state on the delegate.
- **A new submenu must be added to `reconfigure_styles`** (L43), or it keeps the stylesheet
  captured at construction time and looks stale after the user changes the theme/colors.

## Verify it

Run `python CleanFinder.py`, right-click in the relevant context (empty space vs an item, one
vs several selected), confirm the new item appears in the expected position, and click it to
confirm the handler fires.
