import sys
import threading
import websocket
import json
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon
from voice_assistant import VoiceAssistant
from debug_window import DebugWindow, debug_signals
import os

# Get the directory of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Define the path to the config.ini file
CONFIG_PATH = os.path.join(current_dir, 'config.ini')

def main():
    app = QApplication(sys.argv)
    
    # Create the voice assistant with the config path and increased sensitivity
    assistant = VoiceAssistant(CONFIG_PATH, sensitivity=0.7)
    
    # Create the debug window
    debug_window = DebugWindow()
    debug_signals.debug_signal.connect(debug_window.append_text)
    debug_window.hide()  # Initially hide the debug window
    
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
        ws_protocol = "wss://" if assistant.ha_url.startswith("https://") else "ws://"
        ws_url = f"{ws_protocol}{assistant.ha_url.split('://', 1)[1]}/api/websocket"
        debug_signals.debug_signal.emit(f"Connecting to WebSocket: {ws_url}")
        try:
            ws = websocket.create_connection(ws_url)
            auth_message = {
                "type": "auth",
                "access_token": assistant.ha_token
            }
            auth_required = json.loads(ws.recv())
            debug_signals.debug_signal.emit(f"Auth required: {auth_required}")
            
            if auth_required.get("type") == "auth_required":
                ws.send(json.dumps(auth_message))
                auth_result = json.loads(ws.recv())
                debug_signals.debug_signal.emit(f"Auth result: {auth_result}")
                
                if auth_result.get("type") == "auth_ok":
                    # Get pipelines
                    pipeline_message = {
                        "type": "assist_pipeline/pipeline/list",
                        "id": 1  # Add a unique ID for the message
                    }
                    ws.send(json.dumps(pipeline_message))
                    result = json.loads(ws.recv())
                    debug_signals.debug_signal.emit(f"Pipelines result: {result}")
                    
                    while result.get("type") != "result" or result.get("id") != 1:
                        result = json.loads(ws.recv())
                        debug_signals.debug_signal.emit(f"Additional response: {result}")
                    
                    pipelines = result.get("result", {}).get("pipelines", [])
                    preferred_pipeline = result.get("result", {}).get("preferred_pipeline")
                    
                    # Find the "jarvis" pipeline or use the first one as default
                    default_pipeline = next((p for p in pipelines if p.get('name', '').lower() == 'jarvis'), pipelines[0] if pipelines else None)
                    
                    for pipeline in pipelines:
                        pipeline_name = pipeline.get('name', 'Unknown')
                        pipeline_id = pipeline.get('id')
                        action = QAction(pipeline_name, ha_menu)
                        action.triggered.connect(lambda checked, p=pipeline_id: set_ha_pipeline(p))
                        ha_menu.addAction(action)
                    
                    # Set default pipeline
                    if pipelines:
                        default_pipeline = next((p for p in pipelines if p.get('name', '').lower() == 'jarvis'), pipelines[0])
                        set_ha_pipeline(default_pipeline.get('id'))
                        debug_signals.debug_signal.emit(f"Set default pipeline: {default_pipeline.get('name')}")
                else:
                    debug_signals.debug_signal.emit(f"Authentication failed: {auth_result}")
            else:
                debug_signals.debug_signal.emit(f"Unexpected response: {auth_required}")
            
            ws.close()
        except Exception as e:
            debug_signals.debug_signal.emit(f"Error updating pipelines: {e}")
    
    # Function to set the selected Home Assistant pipeline
    def set_ha_pipeline(pipeline_id):
        if pipeline_id:
            assistant.ha_pipeline = pipeline_id
            debug_signals.debug_signal.emit(f"Selected pipeline: {pipeline_id}")
        else:
            debug_signals.debug_signal.emit("No pipeline selected")
    
    # Add action to update pipelines
    update_pipelines_action = ha_menu.addAction("Update Pipelines")
    update_pipelines_action.triggered.connect(update_ha_pipelines)
    
    exit_action = menu.addAction("Exit")
    
    # Connect menu actions
    start_action.triggered.connect(assistant.start)
    stop_action.triggered.connect(lambda: (assistant.stop(), assistant.rgb_control.set_profile("lava")))  # Load 'lava' profile when stopped
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
