import pandas as pd
from PySide6.QtGui import QKeySequence, QDrag
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtWidgets import (QLabel, QGridLayout, QPushButton, QSizePolicy, QHBoxLayout, QFrame,
                               QVBoxLayout, QWidget, QDialog)
from src.utils.utils import flatten_list_of_lists


class LabelWithXButton(QDialog):
    break_thread_run = Signal(str, str)

    def __init__(self, text: str = "", category_name: str = "",
                 fill_color: str = "rgb(200, 220, 220)"):
        super().__init__()

        self.category_name = category_name

        # Add a main layout to which everything will be added
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(9, 1, 9, 1)  # left-top-right-bottom
        self.setLayout(self.main_layout)

        self.label = QLabel(text, self)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.main_layout.addWidget(self.label)
        self.label.setStyleSheet("QLabel{border: none;"
                                 "background-color: transparent;"
                                 "font-weight:100;}")

        self.close_btn = QPushButton('x')
        self.close_btn.setStyleSheet("background-color: transparent; border: none;")
        self.main_layout.addWidget(self.close_btn)

        self.setStyleSheet("QDialog{background-color: " + fill_color + ";"
                           "border-radius: 5px;"
                           "border: grey;}")

        self.close_btn.clicked.connect(self.close)

    def set_text(self, new_text: str):
        self.label.setText(new_text)

    def close(self):
        self.break_thread_run.emit(self.label.text(), self.category_name)
        self.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            # Start the drag operation
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(self.label.text())
            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.MoveAction)


class DraggableFrame(QFrame):
    def __init__(self, encompassing_obj=None, name=None, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.encompassing_obj = encompassing_obj
        self.name = name

    def dragEnterEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        source_label = event.source()
        if source_label and isinstance(source_label, LabelWithXButton):
            if self.name != source_label.category_name:
                source_label.close()
                self.encompassing_obj.add_value_label_to_category(
                    self.name, source_label.label.text())
                event.acceptProposedAction()   # NOTE: this cancels the dragging-back animation


class KeyboardShortcutSelectorUi(QDialog):
    def __init__(self, title="", **params):
        super().__init__()

        self.setWindowTitle(title)

        # Add a main layout to which everything will be added
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self._label = QLabel(" ", self)
        self._label.setStyleSheet("QLabel { background-color : white; padding: 5 2 5 2;}")

        self.main_layout.addWidget(self._label)

        self._user_message = QLabel(" ", self)
        self.main_layout.addWidget(self._user_message)

        self.buttons_layout = QHBoxLayout()
        self.main_layout.addLayout(self.buttons_layout)
        self.ok_btn = QPushButton('Select')
        self.cancel_btn = QPushButton('Cancel')
        self.buttons_layout.addWidget(self.ok_btn)
        self.buttons_layout.addWidget(self.cancel_btn)

        self.ok_btn.clicked.connect(self.on_ok_clicked)
        self.ok_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)

        if 'labels_manager' in params.keys():
            self.labels_manager = params['labels_manager']

    @property
    def label(self):
        return self._label.text()

    def on_ok_clicked(self):
        self.accept()

    def on_cancel_clicked(self):
        self.reject()

    @property
    def text_already_in_use(self):
        if hasattr(self, 'labels_manager'):
            if self._label.text() in self.labels_manager.all_action_names:
                return False
        return True

    def keyPressEvent(self, event):

        self._user_message.setText("")
        self.ok_btn.setEnabled(False)

        # Capture modifier keys like Ctrl, Shift, Alt
        modifiers = []
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            modifiers.append("Ctrl")
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            modifiers.append("Shift")
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            modifiers.append("Alt")
        if event.modifiers() & Qt.KeyboardModifier.MetaModifier:
            modifiers.append("Meta")

        # Get the key and create a string that represents the full key stroke
        key = event.key()
        base_key_name = QKeySequence(key).toString() if key not in [16777248, 16777249,
                                                                    16777250, 16777251] else ""

        if modifiers:
            key_name = "+".join(modifiers) + "+" + base_key_name
        else:
            key_name = base_key_name

        self._label.setText(key_name)

        if not self.text_already_in_use:
            self._user_message.setText("This key is already assigned to another action")
        elif len(modifiers) >= 1 and base_key_name != "":
            self.ok_btn.setEnabled(True)


