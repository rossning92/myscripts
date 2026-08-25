import { extractPageContent } from "./page-content.js";
import { collectSnapshot } from "./snapshot-cdp.js";

const BRIDGE_URL = "http://127.0.0.1:21224/extension";
const RECONNECT_ALARM = "browsercli-reconnect";
const NAVIGATION_TIMEOUT_MS = 30000;
const POST_NAVIGATION_DELAY_MS = 3000;
const ELEMENT_WAIT_TIMEOUT_MS = 10000;
const ELEMENT_WAIT_INTERVAL_MS = 100;
let running = false;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

class TargetNotFoundError extends Error {}

async function showConnected(connected) {
  await chrome.action.setBadgeText({ text: connected ? "ON" : "" });
  await chrome.action.setBadgeBackgroundColor({ color: "#16803c" });
}

function normalizeUrl(url) {
  if (!url) return null;
  if (/^[a-z][a-z\d+.-]*:/i.test(url)) return url;
  return `http://${url}`;
}

function waitForTabNavigation(
  tabId,
  startNavigation,
  finishWhenStarted = false
) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const cleanup = () => {
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(onUpdated);
      chrome.tabs.onRemoved.removeListener(onRemoved);
    };
    const finish = (error) => {
      if (settled) return;
      settled = true;
      cleanup();
      if (error) reject(error);
      else resolve();
    };
    const onUpdated = (updatedTabId, changeInfo) => {
      if (updatedTabId === tabId && changeInfo.status === "complete") finish();
    };
    const onRemoved = (removedTabId) => {
      if (removedTabId === tabId) finish(new Error("Tab closed during navigation"));
    };
    const timer = setTimeout(() => {
      finish(new Error("Navigation timed out"));
    }, NAVIGATION_TIMEOUT_MS);

    chrome.tabs.onUpdated.addListener(onUpdated);
    chrome.tabs.onRemoved.addListener(onRemoved);
    let started;
    try {
      started = startNavigation();
    } catch (error) {
      finish(error);
      return;
    }
    Promise.resolve(started)
      .then((completed) => {
        if (finishWhenStarted && completed) finish();
      })
      .catch(finish);
  });
}

async function open(url) {
  if (!url) return;
  const normalizedUrl = normalizeUrl(url);
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (activeTab?.id) {
    await waitForTabNavigation(activeTab.id, () =>
      chrome.tabs.update(activeTab.id, { url: normalizedUrl })
    );
  } else {
    const tab = await chrome.tabs.create({ url: normalizedUrl });
    if (tab.id && tab.status !== "complete") {
      await waitForTabNavigation(
        tab.id,
        async () => {
          // The new tab may have completed between tabs.create() and listener
          // registration, so inspect it again after the listeners are installed.
          const currentTab = await chrome.tabs.get(tab.id);
          return currentTab.status === "complete";
        },
        true
      );
    }
  }
  await sleep(POST_NAVIGATION_DELAY_MS);
}

async function withActiveDebuggee(callback) {
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!activeTab?.id) throw new Error("No active tab");

  const target = { tabId: activeTab.id };
  await chrome.debugger.attach(target, "1.3");
  try {
    return await callback(target, activeTab);
  } finally {
    await chrome.debugger.detach(target).catch(() => {});
  }
}

function findElementByRef(ref) {
  const wanted = String(ref).replace(/^@/, "");
  const walk = (root) => {
    const found = root.querySelector(
      `[data-agent-ref="${CSS.escape(wanted)}"]`,
    );
    if (found) return found;
    for (const element of root.querySelectorAll("*")) {
      if (element.shadowRoot) {
        const nested = walk(element.shadowRoot);
        if (nested) return nested;
      }
    }
    return null;
  };
  return walk(document);
}

async function evaluateTarget(target, expression, description) {
  const response = await sendDebuggeeCommand(target, "Runtime.evaluate", {
    expression,
  });
  if (response.exceptionDetails) {
    throw new Error(response.exceptionDetails.exception?.description ||
      response.exceptionDetails.text || "Unable to resolve target element");
  }
  if (!response.result?.objectId || response.result.subtype === "null") {
    throw new TargetNotFoundError(`Unable to find element with ${description}`);
  }
  return response.result.objectId;
}

