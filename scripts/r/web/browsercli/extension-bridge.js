// Manifest V3 service workers can be suspended while the daemon is offline.
// Chrome alarms wake the extension every 30 seconds, so allow one full alarm
// interval plus startup time for it to collect a queued command.
const COMMAND_TIMEOUT_MS = 40000;
const POLL_TIMEOUT_MS = 25000;

class ExtensionBridge {
  constructor() {
    this.nextId = 1;
    this.queuedCommand = null;
    this.pollWaiter = null;
    this.pendingResults = new Map();
  }

  send(command, args) {
    if (this.queuedCommand) {
      return Promise.reject(
        new Error("The extension already has a queued command")
      );
    }

    const item = { id: this.nextId++, command, args };
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingResults.delete(item.id);
        if (this.queuedCommand?.id === item.id) this.queuedCommand = null;
        reject(
          new Error(
            "Browser extension did not respond. Load the extension and click its toolbar icon to reconnect."
          )
        );
      }, COMMAND_TIMEOUT_MS);
      this.pendingResults.set(item.id, { resolve, reject, timer });

      if (this.pollWaiter) {
        const deliver = this.pollWaiter;
        this.pollWaiter = null;
        deliver(item);
      } else {
        this.queuedCommand = item;
      }
    });
  }

  poll() {
    if (this.queuedCommand) {
      const item = this.queuedCommand;
      this.queuedCommand = null;
      return Promise.resolve(item);
    }

    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        if (this.pollWaiter === deliver) this.pollWaiter = null;
        resolve(null);
      }, POLL_TIMEOUT_MS);
      const deliver = (item) => {
        clearTimeout(timer);
        resolve(item);
      };
      this.pollWaiter = deliver;
    });
  }

  requeue(item) {
    if (!item) return;
    if (this.queuedCommand) {
      throw new Error("Cannot requeue an extension command while another is queued");
    }
    this.queuedCommand = item;
  }

  resolve({ id, result, error }) {
    const pending = this.pendingResults.get(id);
    if (!pending) return;
    clearTimeout(pending.timer);
    this.pendingResults.delete(id);
    if (error) pending.reject(new Error(error));
    else pending.resolve(result);
  }
}

export const extensionBridge = new ExtensionBridge();
