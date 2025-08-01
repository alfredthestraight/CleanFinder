from PySide6 import QtCore
from PySide6.QtWidgets import (QTableView, QAbstractItemView, QLineEdit, QSizePolicy, QVBoxLayout,
                               QHeaderView, QDialog, QDialogButtonBox, QStyledItemDelegate, QStyle)
from PySide6.QtCore import Signal, QObject, QThread, Qt
from PySide6.QtGui import QFont
import os
import time
import pandas as pd
from src.utils.os_utils import run_file_in_terminal
from src.data_models import SimplePandasModel
from src.shared.vars import conf_manager as conf


def files_iterator(path: str, txt: str):
    for root, dirs, files in os.walk(path, topdown=True):
        files_and_dirs = files + dirs
        for name in files_and_dirs:
            relative_path = os.path.join(root, name).replace(path + '/', '')
            if txt in relative_path:
                yield relative_path


class Worker(QObject):
    finished = Signal()
    progress = Signal(int)

    def __init__(self, encompassing_obj, num_items_to_find, text_to_search):
        self.encompassing_obj = encompassing_obj
        self.num_items_to_find = num_items_to_find
        self.chunk_ended = False
        super().__init__()

    def run(self):
        i = 0
        while i < self.num_items_to_find:
            try:
                nextfile = next(self.encompassing_obj.files_iter)
                self.encompassing_obj.results_table.model().insertRows(new_row=[nextfile])
            except StopIteration:
                self.encompassing_obj.search_finished = True
                pass
            i += 1
        self.chunk_ended = True
        self.encompassing_obj.quit_all_threads()


class NoElideDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # Adjust the font metrics to measure the text
        # font_metrics = QFontMetrics(option.font)
        text = index.data()

        # Set up the painter to avoid eliding text
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        # Draw the text directly in the item rectangle
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         text)


class SearchWindow_threaded(QDialog):
    def __init__(self, root_path, encompassing_ui):
        super(SearchWindow_threaded, self).__init__()
        self.root_path = root_path
        self.encompassing_ui = encompassing_ui
        self.threads = {}
        self.initUI()
        self.installEventFilter(self)
        self.search_box.setFocus()

    def initUI(self):
        self.setFocus()
        self.setWindowTitle('Search')
        self.setGeometry(300, 300, 300, 300)
        self.resize(500, 600)

        # Layout for General tab
        self.overall_layout = QVBoxLayout()
        self.search_layout = QVBoxLayout()
        self.results_layout = QVBoxLayout()

        self.search_box = QLineEdit()
        self.search_box.setFont(QFont(conf.TEXT_FONT, conf.TEXTBOX_FONT_SIZE))
        # self.search_box.setStyleSheet(conf.TEXTBOX_STYLE)
        self.search_box.setStyleSheet("""
            QLineEdit{background-color: rgb(255,255,255);
            border:  1px solid lightgrey;
            };""")
        self.search_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.search_layout.addWidget(self.search_box)

        # Results:
        self.results_table = QTableView()
        self.results_table.setItemDelegate(NoElideDelegate())
        self.results_table.setStyleSheet("""QTableView{border: 0px;  margin: 0px;}""")
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setVisible(False)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.model = SimplePandasModel(data=pd.DataFrame(columns=['Filename']))
        self.results_table.setModel(self.model)
        self.results_table.doubleClicked.connect(self.double_click_on_search_result)
        self.results_table.verticalScrollBar().valueChanged.connect(self.scrollbar_reached_bottom)
        self.results_layout.addWidget(self.results_table)

        # Create the buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # Main layout
        self.overall_layout.addLayout(self.search_layout)
        self.overall_layout.addLayout(self.results_layout)
        self.overall_layout.addWidget(self.button_box)

        self.setLayout(self.overall_layout)

    def empty_results_table(self):
        self.results_table.model().clear_all_data()
        self.update()

    def keyPressEvent(self, e):
        if (e.key() == QtCore.Qt.Key.Key_Return) or (e.key() == QtCore.Qt.Key.Key_Enter):   # Enter
            if self.search_box.text() != '':
                self.empty_results_table()
                self.quit_all_threads()
                self.search_finished = False
                self.chunk_ended = False
                # Stateful (for the lifecycle of the search-box) iterator which will be
                # used by all workers
                self.files_iter = files_iterator(self.root_path, self.search_box.text())
                # Find the first n items (the following n items will be looked for once
                # user scrolls all the way down):
                self.next_n_items_finder_thread()
        elif e.key() == QtCore.Qt.Key.Key_Escape:    # Enter
            self.reject()

    def scrollbar_reached_bottom(self, value: int):
        if value == self.results_table.verticalScrollBar().maximum():
            print("Scrollbar has reached the end")
            if not self.search_finished and self.worker.chunk_ended:
                self.next_n_items_finder_thread()
                time.sleep(0.5)

    def next_n_items_finder_thread(self, n: int = 100):
        new_thread_index = len(self.threads)
        self.threads[new_thread_index] = {'thread': QThread(), 'is_alive': True}
        new_thread = self.threads[new_thread_index]['thread']
        self.worker = Worker(self, n, self.search_box.text())
        self.worker.moveToThread(new_thread)
        new_thread.started.connect(self.worker.run)
        new_thread.start()

    def quit_all_threads(self):
        for thread in self.threads.keys():
            if self.threads[thread]['is_alive']:
                self.threads[thread]['thread'].quit()
                self.threads[thread]['is_alive'] = False

    def accept(self):
        self.quit_all_threads()
        super(SearchWindow_threaded, self).accept()

    def reject(self):
        self.quit_all_threads()
        super(SearchWindow_threaded, self).reject()

    def double_click_on_search_result(self, index):
        item_path = os.path.join(self.root_path, index.data())
        if os.path.isdir(item_path):
            self.encompassing_ui.encompassing_uis_manager.create_new_window(item_path)
        else:
            run_file_in_terminal(item_path)