async function resolveAccessibilityTarget(target, { role, name }) {
  await sendDebuggeeCommand(target, "Accessibility.enable");
  const { root } = await sendDebuggeeCommand(target, "DOM.getDocument", {
    depth: 0,
  });
  const { nodes = [] } = await sendDebuggeeCommand(
    target,
    "Accessibility.queryAXTree",
    { nodeId: root.nodeId, accessibleName: name, role },
  );
  const node = nodes.find((item) =>
    !item.ignored && item.backendDOMNodeId &&
    item.role?.value === role && item.name?.value === name
  );
  if (!node) {
    throw new TargetNotFoundError(
      `Unable to find element with ${role} named "${name}"`,
    );
  }

  const { object } = await sendDebuggeeCommand(target, "DOM.resolveNode", {
    backendNodeId: node.backendDOMNodeId,
  });
  if (!object?.objectId) {
    throw new TargetNotFoundError("Unable to resolve accessibility node");
  }
  return object.objectId;
}

async function resolveTargetOnce(target, args, { focused = false } = {}) {
  if (args.role && args.name) {
    return resolveAccessibilityTarget(target, args);
  }
  if (args.ref) {
    return evaluateTarget(
      target,
      `(${findElementByRef.toString()})(${JSON.stringify(args.ref)})`,
      `ref "${args.ref}"`,
    );
  }
  if (focused) {
    return evaluateTarget(target, "document.activeElement", "focused element");
  }
  throw new Error("No element target specified");
}

async function resolveTarget(target, args, { focused = false } = {}) {
  // An untargeted `type` intentionally uses the currently focused element and
  // should not wait. Explicit targets may be rendered asynchronously.
  if (focused && !args.ref && !(args.role && args.name)) {
    return resolveTargetOnce(target, args, { focused });
  }

  const deadline = Date.now() + ELEMENT_WAIT_TIMEOUT_MS;
  while (true) {
    try {
      return await resolveTargetOnce(target, args, { focused });
    } catch (error) {
      if (!(error instanceof TargetNotFoundError)) throw error;
      const remainingMs = deadline - Date.now();
      if (remainingMs <= 0) throw error;
      await sleep(Math.min(ELEMENT_WAIT_INTERVAL_MS, remainingMs));
    }
  }
}

async function releaseTarget(target, objectId) {
  if (!objectId) return;
  await sendDebuggeeCommand(target, "Runtime.releaseObject", {
    objectId,
  }).catch(() => {});
}

