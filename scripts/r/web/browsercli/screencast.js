import { spawn } from "child_process";
import { getExecutablePath, withActivePage } from "./browser-core.js";
import { currentSession, DAEMON_PORT, sessionQuery } from "./config.js";

export async function screencast() {
  await withActivePage(() => {});

  const viewerUrl = `http://127.0.0.1:${DAEMON_PORT}/screencast${sessionQuery(currentSession())}`;
  const desktopPlatform = ["win32", "darwin", "linux"].includes(process.platform);
  const opener = desktopPlatform ? getExecutablePath() : "xdg-open";
  const args = desktopPlatform ? [`--app=${viewerUrl}`] : [viewerUrl];
  spawn(opener, args, {
    detached: true,
    stdio: "ignore",
  }).unref();

  return `Screencast viewer opened at: ${viewerUrl}`;
}
