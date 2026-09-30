import { AsyncLocalStorage } from "async_hooks";
import { getProfileDir } from "./app-paths.js";

export function validateSessionName(session) {
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

// One daemon serves every session. The daemon runs each request in the
// context of the session named by its ?session= query parameter.
export const sessionContext = new AsyncLocalStorage();
export const currentSession = () => sessionContext.getStore() ?? null;
export const sessionQuery = (session) => (session ? `?session=${session}` : "");
export const profileDir = () => getProfileDir(currentSession());
// Keep the original port for the default session. Named sessions get a stable
// port, allowing their Chrome profiles to run concurrently.
export function debugPort() {
  const session = currentSession();
  return session ? 30000 + (hashSession(session) % 15000) * 2 : 21222;
}
export const WINDOW_WIDTH = 1024;
export const WINDOW_HEIGHT = 768;
export const DAEMON_PORT = 21224;
