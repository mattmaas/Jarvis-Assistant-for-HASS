from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt5.QtCore import pyqtSlot, QObject, pyqtSignal

class DebugWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        self.textEdit = QTextEdit()
        self.textEdit.setReadOnly(True)
        layout.addWidget(self.textEdit)
        self.setLayout(layout)
        self.setWindowTitle('Debug Window')
        self.setGeometry(300, 300, 600, 400)

    @pyqtSlot(str)
    def append_text(self, text):
        self.textEdit.append(text)

class DebugSignals(QObject):
    debug_signal = pyqtSignal(str)

debug_signals = DebugSignals()
