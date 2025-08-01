import os

"""
I want the directory with all the code and folder to be either:
1. Project directory (the one containing the source code, etc.)
2. <app_name>.app/Contents/Resources

If the code is run as a sctript (e.g., from PyCharm) - the working directory will be (2) above and
no changes are needed.

If py2app or Nuitka are used to make a standalone app - the working directory should be (1) above.
However, while in the case of py2app this will ba taken care of automatically, in the case of Nuitka
the working directory will be <app_name>.app/Contents/MacOS. In this case, the working directory
will be set programmatically to be <app_name>.app/Contents/Resources.
"""

app_full_name = 'app.app'
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != script_dir:
    os.chdir(script_dir)


if not os.path.exists(os.path.join(os.getcwd(), 'results')):
    os.mkdir(os.path.join(os.getcwd(), 'results'))
if not os.path.exists(os.path.join(os.getcwd(), 'results', 'icons')):
    os.mkdir(os.path.join(os.getcwd(), 'results', 'icons'))
if not os.path.exists(os.path.join(os.getcwd(), 'results', 'log.log')):
    open(os.path.join(os.getcwd(), 'results', 'log.log'), 'a').close()

import sys
from PySide6 import QtWidgets

from src.non_ui_components.servers import ThreadsUiServer
from src.non_ui_components.uis_manager import UiWindowManager
from src.ui_components.misc_widgets.menu_bar import populate_menubar_and_connect_triggers
from src.shared.vars import conf_manager as conf, threads_server, logger as logger
from src.installation import InstallationUiWidget


def enforce_should_reset_file_exists(should_reset_file_path: str):
    if not os.path.exists(should_reset_file_path):
        f = open(should_reset_file_path, "w")
        f.write("1")    # Write inside file
        f.close()


def should_reset(should_reset_file_path: str):
    f = open(should_reset_file_path, "r")
    should_reset = f.read()
    f.close()
    return should_reset == "1"


def start_app():
    logger.info("Starting app - UiWindowManager()")
    ui_manager = UiWindowManager()
    logger.info("Starting app - ThreadsUiServer()")
    threads_server['s1'] = ThreadsUiServer(ui_manager)
    logger.info("Starting app - create_new_window")
    ui_manager.create_new_window(root_dir_path=conf.DEFAULT_PATH)
    # Did not work on Sequoia 15.3 (functionality moved to the UI objects):
    # menubar = MebuBarManager(ui_manager)  # Takes care of menu bar requests
    # populate_menubar_and_connect_triggers(menubar)


def main():

    # enforce_directories_and_files_exist()
    app = QtWidgets.QApplication(sys.argv)
    app.setStartDragTime(1)
    should_reset_file_path = os.path.join(os.getcwd(), 'should_reset.txt')
    enforce_should_reset_file_exists(should_reset_file_path)

    # First time installation
    if should_reset(should_reset_file_path):
        logger.info("First time installation")
        if not os.path.exists(os.path.join(os.getcwd(), 'results')):
            os.mkdir(os.path.join(os.getcwd(), 'results'))
        installation_widget = InstallationUiWidget(should_reset_file_path, start_app)
        installation_widget.show()
        installation_widget.run_installation()
        conf.revert_back_to_default_config()

    # Post installation
    else:
        start_app()
    sys.exit(app.exec())


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print("main crashed. Error: %s", e)
