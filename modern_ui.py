import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton
from PyQt5.QtGui import QColor, QPalette, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class ConversationSignals(QObject):
    update_signal = pyqtSignal(str, bool)

conversation_signals = ConversationSignals()

class ModernUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Jarvis Assistant')
        self.setGeometry(100, 100, 400, 600)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Conversation display
        self.conversation = QTextEdit()
        self.conversation.setReadOnly(True)
        self.conversation.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 100);
                border: none;
                border-radius: 10px;
                padding: 10px;
                color: #333;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }
        """)
        main_layout.addWidget(self.conversation)

        # Close button
        close_button = QPushButton("Close")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 150);
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
                color: #333;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 200);
            }
        """)
        close_button.clicked.connect(self.hide)
        main_layout.addWidget(close_button, alignment=Qt.AlignRight)

        conversation_signals.update_signal.connect(self.update_conversation)

    def update_conversation(self, message, is_user):
        if is_user:
            self.conversation.append(f'<div style="text-align: right;"><span style="background-color: #DCF8C6; padding: 5px; border-radius: 5px;">You: {message}</span></div>')
        else:
            self.conversation.append(f'<div style="text-align: left;"><span style="background-color: #E5E5EA; padding: 5px; border-radius: 5px;">Jarvis: {message}</span></div>')
        self.conversation.verticalScrollBar().setValue(self.conversation.verticalScrollBar().maximum())

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QColor
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ModernUI()
    ex.show()
    sys.exit(app.exec_())
