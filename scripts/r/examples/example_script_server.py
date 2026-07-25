from _scriptmanager import ScriptManager
from _scriptserver import ScriptServer
from utils.logger import setup_logger

if __name__ == "__main__":
    setup_logger()
    script_manager = ScriptManager(start_daemon=False)
    script_server = ScriptServer(script_manager=script_manager, port=8888)
    script_server.start_server()
    script_server.join_server_thread()
