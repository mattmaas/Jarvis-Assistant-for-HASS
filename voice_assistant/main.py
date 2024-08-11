import sys
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QIcon
from voice_assistant import VoiceAssistant
from debug_window import DebugWindow, debug_signals
from config import PORCUPINE_ACCESS_KEY

def main():
    app = QApplication(sys.argv)
    
    # Create the voice assistant with the access key from config.py
    assistant = VoiceAssistant(PORCUPINE_ACCESS_KEY)
    
    # Create the debug window
    debug_window = DebugWindow()
    debug_signals.debug_signal.connect(debug_window.append_text)
    
    # Create the system tray icon
    icon = QIcon("icon.png")  # Make sure to have an icon file
    tray = QSystemTrayIcon(icon)
    
    # Create the tray menu
    menu = QMenu()
    start_action = menu.addAction("Start Listening")
    stop_action = menu.addAction("Stop Listening")
    debug_action = menu.addAction("Show Debug Window")
    exit_action = menu.addAction("Exit")
    
    # Connect menu actions
    start_action.triggered.connect(assistant.start)
    stop_action.triggered.connect(assistant.stop)
    debug_action.triggered.connect(debug_window.show)
    exit_action.triggered.connect(app.quit)
    
    tray.setContextMenu(menu)
    tray.show()
    
    # Start the voice assistant
    assistant.start()
    
    # Enable tray icon double-click to show/hide main window
    tray.activated.connect(lambda reason: exit_action.trigger() if reason == QSystemTrayIcon.DoubleClick else None)
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
