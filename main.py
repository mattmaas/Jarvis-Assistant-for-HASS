import sys
import threading
import websocket
import json
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QActionGroup
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer
from voice_assistant import JarvisAssistant
from debug_window import DebugWindow, debug_signals
# from modern_ui import ModernUI, conversation_signals
import os
import winreg
import time
import logging

# Get the directory of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Define the path to the config.ini file
CONFIG_PATH = os.path.join(current_dir, 'config.ini')

# Configure logging
logging.basicConfig(filename='jarvis_assistant.log', level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AssistantThread(threading.Thread):
    def __init__(self, assistant):
        threading.Thread.__init__(self)
        self.assistant = assistant
        self.daemon = True

    def run(self):
        try:
            self.assistant.start()
        except Exception as e:
            logger.error(f"Error in assistant thread: {e}")
            debug_signals.debug_signal.emit(f"Error in assistant thread: {e}")

def main():
    app = QApplication(sys.argv)
    
    # Create the Jarvis assistant with the config path
    assistant = JarvisAssistant(CONFIG_PATH, logger)
    
    # Create the debug window
    debug_window = DebugWindow()
    debug_signals.debug_signal.connect(debug_window.append_text)
    debug_window.hide()  # Initially hide the debug window
    
    # # Create the modern UI
    # modern_ui = ModernUI()
    # modern_ui.hide()  # Initially hide the modern UI
    
    # # Connect the conversation signals to the ModernUI
    # conversation_signals.update_signal.connect(modern_ui.update_conversation)
    
    # Create the system tray icon
    icon = QIcon("icon.png")  # Make sure to have an icon file
    tray = QSystemTrayIcon(icon)
    
    # Create the tray menu
    menu = QMenu()
    start_action = menu.addAction("Start Listening")
    stop_action = menu.addAction("Stop Listening")
    debug_action = menu.addAction("Show Debug Window")
    # modern_ui_action = menu.addAction("Show Conversation")
    # modern_ui_action.triggered.connect(modern_ui.show)
    
    # Create a submenu for Home Assistant pipelines
    ha_menu = QMenu("Home Assistant Pipelines")
    pipeline_group = QActionGroup(ha_menu)
    pipeline_group.setExclusive(True)
    menu.addMenu(ha_menu)

    # Create a submenu for startup options
    startup_menu = menu.addMenu("Startup Options")
    enable_startup_action = startup_menu.addAction("Enable on Startup")
    disable_startup_action = startup_menu.addAction("Disable on Startup")
    enable_startup_action.setCheckable(True)
    disable_startup_action.setCheckable(True)
    
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
                    
                    # Add "Auto (Interpreter)" option
                    auto_action = QAction("Auto (Interpreter)", ha_menu, checkable=True)
                    auto_action.setData("auto")
                    auto_action.triggered.connect(lambda checked, p="auto": set_ha_pipeline(p))
                    pipeline_group.addAction(auto_action)
                    ha_menu.addAction(auto_action)
                    
                    # Add a separator
                    ha_menu.addSeparator()
                    
                    for pipeline in pipelines:
                        pipeline_name = pipeline.get('name', 'Unknown')
                        pipeline_id = pipeline.get('id')
                        action = QAction(pipeline_name, ha_menu, checkable=True)
                        action.setData(pipeline_id)
                        action.triggered.connect(lambda checked, p=pipeline_id: set_ha_pipeline(p))
                        pipeline_group.addAction(action)
                        ha_menu.addAction(action)
                    
                    # Set default pipeline to "Auto" or the preferred pipeline
                    default_pipeline = "auto"
                    set_ha_pipeline(default_pipeline)
                    debug_signals.debug_signal.emit(f"Set default pipeline: {default_pipeline}")
                else:
                    debug_signals.debug_signal.emit(f"Authentication failed: {auth_result}")
            else:
                debug_signals.debug_signal.emit(f"Unexpected response: {auth_required}")
            
            ws.close()
        except Exception as e:
            debug_signals.debug_signal.emit(f"Error updating pipelines: {e}")
    
    # Function to set the selected Home Assistant pipeline
    def set_ha_pipeline(pipeline_id):
        assistant.ha_pipeline = pipeline_id
        for action in pipeline_group.actions():
            action.setChecked(action.data() == pipeline_id)
        
        if pipeline_id == "auto":
            debug_signals.debug_signal.emit("Auto pipeline selection enabled")
        elif pipeline_id:
            debug_signals.debug_signal.emit(f"Selected pipeline: {pipeline_id}")
        else:
            debug_signals.debug_signal.emit("No pipeline selected")
    
    # Add action to update pipelines
    update_pipelines_action = ha_menu.addAction("Update Pipelines")
    update_pipelines_action.triggered.connect(update_ha_pipelines)
    
    restart_action = menu.addAction("Restart")
    exit_action = menu.addAction("Exit")
    
    # Function to enable/disable startup
    def toggle_startup(enable):
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_ALL_ACCESS) as registry_key:
                if enable:
                    winreg.SetValueEx(registry_key, "JarvisAssistant", 0, winreg.REG_SZ, sys.argv[0])
                    enable_startup_action.setChecked(True)
                    disable_startup_action.setChecked(False)
                else:
                    winreg.DeleteValue(registry_key, "JarvisAssistant")
                    enable_startup_action.setChecked(False)
                    disable_startup_action.setChecked(True)
        except WindowsError:
            debug_signals.debug_signal.emit(f"Error {'enabling' if enable else 'disabling'} startup")

    # Check current startup status
    def check_startup_status():
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_READ) as registry_key:
                value, _ = winreg.QueryValueEx(registry_key, "JarvisAssistant")
                if value == sys.argv[0]:
                    enable_startup_action.setChecked(True)
                    disable_startup_action.setChecked(False)
                else:
                    enable_startup_action.setChecked(False)
                    disable_startup_action.setChecked(True)
        except WindowsError:
            enable_startup_action.setChecked(False)
            disable_startup_action.setChecked(True)

    # Connect menu actions
    start_action.triggered.connect(lambda: QTimer.singleShot(0, assistant.start))
    stop_action.triggered.connect(lambda: QTimer.singleShot(0, assistant.stop))
    debug_action.triggered.connect(debug_window.show)
    def restart_assistant():
        debug_signals.debug_signal.emit("Restarting application...")
        assistant.stop()
        time.sleep(1)  # Give some time for the assistant to stop
        python = sys.executable
        os.execl(python, python, *sys.argv)

    restart_action.triggered.connect(restart_assistant)
    exit_action.triggered.connect(lambda: (assistant.rgb_control.set_profile("lava"), app.quit()))
    enable_startup_action.triggered.connect(lambda: toggle_startup(True))
    disable_startup_action.triggered.connect(lambda: toggle_startup(False))
    
    tray.setContextMenu(menu)
    tray.show()
    
    # Start the voice assistant in a separate thread
    assistant_thread = AssistantThread(assistant)
    assistant_thread.start()
    
    # Enable tray icon double-click to show/hide main window
    tray.activated.connect(lambda reason: exit_action.trigger() if reason == QSystemTrayIcon.DoubleClick else None)
    
    # Update pipelines on startup
    update_ha_pipelines()

    # Check startup status on launch
    check_startup_status()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
