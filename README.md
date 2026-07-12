A file manager for macos which is cleaner and more customizable.
Similar to the file explorer used in Windows 10.
Currently supports Sonoma, and (though a bit buggy) Sequoia


# **Installation:**
1. pip install --upgrade pip
2. pip install Foundation==0.1.0a0.dev1
3. Rename the two "foundation" folders ('.../site-packages/foundation' and '.../site-packages/foundation-0.1.0a0.dev1.dist-info') to "Foundation", i.e., F instead of f
4. Restart project
5. Install requirements.txt




# To wrap the project using py2app (assuming it's already installed):

**python py2app_setup.py py2app**

### Issues that may arise when trying to use py2app in order to compile the project:
* You may need to change folder "~.venv/lib/python3.9/site-packages/Foundation" from "Foundation" to "foundation" or vice versa 
* For py2app_setup to work you may need to revert setup tools to version 70.3.0
* Sometimes pip3 install / pip3 install -U worked and pip didn't (e.g., **pip3 install -U pyobjc**)
* If everything fails, you can use **python setup.py py2app -A**. The -A flag will create an alias to the source code, making it behave as if it's a standalone app, but it's not really. It's more like a shortcut to the python code without needing to run the python command in the terminal. 
* Wrapping the entire project after transforming the py scripts into Nuitka code doesn't work. An alternative is to compile individual files using command **nuitka --module filename.py**, and just run the project (e.g., in pycharm) with the created files instead of the original .py file

pyinstaller --noconfirm --windowed \
    --name="CleanFinder" \
    --icon="resources/black_binder.icns" \
    --add-data "resources:resources" \
    CleanFinder.py


# Building the app (future rebuilds — use this)

The command above is the **one-time** command that generated `CleanFinder.spec`. For
every rebuild after that, build **from the spec** — the spec holds the icon,
bundled resources, the `com.cleanfinder.app` bundle identifier, and the
`NSServices` ("Open in CleanFinder") declaration. Do **not** re-pass `--icon` /
`--add-data`: PyInstaller ignores build options when given a `.spec`, and passing
them as bare arguments breaks the build.

Run these as **separate** commands (no backslash chaining):

**pyinstaller --noconfirm CleanFinder.spec**

Then, to install it and register the "Open in CleanFinder" macOS Service (right-click
a file/folder in Finder → Services):

**cp -R dist/CleanFinder.app /Applications/**

**xattr -cr /Applications/CleanFinder.app && codesign --force --deep --sign - /Applications/CleanFinder.app**

**/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f /Applications/CleanFinder.app**

**/System/Library/CoreServices/pbs -flush && open /Applications/CleanFinder.app && killall Finder**

Notes:
* The Service only appears for the app registered with Launch Services (the built
  `.app`), not when running `python CleanFinder.py`.
* Keep a single `CleanFinder.app` around. Multiple copies sharing one bundle
  identifier make Launch Services resolve the Service to the wrong bundle and it
  stops appearing.


# Opening a path from the terminal

Once the built app is installed (see above), open any path in CleanFinder from the
terminal:

**open -a CleanFinder /some/path**

A folder opens in a new window; a file opens its parent folder with the file
highlighted. (Same mechanism as Finder's "Open With" and dragging a folder onto the
dock icon — all handled via `QFileOpenEvent`.) As with the Service, this works with
the built `.app`, not `python CleanFinder.py`.
