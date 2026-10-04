import { spawn } from "child_process";
import fs from "fs";
import path from "path";
import {
  currentSession,
  debugPort,
  profileDir,
  WINDOW_HEIGHT,
  WINDOW_WIDTH,
} from "./config.js";
import { normalizeUrl } from "./extension/shared/navigation.js";
import { CdpBrowser } from "./cdp-browser.js";
import { getViewport } from "./viewport.js";

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const getExecutablePath = () => {
  const defaults = {
    win32: [
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    ],
    darwin: ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
    linux: [
      "/usr/bin/google-chrome-stable",
      "/usr/bin/google-chrome",
      "/usr/bin/chromium",
      "/usr/bin/chromium-browser",
    ],
    android: ["/data/data/com.termux/files/usr/bin/chromium-browser"],
  };
  for (const candidate of defaults[process.platform] || []) {
    if (fs.existsSync(candidate)) return candidate;
  }

  const executableNames =
    process.platform === "win32"
      ? ["chrome.exe", "msedge.exe", "chromium.exe"]
      : ["google-chrome-stable", "google-chrome", "chromium", "chromium-browser"];
  for (const directory of (process.env.PATH || "").split(path.delimiter)) {
    for (const name of executableNames) {
      const candidate = path.join(directory, name);
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  throw new Error("Unable to find Chrome or Chromium. Add it to PATH.");
};

async function launchDetachedChrome(headed = false) {
  const executablePath = getExecutablePath();
  const chromeArgs = [
    `--remote-debugging-port=${debugPort()}`,
    `--user-data-dir=${profileDir()}`,
    "--remote-allow-origins=*",
    "--no-first-run",
    `--window-size=${WINDOW_WIDTH},${WINDOW_HEIGHT}`,
    "--disable-blink-features=AutomationControlled",
  ];

  // --no-sandbox is an automation fingerprint and is only needed on headless
  // Linux/Android servers. Skip it on desktop OSes to look more like a real browser.
  if (process.platform === "linux" || process.platform === "android") {
    chromeArgs.push("--no-sandbox");
  }

  if (
    !headed &&
    (process.platform === "linux" || process.platform === "android")
  ) {
    const chromeProcess = await new Promise((resolve, reject) => {
      const child = spawn(
        "xvfb-run",
        [
          "--auto-servernum",
          `--server-args=-screen 0 ${WINDOW_WIDTH}x${WINDOW_HEIGHT}x24`,
          executablePath,
          ...chromeArgs,
        ],
        {
          detached: true,
          stdio: "ignore",
        }
      );
      child.once("spawn", () => resolve(child));
      child.once("error", (error) => {
        reject(
          new Error(`Failed to start xvfb-run: ${error.message}`, {
            cause: error,
          })
        );
      });
    });
    chromeProcess.unref();
  } else {
    const args = [...chromeArgs];
    if (!headed) {
      args.push("--headless=new");
    }
    const chromeProcess = spawn(executablePath, args, {
      detached: true,
      stdio: "ignore",
    });
    chromeProcess.unref();
  }
}

async function getActivePage(browser) {
  const pages = await browser.pages();
  const vis_results = await Promise.all(
    pages.map(async (p) => {
      const state = await p.evaluate(() => document.webkitHidden);
      return !state;
    })
  );
  let visiblePage = pages.filter((_v, index) => vis_results[index])[0];
  return visiblePage;
}

export async function getOrOpenPage(browser, url) {
  let page;
  if (url) {
    const pages = await browser.pages();
    page = await browser.newPage();
    await Promise.race([
      Promise.all(pages.map((p) => p.close().catch((_e) => {}))),
      new Promise((resolve) => setTimeout(resolve, 2000)),
    ]);

    await page.setViewport({ ...getViewport(), deviceScaleFactor: 1 });
    url = normalizeUrl(url);
    const response = await page.goto(url, { waitUntil: "load" });
    if (response && !response.ok() && response.status() !== 304) {
      throw new Error(
        `Failed to load page: ${response.status()} ${response.statusText()}`
      );
    }
  } else {
    page = await getActivePage(browser);
    if (page) {
      await page.setViewport({ ...getViewport(), deviceScaleFactor: 1 });
    }
  }

  return page;
}

export async function launchOrConnectBrowser({
  headed = false,
  browserURL = `http://127.0.0.1:${debugPort()}`,
} = {}) {
  let browser;

  // Reuse whatever browser is already on the debug port, regardless of the
  // headed flag. To switch an existing session between headed and headless,
  // run close-browser first, then open again.
  try {
    browser = await CdpBrowser.connect(browserURL);
  } catch (err) {
    console.log("Unable to connect, launching a new browser instance...");

    await launchDetachedChrome(headed);
    // A heavyweight profile (session restore, extensions) can take well over 5s
    // to open the debug port on a cold start, so give it up to ~30s.
    const maxRetries = 60;
    const retryDelay = 500;
    let connected = false;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        browser = await CdpBrowser.connect(browserURL);
        connected = true;
        break;
      } catch (err) {
        if (attempt === maxRetries - 1) {
          throw err;
        }
        await sleep(retryDelay);
      }
    }
    if (!connected) throw new Error("Failed to connect to browser");
  }

  return browser;
}

const sessions = new Map();

function sessionState() {
  const session = currentSession();
  if (!sessions.has(session)) {
    sessions.set(session, { browser: null, headed: false });
  }
  return sessions.get(session);
}

export function getStatus() {
  return {
    port: debugPort(),
    mode: sessionState().headed ? "headed" : "headless",
    profile: profileDir(),
  };
}