async function runTargetAction(target, objectId, command, args) {
  const response = await sendDebuggeeCommand(target, "Runtime.callFunctionOn", {
    objectId,
    functionDeclaration: function (command, args) {
      const input = (element, text, clear) => {
        element.focus();
        if (clear && "value" in element) element.value = "";
        if ("value" in element) element.value += text;
        else document.execCommand("insertText", false, text);
        element.dispatchEvent(new InputEvent("input", { bubbles: true, data: text }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
      };

      if (command === "click") {
        this.click();
        return null;
      }
      if (command === "type") {
        input(this, args.text, false);
        return null;
      }
      if (command === "fill") {
        input(this, args.text, true);
        return null;
      }
      if (command === "select") {
        const option = [...(this.options || [])].find((item) =>
          item.value === args.value ||
          item.text.trim().toLowerCase() === args.value.toLowerCase()
        );
        if (!option) throw new Error(`No option matching "${args.value}"`);
        this.value = option.value;
        this.dispatchEvent(new Event("input", { bubbles: true }));
        this.dispatchEvent(new Event("change", { bubbles: true }));
        return null;
      }
      throw new Error(`Unsupported element action: ${command}`);
    }.toString(),
    arguments: [{ value: command }, { value: args }],
    awaitPromise: true,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    throw new Error(response.exceptionDetails.exception?.description ||
      response.exceptionDetails.text || "Page command failed");
  }
  return response.result?.value;
}

async function pageCommand(command, args = {}) {
  return withActiveDebuggee(async (target) => {
    if (["click", "type", "fill", "select"].includes(command)) {
      const objectId = await resolveTarget(target, args, {
        focused: command === "type",
      });
      try {
        return await runTargetAction(target, objectId, command, args);
      } finally {
        await releaseTarget(target, objectId);
      }
    }
    const expression = `(${function (command, args, pageContent) {
      if (["get-text", "get-html", "get-markdown"].includes(command)) {
        return pageContent(command);
      }
      if (command === "scroll-bottom") {
        window.scrollTo(0, document.documentElement.scrollHeight);
        return null;
      }
      if (command === "press") {
        const key = args.key.split("+").pop();
        const target = document.activeElement || document.body;
        target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
        target.dispatchEvent(new KeyboardEvent("keyup", { key, bubbles: true }));
        return null;
      }
      throw new Error(`Unsupported extension command: ${command}`);
    }})(${JSON.stringify(command)}, ${JSON.stringify(args)}, ${extractPageContent.toString()})`;
    const response = await sendDebuggeeCommand(target, "Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (response.exceptionDetails) {
      throw new Error(response.exceptionDetails.exception?.description ||
        response.exceptionDetails.text || "Page command failed");
    }
    return response.result?.value;
  });
}

function sendDebuggeeCommand(target, method, params = {}) {
  return chrome.debugger.sendCommand(target, method, params);
}

async function snapshot() {
  return withActiveDebuggee(async (target, activeTab) => {
    return await collectSnapshot(
      (method, params) => sendDebuggeeCommand(target, method, params),
      { title: activeTab.title, url: activeTab.url },
    );
  });
}

async function screenshot(args = {}) {
  return withActiveDebuggee(async (target) => {
    let clip;
    let objectId;
    if (args.ref || (args.role && args.name)) {
      objectId = await resolveTarget(target, args);
      try {
        const response = await sendDebuggeeCommand(target, "Runtime.callFunctionOn", {
          objectId,
          functionDeclaration: function () {
            this.scrollIntoView({ block: "center", inline: "center" });
            const rect = this.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) {
              throw new Error("Target element has no visible area");
            }
            return {
              x: rect.left + window.scrollX,
              y: rect.top + window.scrollY,
              width: rect.width,
              height: rect.height,
            };
          }.toString(),
          returnByValue: true,
        });
        if (response.exceptionDetails) {
          throw new Error(response.exceptionDetails.exception?.description ||
            response.exceptionDetails.text || "Unable to measure target element");
        }
        clip = { ...response.result.value, scale: 1 };
      } finally {
        await releaseTarget(target, objectId);
      }
    }

    const { data } = await sendDebuggeeCommand(target, "Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
      ...(clip ? { clip, captureBeyondViewport: true } : {}),
    });
    return { data };
  });
}

async function report(command, result, error) {
  await fetch(`${BRIDGE_URL}/result`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: command.id, result, error }),
  });
}

async function run() {
  if (running) return;
  running = true;
  try {
    while (true) {
      let command;
      try {
        const response = await fetch(`${BRIDGE_URL}/poll`);
        if (!response.ok) throw new Error(`Bridge returned HTTP ${response.status}`);
        await showConnected(true);
        command = await response.json();
      } catch {
        await showConnected(false);
        await new Promise((resolve) => setTimeout(resolve, 1000));
        continue;
      }

      if (!command) continue;
      try {
        let result;
        if (command.command === "open") {
          await open(command.args?.url);
          result = { ok: true };
        } else if (command.command === "ping") {
          result = { ok: true };
        } else if (command.command === "snapshot") {
          result = await snapshot();
        } else if (command.command === "screenshot") {
          result = await screenshot(command.args);
        } else if ([
          "get-text", "get-html", "get-markdown", "scroll-bottom", "click",
          "type", "fill", "press", "select",
        ].includes(command.command)) {
          result = await pageCommand(command.command, command.args);
        } else {
          throw new Error(`Unsupported command: ${command.command}`);
        }
        await report(command, result);
      } catch (error) {
        await report(command, null, error?.message || String(error));
      }
    }
  } finally {
    running = false;
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(RECONNECT_ALARM, { periodInMinutes: 0.5 });
  void run();
});
chrome.runtime.onStartup.addListener(run);
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === RECONNECT_ALARM) void run();
});
chrome.action.onClicked.addListener(run);
chrome.alarms.create(RECONNECT_ALARM, { periodInMinutes: 0.5 });
run();
