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