export async function getBrowser(options) {
  const state = sessionState();
  state.headed = options?.headed ?? state.headed;
  if (state.browser?.isConnected()) return state.browser;
  state.browser = await launchOrConnectBrowser(options);
  return state.browser;
}

export function listSessions() {
  return [...sessions]
    .filter(([, state]) => state.browser?.isConnected())
    .map(([session]) => session);
}

export async function closeBrowser() {
  const browser = await getBrowser();
  sessions.delete(currentSession());
  await browser.close();
}

export async function withActivePage(handler, { url } = {}) {
  const browser = await getBrowser();
  const page = await getOrOpenPage(browser, url);

  if (!page) {
    throw "Failed to get active page";
  }
  return await handler(page, browser);
}

export async function restoreOpenerPage(page, browser) {
  const openerId = page.targetInfo.openerId;
  if (!openerId) return false;

  const pages = await browser.pages();
  const opener = pages.find(({ targetInfo }) => targetInfo.targetId === openerId);
  if (!opener) return false;

  await opener.send("Page.bringToFront");
  await page.close();
  return true;
}

export function refToSelector(ref) {
  if (!ref) return null;
  // Normalize: strip leading "@" if present, then ensure it starts with "e"
  const cleaned = ref.startsWith("@") ? ref.substring(1) : ref;
  if (!cleaned.startsWith("e")) return null;
  return `[data-agent-ref="${cleaned}"]`;
}

export const runAction = ({ type, text } = {}) => {
  let elements = getClickables();

  if (type == "scrollIntoView") {
    const target =
      elements.find(({ text: elementText }) => elementText === text) ||
      elements.find(({ text: elementText }) => elementText.includes(text)) ||
      null;

    if (!target) return false;

    const rect = target.el.getBoundingClientRect();

    const isOutsideView =
      rect.top < 0 ||
      rect.bottom > window.innerHeight ||
      rect.left < 0 ||
      rect.right > window.innerWidth;

    if (isOutsideView) {
      target.el.scrollIntoView({ block: "center", inline: "center" });
    }

    return true;
  } else if (type == "getClickables") {
    return elements.map(({ rect, text }) => ({
      rect,
      text,
    }));
  }

  function getControlLabel(el) {
    const ariaLabelledBy = el.getAttribute("aria-labelledby");
    if (ariaLabelledBy) {
      const labelEl = document.getElementById(ariaLabelledBy);
      if (labelEl) return labelEl.innerText;
    }

    if (el.id) {
      try {
        const labelEl = document.querySelector(
          `label[for="${CSS.escape(el.id)}"]`
        );
        if (labelEl) return labelEl.innerText;
      } catch (e) {}
    }

    const parentLabel = el.closest("label");
    if (parentLabel) return parentLabel.innerText;

    return null;
  }

  function getElementText(el) {
    let label =
      el.getAttribute("aria-label") ||
      el.getAttribute("title") ||
      el.getAttribute("placeholder");

    if (
      (!label || !label.trim()) &&
      (el.tagName === "INPUT" ||
        el.tagName === "TEXTAREA" ||
        el.tagName === "SELECT")
    ) {
      label = getControlLabel(el);
    }

    if (!label) label = el.innerText || el.textContent || el.value;

    return label ? String(label).replace(/\s+/g, " ").trim() : "";
  }

  function highlightElements(elements) {
    const boxes = [];
    elements.forEach(function (el) {
      const width = el.rect.right - el.rect.left;
      const height = el.rect.bottom - el.rect.top;
      if (width <= 0 || height <= 0) return;
      const box = document.createElement("div");
      box.style.position = "fixed";
      box.style.left = el.rect.left + "px";
      box.style.top = el.rect.top + "px";
      box.style.width = width + "px";
      box.style.height = height + "px";
      box.style.pointerEvents = "none";
      box.style.boxSizing = "border-box";
      box.style.zIndex = 2147483647;
      box.style.border = "2px solid red";
      const label = document.createElement("div");
      label.textContent = el.text;
      label.style.position = "absolute";
      label.style.top = "0";
      label.style.left = "0";
      label.style.transform = "translateY(-100%)";
      label.style.fontSize = "8pt";
      label.style.whiteSpace = "nowrap";
      label.style.pointerEvents = "none";
      label.style.backgroundColor = "red";
      label.style.color = "white";
      box.appendChild(label);
      document.body.appendChild(box);
      boxes.push(box);
    });
    setTimeout(() => boxes.forEach((box) => box.remove()), 1000);
  }

  function getClickables() {
    let elements = Array.prototype.slice
      .call(document.querySelectorAll("*"))
      .filter((el) => {
        if (
          el.tagName === "BUTTON" ||
          el.tagName === "A" ||
          (el.tagName === "INPUT" && el.type !== "hidden") ||
          el.tagName === "TEXTAREA" ||
          el.tagName === "SELECT" ||
          el.tagName === "LABEL" ||
          el.getAttribute("role") === "textbox" ||
          el.getAttribute("role") === "button" ||
          el.getAttribute("role") === "checkbox" ||
          el.getAttribute("role") === "radio" ||
          el.onclick != null
        ) {
          const rect = el.getBoundingClientRect();
          return (rect.right - rect.left) * (rect.bottom - rect.top) >= 20;
        }
        return false;
      })
      .map((el) => {
        const rect = el.getBoundingClientRect();
        return {
          el,
          rect: {
            left: rect.left,
            top: rect.top,
            right: rect.right,
            bottom: rect.bottom,
          },
          text: getElementText(el),
        };
      })
      .filter((x) => Boolean(x.text));

    // If one element contains another, return the contained one.
    elements = elements.filter(
      (x) => !elements.some((y) => x.el.contains(y.el) && !(x == y))
    );
    return elements;
  }
};
