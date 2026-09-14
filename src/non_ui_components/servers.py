from PySide6.QtWidgets import QWidget
from src.ui_components.misc_widgets.dialogs_and_messages import QDialogFreeTextButtons


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
            # A Cancel button, so a long job (zipping a big folder onto a slow volume) can be
            # stopped. The dialog's own handler closes it; 'on_cancel' is what stops the job.
            msg = QDialogFreeTextButtons(button_texts=['Cancel'],
                                         title_text=params.get('title', 'Zipping'),
                                         message_text=params.get('msg', 'Zipping files...'),
                                         btn_width=90)
            on_cancel = params.get('on_cancel')
            if on_cancel is not None:
                msg.buttons['Cancel'].clicked.connect(on_cancel)
            self.message_boxes[params['caller_id']] = msg
            msg.open()

        if params['call_type'] == 'remove_prompt_message':
            # Closed, not just dropped: forgetting the last reference leaves the window on screen
            # until Python happens to collect it.
            msg = self.message_boxes.pop(params['caller_id'], None)
            if msg is not None:
                msg.close()

        if params['call_type'] == 'show_error_message':
            # A background job that failed has no other way to say so - it cannot build widgets
            # of its own.
            msg = QDialogFreeTextButtons(button_texts=['OK'],
                                         title_text=params.get('title', 'Error'),
                                         message_text=params.get('msg', ''),
                                         btn_width=90)
            msg.exec()
