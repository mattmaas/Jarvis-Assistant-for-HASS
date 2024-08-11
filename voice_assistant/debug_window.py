from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt5.QtCore import pyqtSlot, QObject, pyqtSignal

class DebugWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.debug_history = []

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
        self.debug_history.append(text)
        self.textEdit.append(text)

    def showEvent(self, event):
        super().showEvent(event)
        self.textEdit.clear()
        for text in self.debug_history:
            self.textEdit.append(text)

    def closeEvent(self, event):
        event.ignore()
        self.hide()

class DebugSignals(QObject):
    debug_signal = pyqtSignal(str)

debug_signals = DebugSignals()
