import { extractPageContent } from "./page-content.js";
import { collectSnapshot } from "./snapshot-cdp.js";

const BRIDGE_URL = "http://127.0.0.1:21224/extension";
const RECONNECT_ALARM = "browsercli-reconnect";
const NAVIGATION_TIMEOUT_MS = 30000;
const POST_NAVIGATION_DELAY_MS = 3000;
let running = false;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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

async function pageCommand(command, args = {}) {
  if (args.url) await open(args.url);
  return withActiveDebuggee(async (target) => {
    const expression = `(${function (command, args, pageContent) {
      const findRef = (ref) => {
        const wanted = String(ref || "").replace(/^@/, "");
        const walk = (root) => {
          const found = root.querySelector(`[data-agent-ref="${CSS.escape(wanted)}"]`);
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
      };
      const input = (element, text, clear) => {
        if (!element) throw new Error(`Unable to find element with ref "${args.ref}"`);
        element.focus();
        if (clear && "value" in element) element.value = "";
        if ("value" in element) element.value += text;
        else document.execCommand("insertText", false, text);
        element.dispatchEvent(new InputEvent("input", { bubbles: true, data: text }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
      };

      if (["get-text", "get-html", "get-markdown"].includes(command)) {
        return pageContent(command);
      }
      if (command === "scroll-bottom") {
        window.scrollTo(0, document.documentElement.scrollHeight);
        return null;
      }
      if (command === "click") {
        const element = findRef(args.ref);
        if (!element) throw new Error(`Unable to find element with ref "${args.ref}"`);
        element.click();
        return null;
      }
      if (command === "type") {
        input(args.ref ? findRef(args.ref) : document.activeElement, args.text, false);
        return null;
      }
      if (command === "fill") {
        input(findRef(args.ref), args.text, true);
        return null;
      }
      if (command === "press") {
        const key = args.key.split("+").pop();
        const target = document.activeElement || document.body;
        target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
        target.dispatchEvent(new KeyboardEvent("keyup", { key, bubbles: true }));
        return null;
      }
      if (command === "select") {
        const element = findRef(args.ref);
        if (!element) throw new Error(`Unable to find element with ref "${args.ref}"`);
        const option = [...(element.options || [])].find((item) =>
          item.value === args.value || item.text.trim().toLowerCase() === args.value.toLowerCase());
        if (!option) throw new Error(`No option matching "${args.value}"`);
        element.value = option.value;
        element.dispatchEvent(new Event("input", { bubbles: true }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
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

async function screenshot() {
  return withActiveDebuggee(async (target) => {
    const { data } = await sendDebuggeeCommand(target, "Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
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
          result = await screenshot();
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
