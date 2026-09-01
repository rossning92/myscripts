import { spawn } from "child_process";
import { withActivePage } from "./browser-core.js";
import { DAEMON_PORT } from "./config.js";

export async function screencast() {
  await withActivePage(() => {});

  const viewerUrl = `http://127.0.0.1:${DAEMON_PORT}/screencast`;
  const opener =
    process.platform === "win32"
      ? "start"
      : process.platform === "darwin"
        ? "open"
        : "xdg-open";
  spawn(opener, [viewerUrl], {
    detached: true,
    stdio: "ignore",
    shell: process.platform === "win32",
  }).unref();

  return `Screencast viewer opened at: ${viewerUrl}`;
}