class LabelsSelectionPerCategory(QWidget):
    def __init__(self, categories_to_values_df, value_selection_dialog, on_button_click=None,
                 containing_obj=None,
                 label_style="QLabel{background-color: transparent;}",
                 frame_style="QFrame{background-color: white;}"
                 ):
        super().__init__()
        self.containing_obj = containing_obj
        self.categories_to_values_df = categories_to_values_df
        self.category_col_name = categories_to_values_df.columns[0]
        self.value_col_name = categories_to_values_df.columns[1]
        self.grid_layout = QGridLayout(self)
        self.setLayout(self.grid_layout)
        self.on_button_click = on_button_click
        self.value_selection_dialog = value_selection_dialog
        self.label_style = label_style
        self.frame_style = frame_style
        self.create_ui()

    @property
    def layouts_widgets_mapping(self):
        return self._layouts_widgets_mapping

    @property
    def updated_categories_to_values_df(self):
        df = pd.DataFrame(self._layouts_widgets_mapping).T.reset_index()
        df['values'] = df['widgets'].apply(lambda x: list(x.keys()))
        df.drop(columns=['layout', 'widgets'], inplace=True)
        df.rename(columns={'index': self.category_col_name,
                           'values': self.value_col_name}, inplace=True)
        return df

    def create_ui(self):
        self._category_name_widgets_list = []
        self._values_widgets_list = []
        self._layouts_widgets_mapping = {}
        for i in range(self.categories_to_values_df.shape[0]):
            category_name = self.categories_to_values_df.iloc[i, :][self.category_col_name]
            w1 = self.create_label(category_name)
            w2 = self.create_values_frame(category_name)
            in_layout = QHBoxLayout()
            in_layout.setContentsMargins(2, 4, 2, 4)
            self._layouts_widgets_mapping[category_name] = {'layout': in_layout, 'widgets': {}}
            w2.setLayout(in_layout)
            label_values = self.categories_to_values_df.iloc[i, :][self.value_col_name]
            for lbl_val in label_values:
                w3 = LabelWithXButton(lbl_val, category_name)
                w3.break_thread_run.connect(self.label_closed)
                in_layout.addWidget(w3)
                self._layouts_widgets_mapping[category_name]['widgets'][lbl_val] = w3
            in_layout.addStretch(1)
            self.grid_layout.addWidget(w1, i, 0)
            self.grid_layout.addWidget(w2, i, 1)
            w4 = self.create_and_connect_button("+", category_name)
            self.grid_layout.addWidget(w4, i, 2)
            self._category_name_widgets_list.append(w1)
            self._values_widgets_list.append(w2)

    def create_values_frame(self, category_name):
        f = DraggableFrame(self, name=category_name)
        f.setStyleSheet(self.frame_style)
        return f

    def create_label(self, text: str) -> QLabel:
        x = QLabel(text)
        x.setStyleSheet(self.label_style)
        return x

    def create_and_connect_button(self, text, category_name):
        b = QPushButton(text=text)
        b.clicked.connect(self.open_value_selection_dialog(self, category_name))
        return b

    def label_closed(self, label, category_name):
        popped_widget = self._layouts_widgets_mapping[category_name]['widgets'].pop(label)
        self._layouts_widgets_mapping[category_name]['layout'].removeWidget(popped_widget)

    @property
    def all_action_names(self):
        actions_lists = []
        actions_lists += [list(v['widgets'].keys())
                          for k, v in self._layouts_widgets_mapping.items()]
        actions_lists_flat = flatten_list_of_lists([[x] if isinstance(x, str) else x
                                                    for x in actions_lists])
        return actions_lists_flat

    def add_value_label_to_category(self, category_name: str, new_value: str):
        w2 = self.create_values_frame(category_name)
        in_layout = QHBoxLayout()
        in_layout.setContentsMargins(2, 4, 2, 4)
        w2.setLayout(in_layout)
        for k in self._layouts_widgets_mapping[category_name]['widgets'].keys():
            w3 = LabelWithXButton(k, category_name=category_name)
            w3.break_thread_run.connect(self.label_closed)
            in_layout.addWidget(w3)
        w3 = LabelWithXButton(new_value, category_name=category_name)
        w3.break_thread_run.connect(self.label_closed)
        in_layout.addWidget(w3)
        in_layout.addStretch(1)
        self._layouts_widgets_mapping[category_name]['layout'] = in_layout
        self._layouts_widgets_mapping[category_name]['widgets'][new_value] = w3

        cat_num = self.categories_to_values_df.index[
            self.categories_to_values_df[self.category_col_name] == category_name
        ][0]
        self.grid_layout.addWidget(w2, cat_num, 1)

    class open_value_selection_dialog:
        def __init__(self, outer_instance, category=""):
            self.title = category
            self.outer_instance = outer_instance
            self.params = {'labels_manager': outer_instance}

        def __call__(self):
            self.value_selector = \
                self.outer_instance.value_selection_dialog(title=self.title, **self.params)
            reply = self.value_selector.exec()
            self.value_selector.deleteLater()
            if reply == 1:
                self.outer_instance.add_value_label_to_category(self.title,
                                                                self.value_selector.label)
