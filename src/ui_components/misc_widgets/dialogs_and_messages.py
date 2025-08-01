from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QMessageBox, QLabel, QPushButton, QHBoxLayout, QWidget, QVBoxLayout,
                               QDialog, QDialogButtonBox)


def prompt_message(title_text: str, message_text: str):
    """
    Prompt a message, with two buttons: Ok and Cancel
    """
    msg_box = CustomQDialogButtonBox(title_text,
                                     message_text,
                                     buttons=QDialogButtonBox.StandardButton.Cancel |
                                             QDialogButtonBox.StandardButton.Ok,
                                     )
    msg_box.exec()


class TextMessageBoxNoBottons(QDialog):
    """
    Only text. No buttons
    """
    def __init__(self, header_text: str = '', text: str = ''):
        super().__init__()
        self.setWindowTitle(header_text)
        self.setFixedSize(200, 100)
        label = QLabel(text, self)
        layout = QVBoxLayout()
        layout.addWidget(label)
        self.setLayout(layout)


class CustomQDialogButtonBox(QDialog):
    def __init__(self, title_text: str = "", message_text: str = "",
                 buttons=QDialogButtonBox.StandardButton.Cancel |
                         QDialogButtonBox.StandardButton.Ok,
                 ):
        super().__init__()

        self.setWindowTitle(title_text)

        self.buttonBox = QDialogButtonBox(buttons)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        message = QLabel(message_text)
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def set_button(self, btn_type, button_text):
        self.buttonBox.button(btn_type).setText(button_text)



class QDialogFreeTextButtons(QDialog):
    """
    After a buttons is clicked - attribute 'selected_button' will contain the button's text
    E.g.::
    dialog = QDialogFreeTextButtons(button_texts=['Cancel', 'Replace', 'Keep both'])
    if dialog.exec() == QDialog.Accepted:
        print(dialog.selected_button)

    Implement the accept method to decide what do to after one of the buttons was click
    """
    def __init__(self,
                 button_texts: list[str],
                 title_text: str = "",
                 message_text: str = "",
                 btn_width: int = None,
                 align_buttons: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft):
        super().__init__()

        # Will only be assigned with a value after one of the buttons is clicked
        self.selected_button_ = None

        self.button_texts = button_texts
        self.buttons_dict = {}
        self.functions_dict = {}

        self.setWindowTitle(title_text)

        self.layout = QVBoxLayout()
        self.message = QLabel(message_text)
        self.layout.addWidget(self.message)
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setAlignment(align_buttons)
        self.layout.addLayout(self.buttons_layout)

        for txt in button_texts:
            self.buttons_dict[txt] = QPushButton(txt)
            if btn_width is not None:
                self.buttons_dict[txt].setFixedWidth(btn_width)
            self.functions_dict[txt] = self.__parameterized_func(btn_text=txt, obj=self)
            self.buttons_dict[txt].clicked.connect(self.functions_dict[txt])
            self.buttons_layout.addWidget(self.buttons_dict[txt])

        self.setLayout(self.layout)
        self.installEventFilter(self)

    def set_message_text(self, text: str):
        self.message.setText(text)

    @property
    def buttons(self):
        return self.buttons_dict

    def generate_click_on_button(self, button_text: str):
        return self.functions_dict[button_text]()

    @property
    def clicked_button(self):
        return self.selected_button_

    class __parameterized_func():
        def __init__(self, btn_text, obj=None):
            self.btn_text = btn_text
            self.obj = obj

        def __call__(self, *args, **kwargs):
            self.obj.selected_button_ = self.btn_text
            self.obj.accept()



class QDialogButtonsAndWidgets(QWidget):
    """
    A widget which contains widgets above, and a few buttons at the bottom
    Button actions need to be implemented
    """
    def __init__(self,
                 widgets_list: list,
                 buttons_dict: dict   # Dictionary of type: {button_text: function_to_invoke}
                 ):
        super().__init__()

        self.layout = QVBoxLayout()
        self.buttons_layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.layout.addLayout(self.buttons_layout)

        for widg in widgets_list:
            self.layout.addWidget(widg)

        for btn_name in buttons_dict.keys():
            new_btn = QPushButton(btn_name, self)
            if buttons_dict[btn_name] is not None:
                new_btn.clicked.connect(buttons_dict[btn_name])
            self.buttons_layout.addWidget(new_btn)

    def add_button(self, btn_text, invoke_when_clicked):
        self.buttons_layout.addWidget(QPushButton(btn_text, invoke_when_clicked))


class message_box_w_arrow_keys_enabled(QMessageBox):
    """
    When we want the user to click the right/left arrow keys to navigate between buttons
    """
    def __init__(self,
                 message: str = "",
                 title: str = "",
                 buttons=[QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No],
                 default_button_ind: int = None):
        super().__init__()
        self.setWindowTitle(title)
        self.setText(message)
        for btn in buttons:
            button = self.addButton(btn)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if default_button_ind is not None:
            self.setDefaultButton(buttons[default_button_ind])
