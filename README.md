File manager for macos which is cleaner and more customizable.
Similar in nature to Windows 10 file explorer.


To install, this is what worked for me:
1. pip install --upgrade pip
2. pip install Foundation==0.1.0a0.dev1
3. Rename the two "foundation" folders ('.../site-packages/foundation' and '.../site-packages/foundation-0.1.0a0.dev1.dist-info') to "Foundation", i.e., F instead of f
4. Restart project
5. Install requirements.txt



To compile using Nuitka:
1. Must install CPython (which may not be the default macos python version). For that, visit the official Python website: https://www.python.org/downloads/macos/. 
2. Download the latest stable version of Python for macOS. 
3. Open the file you downloaded (in the case of a tar.xz file, you can use the following command to extract it: **tar -xvf Python-<version>.tar.xz**)
4. Navigate to the extracted directory and run the configure script to prepare the build environment: **./configure --enable-optimizations**
5. Compile the source code using make: **make -j$(nproc)**
6. Install Python: **sudo make altinstall**
7. Verify the installation: **python3.x --version**
8. Install Nuitka: **python3.x -m pip install nuitka**
9. Install all packages in the requirements.txt file. Don't keep an venv folder in the project directory so Nuitka won't compile it as well.
10. To compile the project:
**python3.9 -m nuitka --standalone --macos-create-app-bundle --follow-imports --enable-plugin=pyside6  --include-data-files="results/icons/*=resources/icons_base/" --include-data-files="resources/SegoeUI.TTF=resources/"  --macos-app-icon='resources/black_binder.icns' CleanFinder.py**



To wrap the project using py2app (assuming it's already installed, using pip install):

**python py2app_setup.py py2app**

Issues that may arise when trying to use py2app in order to compile the project
* You may need to change folder "~.venv/lib/python3.9/site-packages/Foundation" from "Foundation" to "foundation" or vice versa 
* For py2app_setup to work you may need to revert setup tools to version 70.3.0
* Sometimes pip3 install / pip3 install -U worked and pip didn't (e.g., **pip3 install -U pyobjc**)
* If everything fails, you can use **python setup.py py2app -A**. The -A flag will create an alias to the source code, making it behave as if it's a standalone app, but it's not really. It's more like a shortcut to the python code without needing to run the python command in the terminal. 
* Wrapping the entire project after transforming the py scripts into Nuitka code doesn't work. An alternative is to compile individual files using command **nuitka --module filename.py**, and just run the project (e.g., in pycharm) with the created files instead of the original .py file
