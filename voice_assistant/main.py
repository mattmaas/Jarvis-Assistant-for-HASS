import sys
import threading
import websocket
import json
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon
from voice_assistant import VoiceAssistant
from debug_window import DebugWindow, debug_signals
from config import CONFIG_PATH

def main():
    app = QApplication(sys.argv)
    
    # Create the voice assistant with the config path and increased sensitivity
    assistant = VoiceAssistant(CONFIG_PATH, sensitivity=0.7)
    
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
    
    # Create a submenu for Home Assistant pipelines
    ha_menu = menu.addMenu("Home Assistant Pipelines")
    
    # Function to update Home Assistant pipelines
    def update_ha_pipelines():
        ha_menu.clear()
        ws = websocket.create_connection(f"ws://{assistant.ha_url}/api/websocket")
        auth_message = {
            "type": "auth",
            "access_token": assistant.ha_token
        }
        ws.send(json.dumps(auth_message))
        ws.recv()  # Receive auth_ok message
        
        # Get pipelines
        ws.send(json.dumps({"type": "assist_pipeline/pipeline/list"}))
        result = json.loads(ws.recv())
        pipelines = result.get("result", [])
        
        for pipeline in pipelines:
            action = QAction(pipeline['name'], ha_menu)
            action.triggered.connect(lambda checked, p=pipeline['id']: set_ha_pipeline(p))
            ha_menu.addAction(action)
        
        ws.close()
    
    # Function to set the selected Home Assistant pipeline
    def set_ha_pipeline(pipeline_id):
        assistant.ha_pipeline = pipeline_id
        debug_signals.debug_signal.emit(f"Selected pipeline: {pipeline_id}")
    
    # Add action to update pipelines
    update_pipelines_action = ha_menu.addAction("Update Pipelines")
    update_pipelines_action.triggered.connect(update_ha_pipelines)
    
    exit_action = menu.addAction("Exit")
    
    # Connect menu actions
    start_action.triggered.connect(assistant.start)
    stop_action.triggered.connect(assistant.stop)
    debug_action.triggered.connect(debug_window.show)
    exit_action.triggered.connect(app.quit)
    
    tray.setContextMenu(menu)
    tray.show()
    
    # Start the voice assistant in a separate thread
    assistant_thread = threading.Thread(target=assistant.start)
    assistant_thread.daemon = True
    assistant_thread.start()
    
    # Enable tray icon double-click to show/hide main window
    tray.activated.connect(lambda reason: exit_action.trigger() if reason == QSystemTrayIcon.DoubleClick else None)
    
    # Update pipelines on startup
    update_ha_pipelines()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
