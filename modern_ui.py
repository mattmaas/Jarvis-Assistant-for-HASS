import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, QFrame
from PyQt5.QtGui import QColor, QPalette, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QPoint

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
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        # Top bar
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            QFrame {
                background-color: #2C2C2C;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
        """)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(10, 5, 10, 5)

        # Title
        title = QLabel("Jarvis Assistant")
        title.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }
        """)
        top_bar_layout.addWidget(title)

        # Spacer
        top_bar_layout.addStretch()

        # Window controls
        for icon_path, tip, slot in [
            ("minimize.png", "Minimize", self.showMinimized),
            ("maximize.png", "Maximize", self.toggle_maximize),
            ("close.png", "Close", self.close)
        ]:
            btn = QPushButton()
            btn.setIcon(QIcon(icon_path))
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 30);
                }
            """)
            top_bar_layout.addWidget(btn)

        main_layout.addWidget(top_bar)

        # Content area
        content_area = QFrame()
        content_area.setStyleSheet("""
            QFrame {
                background-color: rgba(44, 44, 44, 200);
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }
        """)
        content_layout = QVBoxLayout(content_area)

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
        content_layout.addWidget(self.conversation)

        main_layout.addWidget(content_area)

        conversation_signals.update_signal.connect(self.update_conversation)

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

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
        painter.setBrush(QColor(44, 44, 44, 200))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ModernUI()
    ex.show()
    sys.exit(app.exec_())
