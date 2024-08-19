import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QTextEdit, QWidget
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QEvent

class ConversationSignals(QObject):
    update_signal = pyqtSignal(str, bool)

conversation_signals = ConversationSignals()

class ModernUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Jarvis Assistant')
        self.setGeometry(100, 100, 400, 600)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        # Set the window background color
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(44, 44, 44))
        self.setPalette(palette)

        # Create central widget and layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Conversation display
        self.conversation = QTextEdit()
        self.conversation.setReadOnly(True)
        self.conversation.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 50);
                border: none;
                border-radius: 10px;
                padding: 10px;
                color: #FFFFFF;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.conversation)

        conversation_signals.update_signal.connect(self.update_conversation)

    def update_conversation(self, message, is_user):
        # Check if the last message is the same as the current one
        last_message = self.conversation.toPlainText().split('\n')[-1] if self.conversation.toPlainText() else ""
        if f"{'You' if is_user else 'Jarvis'}: {message}" == last_message:
            return  # Skip duplicate messages

        if is_user:
            self.conversation.append(f'<div style="text-align: right;"><span style="background-color: #DCF8C6; padding: 5px; border-radius: 5px;">You: {message}</span></div>')
        else:
            if message.strip():  # Only append non-empty Jarvis responses
                self.conversation.append(f'<div style="text-align: left;"><span style="background-color: #E5E5EA; padding: 5px; border-radius: 5px;">Jarvis: {message}</span></div>')
        self.conversation.verticalScrollBar().setValue(self.conversation.verticalScrollBar().maximum())

    def closeEvent(self, event):
        event.ignore()  # Ignore the close event
        self.hide()  # Hide the window instead of closing it

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ModernUI()
    ex.show()
    sys.exit(app.exec_())
