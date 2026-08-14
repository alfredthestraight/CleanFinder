#!/usr/bin/env bash
#
# Installs the built CleanFinder.app into /Applications and registers it with Launch Services,
# so the "Open in CleanFinder" Finder Service and `open -a CleanFinder <path>` both work.
#
# Replaces the README's five manual steps. Run from anywhere:
#
#   ./install_app.sh                 install what is already in dist/
#   ./install_app.sh --build         run pyinstaller first, then install
#   ./install_app.sh --no-open       don't launch the app at the end
#   ./install_app.sh --keep-finder   don't restart Finder
#   ./install_app.sh --force         install even if /Applications/CleanFinder.app looks foreign
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

APP_NAME="CleanFinder.app"
BUNDLE_ID="com.cleanfinder.app"
SOURCE_APP="dist/$APP_NAME"
INSTALLED_APP="/Applications/$APP_NAME"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister"
PBS="/System/Library/CoreServices/pbs"

DO_BUILD=0
LAUNCH_APP=1
RESTART_FINDER=1
FORCE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build)        DO_BUILD=1 ;;
        --no-open)      LAUNCH_APP=0 ;;
        --keep-finder)  RESTART_FINDER=0 ;;
        --force)        FORCE=1 ;;
        -h|--help)      sed -n '3,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)              echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
    shift
done

step() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nError: %s\n' "$1" >&2; exit 1; }

# --- Build ------------------------------------------------------------------------------------
if [[ $DO_BUILD -eq 1 ]]; then
    step "Building with pyinstaller"
    command -v pyinstaller >/dev/null || fail "pyinstaller is not on PATH. Activate the venv first:
  source /Users/roi.granot/PycharmProjects/CleanFinderVenv/bin/activate"
    # Build options live in the .spec - passing --icon/--add-data alongside it breaks the build
    pyinstaller --noconfirm CleanFinder.spec
fi

[[ -d "$SOURCE_APP" ]] || fail "$SOURCE_APP does not exist. Build it first:
  ./install_app.sh --build"

# --- Sanity-check what we are about to delete ---------------------------------------------------
# This script rm -rf's the installed bundle, so be certain that path really is our app and not
# something else that happens to share the name.
if [[ -e "$INSTALLED_APP" ]]; then
    installed_id="$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" \
        "$INSTALLED_APP/Contents/Info.plist" 2>/dev/null || true)"
    if [[ "$installed_id" != "$BUNDLE_ID" ]]; then
        if [[ $FORCE -eq 0 ]]; then
            fail "$INSTALLED_APP exists but its bundle id is '${installed_id:-unreadable}',
not '$BUNDLE_ID'. Refusing to delete it. Re-run with --force if you are sure."
        fi
        echo "Warning: replacing $INSTALLED_APP despite bundle id '${installed_id:-unreadable}' (--force)"
    fi
fi

# --- Quit any running copy ---------------------------------------------------------------------
if pgrep -x CleanFinder >/dev/null 2>&1; then
    step "Quitting the running CleanFinder"
    osascript -e 'quit app "CleanFinder"' >/dev/null 2>&1 || true
    for _ in $(seq 20); do
        pgrep -x CleanFinder >/dev/null 2>&1 || break
        sleep 0.25
    done
    # A copy still holding the bundle open would make the replacement below inconsistent
    pgrep -x CleanFinder >/dev/null 2>&1 && fail "CleanFinder is still running - quit it and retry."
fi

# --- Install -----------------------------------------------------------------------------------
# Deleted rather than copied over: `cp -R dist/CleanFinder.app /Applications/` MERGES into an
# existing bundle, so files from older builds survive and keep getting shipped.
step "Installing to $INSTALLED_APP"
rm -rf "$INSTALLED_APP"
cp -R "$SOURCE_APP" /Applications/

step "Clearing quarantine attributes and ad-hoc signing"
xattr -cr "$INSTALLED_APP"
codesign --force --deep --sign - "$INSTALLED_APP"

step "Registering with Launch Services"
# Only the registered .app exposes the Service - running `python CleanFinder.py` does not
"$LSREGISTER" -f "$INSTALLED_APP"

step "Flushing the Services cache"
"$PBS" -flush

if [[ $RESTART_FINDER -eq 1 ]]; then
    step "Restarting Finder so the Service appears in its context menu"
    killall Finder 2>/dev/null || true
fi

if [[ $LAUNCH_APP -eq 1 ]]; then
    step "Launching CleanFinder"
    open "$INSTALLED_APP"
fi

printf '\nDone. Installed %s\n' "$INSTALLED_APP"
