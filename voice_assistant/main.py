import sys
import os
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QIcon
from voice_assistant import VoiceAssistant
from debug_window import DebugWindow, debug_signals

def main():
    app = QApplication(sys.argv)
    
    # Get the Porcupine access key from an environment variable
    access_key = os.environ.get('PORCUPINE_ACCESS_KEY')
    if not access_key:
        print("Error: PORCUPINE_ACCESS_KEY environment variable not set")
        sys.exit(1)
    
    # Create the voice assistant
    assistant = VoiceAssistant(access_key)
    
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
