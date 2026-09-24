import os from "os";
import path from "path";

function validateSessionName(session) {
  if (session == null) return null;
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(session)) {
    throw new Error(
      "Session names must be 1-64 characters using letters, numbers, '.', '_', or '-'",
    );
  }
  return session;
}

function hashSession(session) {
  let hash = 2166136261;
  for (const character of session) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export const SESSION = validateSessionName(process.env.BROWSERCLI_SESSION);
export const USER_DATA_DIR = SESSION
  ? path.join(os.homedir(), ".browsercli-sessions", SESSION)
  : path.join(os.homedir(), ".browsercli-user-data");
// Keep the original ports for the default session. Named sessions get a stable
// pair of ports, allowing their daemons and Chrome profiles to run concurrently.
export const DEBUG_PORT = SESSION
  ? 30000 + (hashSession(SESSION) % 15000) * 2
  : 21222;
export const BROWSER_URL = `http://127.0.0.1:${DEBUG_PORT}`;
export const WINDOW_WIDTH = 1024;
export const WINDOW_HEIGHT = 768;
export const DAEMON_PORT = DEBUG_PORT + 2;
