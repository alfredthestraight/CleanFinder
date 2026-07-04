# Recipe: adding a new keyboard shortcut

How to add a global keyboard shortcut to a file-explorer window (e.g. `CLOSE_WINDOW` = ⌘W).
Shortcuts are `QAction`s registered per `FileExplorerTable`, driven entirely by the
`keyboard_shortcuts` dict in config. Follow these steps in order.

## Steps

1. **Map the action name to a callable** — in `map_shortcut_name_to_func`
   (`src/utils/file_explorer_utils.py`), add an entry keyed by a new `UPPER_SNAKE_CASE`
   action name:
   ```python
   "CLOSE_WINDOW": file_explorer_obj.encompassing_ui.close
   ```
   `file_explorer_obj` is the `FileExplorerTable`; reach the window via
   `file_explorer_obj.encompassing_ui` and the manager via
   `file_explorer_obj.encompassing_ui.encompassing_uis_manager`.

2. **Add the key binding to `resources/config.json`** — under `keyboard_shortcuts`, add the
   same action name with a list of one or more key strings:
   ```json
   "CLOSE_WINDOW": [
         "Ctrl+W"
   ]
   ```

3. **Add the identical entry to `default_config`** — in the `keyboard_shortcuts` block of
   `ConfigurationsManager.default_config` (`src/non_ui_components/configurations_manager.py`),
   so a config reset / fresh install includes the shortcut. Keep it byte-for-byte the same as
   step 2.

4. **Nothing else for the config dialog.** The **Edit → Keyboard shortcuts** dialog is built
   dynamically from `conf.get('keyboard_shortcuts')` (`menu_bar.py`, `configure_keyboard_shortcuts`),
   so the new action appears there automatically and is user-editable.

That's it — each `FileExplorerTable.initialize_all_key_sequences()` iterates the config and
registers the `QAction`s via `create_qaction_key_sequence` on next window construction /
`reload_keyboard_shortcuts()`.

## Key-string notes

- On macOS, Qt maps `"Ctrl"` in a `QKeySequence` to the **Cmd** key (this project does not
  disable the swap), and `"Meta"` maps to the physical Ctrl key. So `"Ctrl+W"` is ⌘W.
- Existing actions typically pair a `"Ctrl+X"` binding with an `"Alt+X"` alternative; add a
  second string to the list if you want that.

## Gotchas (see also CLAUDE.md → Gotchas)

- **`triggered` emits a `bool`.** `QAction.triggered` passes `checked: bool` as its first
  argument. If you map to a **lambda**, it must be zero-arg (`lambda: ...`) or it receives
  `False` instead of your intended value. Mapping to a bare bound method is fine — Qt matches
  arity, which is why binding directly to a widget's C++ `close` slot works (the standard
  `clicked.connect(widget.close)` idiom).
- **Closing a window: map to `.close()`, not `on_close()`.** `ui.on_close()` is only the
  bookkeeping callback (`UiWindowManager.on_ui_close` — removes the window from the list,
  shrinks it to height 0); it does **not** actually close the `QMainWindow`. Calling it
  directly leaves the widget alive, so Qt never fires "last window closed" and the app stays
  stuck in `app.exec()`. Bind to the `QMainWindow`'s real `close()` instead — that runs the
  same path as the red traffic-light button (`close()` → `closeEvent` → `on_close` →
  `on_ui_close`) and lets Qt quit on the last window (windows are created with
  `WA_DeleteOnClose`).
- **Shortcuts are `WidgetWithChildrenShortcut`-scoped.** `create_qaction_key_sequence`
  (`src/utils/utils.py`) sets this context so that, with two panes registering identical keys
  in one window, Qt doesn't see an ambiguous overload — and each shortcut routes to whichever
  pane has focus.
