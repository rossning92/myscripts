import { EventEmitter } from "events";
import WebSocket from "ws";

const COMMAND_TIMEOUT_MS = 30_000;

export class CdpConnection extends EventEmitter {
  constructor(webSocketUrl) {
    super();
    this.webSocketUrl = webSocketUrl;
    this.socket = null;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    await new Promise((resolve, reject) => {
      const socket = new WebSocket(this.webSocketUrl);
      const onError = (error) => reject(error);
      socket.once("open", () => {
        socket.off("error", onError);
        this.socket = socket;
        resolve();
      });
      socket.once("error", onError);
    });

    this.socket.on("message", (data) => this.#handleMessage(data));
    this.socket.on("close", () => this.#handleDisconnect());
    this.socket.on("error", (error) => {
      if (this.listenerCount("error")) this.emit("error", error);
    });
    return this;
  }

  send(method, params = {}, sessionId) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("CDP connection is not open"));
    }

    const id = this.nextId++;
    const message = { id, method, params };
    if (sessionId) message.sessionId = sessionId;

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP command timed out: ${method}`));
      }, COMMAND_TIMEOUT_MS);
      this.pending.set(id, { resolve, reject, timeout, method });
      this.socket.send(JSON.stringify(message), (error) => {
        if (!error) return;
        clearTimeout(timeout);
        this.pending.delete(id);
        reject(error);
      });
    });
  }

  isConnected() {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  close() {
    this.socket?.close();
  }

  #handleMessage(data) {
    const message = JSON.parse(data.toString());
    if (message.id) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      clearTimeout(pending.timeout);
      this.pending.delete(message.id);
      if (message.error) {
        const error = new Error(
          `${pending.method}: ${message.error.message || "CDP command failed"}`,
        );
        error.code = message.error.code;
        error.data = message.error.data;
        pending.reject(error);
      } else {
        pending.resolve(message.result || {});
      }
      return;
    }

    this.emit("event", message);
    this.emit(message.method, message.params || {}, message.sessionId);
  }

  #handleDisconnect() {
    const error = new Error("CDP connection closed");
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timeout);
      pending.reject(error);
    }
    this.pending.clear();
    this.emit("disconnected");
  }
}

export async function connectToBrowser(browserUrl) {
  const response = await fetch(`${browserUrl.replace(/\/$/, "")}/json/version`);
  if (!response.ok) {
    throw new Error(`Unable to query browser: HTTP ${response.status}`);
  }
  const version = await response.json();
  if (!version.webSocketDebuggerUrl) {
    throw new Error("Browser did not provide a CDP WebSocket URL");
  }
  return new CdpConnection(version.webSocketDebuggerUrl).connect();
}
