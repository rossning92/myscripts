import { evaluatePageContent } from "./shared/evaluate-page-content.js";
import { collectSnapshot } from "./shared/snapshot-cdp.js";
import {
  click,
  pressKey,
  scrollToBottom,
  select,
  typeText,
} from "./shared/actions.js";
import { captureScreenshot } from "./shared/screenshot.js";
import { upload } from "./shared/upload.js";
import { normalizeUrl } from "./shared/navigation.js";

const BRIDGE_URL = "http://127.0.0.1:21224/extension";
const RECONNECT_ALARM = "browsercli-reconnect";
const SOURCE_VERSION_KEY = "browsercliSourceVersion";
const NAVIGATION_TIMEOUT_MS = 30000;
let running = false;
let sourceVersion;

async function showConnected(connected) {
  await chrome.action.setBadgeText({ text: connected ? "ON" : "" });
  await chrome.action.setBadgeBackgroundColor({ color: "#16803c" });
}

async function getInstalledSourceVersion() {
  if (sourceVersion) return sourceVersion;
  const stored = await chrome.storage.local.get(SOURCE_VERSION_KEY);
  sourceVersion = stored[SOURCE_VERSION_KEY];
  return sourceVersion;
}

async function updateSourceVersion(nextSourceVersion) {
  sourceVersion = nextSourceVersion;
  await chrome.storage.local.set({ [SOURCE_VERSION_KEY]: nextSourceVersion });
}

async function ensureLatestSource() {
  const response = await fetch(`${BRIDGE_URL}/source-version`);
  if (!response.ok) throw new Error(`Bridge returned HTTP ${response.status}`);
  const { sourceVersion: latestSourceVersion } = await response.json();
  const installedSourceVersion = await getInstalledSourceVersion();
  if (!installedSourceVersion) {
    await updateSourceVersion(latestSourceVersion);
  } else if (installedSourceVersion !== latestSourceVersion) {
    await updateSourceVersion(latestSourceVersion);
    chrome.runtime.reload();
    return false;
  }
  return true;
}

function navigateAndWaitForLoad(tabId, url) {
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
      if (removedTabId === tabId) {
        finish(new Error("Tab closed during navigation"));
      }
    };
    const timer = setTimeout(
      () => finish(new Error("Navigation timed out")),
      NAVIGATION_TIMEOUT_MS,
    );

    chrome.tabs.onUpdated.addListener(onUpdated);
    chrome.tabs.onRemoved.addListener(onRemoved);
    chrome.tabs.update(tabId, { url }).catch(finish);
  });
}

async function open(url) {
  if (!url) return;
  const normalizedUrl = normalizeUrl(url);
  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) tab = await chrome.tabs.create({ url: "about:blank" });
  await navigateAndWaitForLoad(tab.id, normalizedUrl);
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
  return withActiveDebuggee(async (target) => {
    const send = (method, params) => sendDebuggeeCommand(target, method, params);
    if (["get-text", "get-html", "get-markdown"].includes(command)) {
      return evaluatePageContent(send, command);
    }
    if (command === "click") return click(send, args);
    if (command === "type") return typeText(send, args.text, args);
    if (command === "fill") {
      return typeText(send, args.text, args, { clear: true });
    }
    if (command === "press") return pressKey(send, args.key);
    if (command === "select") return select(send, args, args.value);
    if (command === "scroll-bottom") return scrollToBottom(send);
    if (command === "upload") return upload(send, args, args.filePath);
    throw new Error(`Unsupported extension command: ${command}`);
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
    return captureScreenshot(
      (method, params) => sendDebuggeeCommand(target, method, params),
      args,
    );
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
        if (!(await ensureLatestSource())) return;
        const response = await fetch(
          `${BRIDGE_URL}/poll?sourceVersion=${encodeURIComponent(sourceVersion)}`
        );
        if (!response.ok) throw new Error(`Bridge returned HTTP ${response.status}`);
        await showConnected(true);
        command = await response.json();
      } catch {
        await showConnected(false);
        await new Promise((resolve) => setTimeout(resolve, 1000));
        continue;
      }

      if (!command) continue;
      if (command.reload) {
        await updateSourceVersion(command.sourceVersion);
        chrome.runtime.reload();
        return;
      }
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
          "type", "fill", "press", "select", "upload",
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
