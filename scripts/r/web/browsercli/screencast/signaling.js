import { fork } from "child_process";
import { fileURLToPath } from "url";
import { WebSocketServer } from "ws";
import { debugPort, sessionContext, validateSessionName } from "../config.js";
import { hasAudioSink, sinkName } from "./audio.js";

const senderPath = fileURLToPath(new URL("./sender.js", import.meta.url));

async function startPeer(socket, message) {
  const offer = JSON.parse(message);
  if (offer.type !== "offer" || typeof offer.sdp !== "string") {
    throw new Error("Invalid WebRTC offer");
  }
  if (!(await hasAudioSink())) throw new Error("Audio capture is unavailable");

  const response = await fetch(`http://127.0.0.1:${debugPort()}/json`, {
    signal: AbortSignal.timeout(2000),
  });
  const targets = await response.json();
  const target = targets.find(({ id, type }) => id === offer.targetId && type === "page");
  if (!target) throw new Error("No browser tab");
  if (socket.readyState !== socket.OPEN) return;

  const cdpUrl = new URL(target.webSocketDebuggerUrl);
  cdpUrl.host = `127.0.0.1:${debugPort()}`;
  // Isolate the native addon so a sender crash leaves browser controls running.
  const sender = fork(senderPath, [], { stdio: ["ignore", "ignore", "inherit", "ipc"] });
  const deadline = setTimeout(() => socket.close(1011, "WebRTC setup timed out"), 15000);
  sender.once("message", ({ answer, error }) => {
    clearTimeout(deadline);
    if (error) {
      socket.close(1011, "WebRTC setup failed");
    } else if (socket.readyState === socket.OPEN) {
      socket.send(JSON.stringify(answer));
    }
  });
  sender.on("error", () => socket.close(1011, "WebRTC sender unavailable"));
  sender.once("disconnect", () => socket.close(1011, "WebRTC capture stopped"));
  sender.once("close", () => {
    clearTimeout(deadline);
    socket.close(1011, "WebRTC sender stopped");
  });
  socket.once("close", () => {
    clearTimeout(deadline);
    if (sender.connected) sender.disconnect();
    if (sender.exitCode !== null || sender.signalCode !== null) return;
    const stop = setTimeout(() => sender.kill(), 2000);
    stop.unref();
    sender.once("close", () => clearTimeout(stop));
  });
  sender.send({ url: cdpUrl.href, sink: sinkName(), offer });
}

export function serveScreencastSignaling(server) {
  const signaling = new WebSocketServer({ noServer: true, maxPayload: 64 * 1024 });
  server.on("upgrade", (req, connection, head) => {
    try {
      const url = new URL(req.url, "http://localhost");
      const host = req.headers["x-forwarded-host"] || req.headers.host;
      if (
        url.pathname !== "/screencast/webrtc" ||
        new URL(req.headers.origin).host !== host
      ) {
        connection.destroy();
        return;
      }
      const session = validateSessionName(url.searchParams.get("session"));
      signaling.handleUpgrade(req, connection, head, (socket) => {
        const timeout = setTimeout(() => socket.close(1008, "Offer required"), 6000);
        socket.on("error", () => socket.terminate());
        socket.once("close", () => clearTimeout(timeout));
        socket.once("message", (message) => {
          clearTimeout(timeout);
          sessionContext.run(session, () => startPeer(socket, message)).catch(() => {
            socket.close(1011, "WebRTC setup failed");
          });
        });
      });
    } catch {
      connection.destroy();
    }
  });
}
