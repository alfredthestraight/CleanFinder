# "Open in CleanFinder" macOS Service — Design

**Date:** 2026-07-09
**Status:** Approved, pending implementation plan

## Goal

Let a user open a filesystem path in CleanFinder from other apps. Concretely: a
**"Open in CleanFinder"** entry in the macOS **Services** submenu of any app (and
Finder's right-click), acting on the currently selected file(s)/folder(s).

## Chosen behavior

- **Surface:** a macOS Service ("Open in CleanFinder"). No URL scheme, no CLI/argv,
  no `CFBundleDocumentTypes` "Open With" registration — Services only.
- **When the app is already running:** always open a **new window** per invocation
  (mirrors Finder's "Open With" feel; predictable). Never navigate/hijack an
  existing window.
- **Multiple selected items:** open **one window each**.
- **Selected item is a file (not a folder):** open the file's **parent folder** and
  **highlight the file** (best-effort). Reveal-in-CleanFinder behavior.

## Mechanism

A macOS Service has two halves:

1. **Declaration (static, in the bundle).** An `NSServices` array in the app's
   `Info.plist`, mirrored in the PyInstaller `BUNDLE` block of `CleanFinder.spec`.
   It declares:
   - `NSMenuItem` → `{ "default": "Open in CleanFinder" }` (the visible title).
   - `NSMessage` → `openInCleanFinder` (the selector prefix macOS invokes).
   - `NSSendTypes` → file URLs (`public.file-url`, plus legacy
     `NSFilenamesPboardType` for broad compatibility).
   - `NSPortName` → `CleanFinder`.

2. **Runtime provider (dynamic, in the app).** At startup the app registers a
   provider object with
   `NSApplication.sharedApplication().setServicesProvider_(provider)` followed by
   `NSUpdateDynamicServices()`. pyobjc is already a dependency (`pyobjc==11.0`;
   `AppKit`/`Foundation` already imported in `src/utils/os_utils.py`). When the
   Service fires, macOS calls the provider's selector with an `NSPasteboard`
   carrying the selected paths.

## New component

`src/non_ui_components/macos_services.py`

- `CleanFinderServiceProvider(NSObject)` with a single pyobjc-decorated selector
  `openInCleanFinder:userData:error:` (signature `v@:@@o^@`, matching the
  Services provider convention).
- Holds a reference to the `UiWindowManager` (passed in at construction, same
  pattern as `ThreadsUiServer`).
- On invocation it:
  1. Reads file URLs off the pasteboard → a list of local paths.
  2. Resolves each path to a target: a **folder** → itself; a **file** → its
     parent directory, remembering the filename to highlight.
  3. Routes each target to the `UiWindowManager` on the Qt main thread.

## Data flow

```
Other app: select item(s) → Services menu → "Open in CleanFinder"
  → macOS delivers NSPasteboard to CleanFinderServiceProvider.openInCleanFinder:...
    → for each path:
        folder → ui_manager.create_new_window(root_dir_path=folder)
        file   → parent = dirname(file)
                 ui_manager.create_new_window(root_dir_path=parent)
                 then highlight `file` in the new window's active pane (best-effort)
```

- **One window per resolved target.**
- File highlight uses the active pane table's existing public methods
  (`select_row_where_item_text_is`, or `change_path(..., selected_path_after_change=...)`).
  These back compiled `.so` modules and are **not** modified.

## Thread-safety & app integration

- The provider selector is delivered on the **main thread** via the shared
  `NSApplication` run loop that Qt already drives, so calls into
  `UiWindowManager` are main-thread-safe (no cross-thread marshalling needed).
- `QApplication` already owns the process's `NSApplication`, so
  `NSApplication.sharedApplication()` returns that same instance — registering a
  services provider on it is consistent with Qt's event loop.
- Registration happens in `start_app()` (after `ui_manager` exists). The provider
  object is stored in a long-lived reference (e.g. the existing `threads_server`
  dict or a module global) so it is not garbage-collected while registered.

## Error handling

- Empty/invalid pasteboard, or paths that no longer exist → log and no-op; never
  crash the app.
- The selector always returns cleanly so macOS does not surface a system error.
- The file-highlight step is wrapped independently: if it fails (e.g. the async
  table load races the selection call), the window still stays open at the parent
  folder.

## Testing / verification

**Key constraint:** macOS Services only appear for an app **registered with Launch
Services** — i.e. the packaged `.app`, not `python CleanFinder.py`. Running as a
script, the provider registers fine at runtime but no menu item appears.

Verification steps:
1. Build with PyInstaller (see `CleanFinder.spec`).
2. Register the bundle: `lsregister -f dist/CleanFinder.app` (path:
   `/System/Library/Frameworks/CoreServices.framework/.../lsregister`) or simply
   open the app once.
3. In another app (or Finder), select a **folder**, open its Services menu, confirm
   **"Open in CleanFinder"** appears, invoke it → a new CleanFinder window opens at
   that folder.
4. Repeat with a **file** → a window opens at its parent folder with the file
   highlighted.
5. Multi-select several folders → one window each.

## Files touched

- `CleanFinder.py` — register the provider in `start_app()`.
- `src/non_ui_components/macos_services.py` — **new**; the provider.
- `Info.plist` — add the `NSServices` declaration.
- `CleanFinder.spec` — mirror the `NSServices` declaration in the `BUNDLE` block so
  built apps carry it.
- No changes to compiled `.so` modules; file-highlight uses existing public methods.

## Out of scope (YAGNI)

- URL scheme (`cleanfinder://`).
- Command-line / `open -a CleanFinder <path>` argv handling.
- Finder "Open With" via `CFBundleDocumentTypes` + `QFileOpenEvent`.
- Reusing/navigating an existing window instead of opening a new one.
