import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QTextEdit, QWidget, QScrollBar
from PyQt5.QtGui import QColor, QPalette, QFont, QTextCharFormat, QTextCursor
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QEvent, QRectF

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
        palette.setColor(QPalette.Window, QColor(240, 240, 240))  # Light gray background
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
                background-color: #F0F0F0;
                border: none;
                border-radius: 10px;
                padding: 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 16px;
            }
            QScrollBar:vertical {
                border: none;
                background: #F0F0F0;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #BDBDBD;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        layout.addWidget(self.conversation)

        conversation_signals.update_signal.connect(self.update_conversation)

    def update_conversation(self, message, is_user):
        # Check if the last message is the same as the current one
        cursor = self.conversation.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.select(QTextCursor.BlockUnderCursor)
        last_message = cursor.selectedText()
        if f"{'You' if is_user else 'Jarvis'}: {message}" == last_message:
            return  # Skip duplicate messages

        # Create text block format
        block_format = cursor.blockFormat()
        block_format.setAlignment(Qt.AlignRight if is_user else Qt.AlignLeft)
        cursor.setBlockFormat(block_format)

        # Create text character format
        char_format = QTextCharFormat()
        char_format.setFontFamily("Segoe UI")
        char_format.setFontPointSize(14)

        # Set bubble color and text color
        if is_user:
            bubble_color = QColor(0, 122, 255)  # Blue for user messages
            text_color = QColor(255, 255, 255)  # White text
        else:
            bubble_color = QColor(229, 229, 234)  # Light gray for Jarvis messages
            text_color = QColor(0, 0, 0)  # Black text

        char_format.setBackground(bubble_color)
        char_format.setForeground(text_color)

        # Insert new block if not at the beginning
        if self.conversation.toPlainText():
            cursor.insertBlock()

        # Insert the message
        cursor.insertText(f"{'You' if is_user else 'Jarvis'}: {message}", char_format)

        # Scroll to the bottom
        self.conversation.verticalScrollBar().setValue(self.conversation.verticalScrollBar().maximum())

    def closeEvent(self, event):
        event.ignore()  # Ignore the close event
        self.hide()  # Hide the window instead of closing it

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ModernUI()
    ex.show()
    sys.exit(app.exec_())
