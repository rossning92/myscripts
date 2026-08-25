import os from "os";
import path from "path";

export const USER_DATA_DIR = path.join(os.homedir(), ".browsercli-user-data");
export const DEBUG_PORT = 21222;
export const BROWSER_URL = `http://127.0.0.1:${DEBUG_PORT}`;
export const WINDOW_WIDTH = 1024;
export const WINDOW_HEIGHT = 768;
export const POST_CLICK_DELAY = 500;
export const ELEMENT_WAIT_TIMEOUT_MS = 10000;
export const ELEMENT_WAIT_INTERVAL_MS = 100;
export const DAEMON_PORT = DEBUG_PORT + 2;
