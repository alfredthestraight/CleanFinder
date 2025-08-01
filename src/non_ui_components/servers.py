from PySide6.QtWidgets import QWidget
from src.ui_components.misc_widgets.dialogs_and_messages import TextMessageBoxNoBottons


class ThreadsUiServer(QWidget):
    """
    A server that can used (w.g., by a QThread, or any class which is not a widget)
    to present UI elements to the user
    """

    def __init__(self, uis_manager):
        super().__init__()
        self.uis_manager = uis_manager
        self.progress_bars = {}
        self.timers = {}
        self.message_boxes = {}
        self.position_on_screen = None

    def show_progress_bar(self, caller_id: int):
        self.progress_bars[caller_id].show()

    def __call__(self, params):
        if params['call_type'] == 'show_prompt_message':
            msg = TextMessageBoxNoBottons('Zipping', 'Zipping files...')
            self.message_boxes[params['caller_id']] = msg
            msg.open()

        if params['call_type'] == 'remove_prompt_message':
            try:
                self.message_boxes.pop(params['caller_id'])
            except KeyError:
                pass



