import { spawn } from "child_process";
import fs from "fs";
import puppeteerExtra from "puppeteer-extra";
import puppeteerCore from "rebrowser-puppeteer-core";
import {
  BROWSER_URL,
  DEBUG_PORT,
  USER_DATA_DIR,
  WINDOW_HEIGHT,
  WINDOW_WIDTH,
} from "./config.js";

const puppeteer = puppeteerExtra.addExtra(puppeteerCore);

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const getExecutablePath = () => {
  const defaults = {
    win32: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    darwin: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    linux: "/usr/bin/google-chrome-stable",
    android: "/data/data/com.termux/files/usr/bin/chromium-browser",
  };
  const defaultPath = defaults[process.platform];
  if (defaultPath && fs.existsSync(defaultPath)) {
    return defaultPath;
  }
  return puppeteer.executablePath();
};

async function launchDetachedChrome(headed = false) {
  const executablePath = getExecutablePath();
  const chromeArgs = [
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${USER_DATA_DIR}`,
    "--remote-allow-origins=*",
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
    const chromeProcess = spawn(
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
    chromeProcess.on("error", () => {
      const fallbackProcess = spawn(
        executablePath,
        [...chromeArgs, "--headless=new"],
        {
          detached: true,
          stdio: "ignore",
        }
      );
      fallbackProcess.unref();
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

    if (!/^https?:\/\//i.test(url)) url = `http://${url}`;
    const response = await page.goto(url, { waitUntil: "domcontentloaded" });
    if (response && !response.ok() && response.status() !== 304) {
      throw new Error(
        `Failed to load page: ${response.status()} ${response.statusText()}`
      );
    }
    await sleep(3000);
  } else {
    page = await getActivePage(browser);
  }

  if (page) {
    const defaultViewport = {
      width: WINDOW_WIDTH,
      height: WINDOW_HEIGHT,
      deviceScaleFactor: 1,
    };
    await page.setViewport(defaultViewport);
  }

  return page;
}

export async function launchOrConnectBrowser({
  headed = false,
  browserURL = BROWSER_URL,
} = {}) {
  const defaultViewport = {
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT,
    deviceScaleFactor: 1,
  };
  let browser;

  if (headed) {
    // Kill any existing browser so we can relaunch in headed mode
    try {
      const tmp = await puppeteer.connect({ browserURL, defaultViewport });
      const cdp = await tmp.target().createCDPSession();
      await cdp.send("Browser.close");
      await sleep(1000);
    } catch {}
  }

  try {
    browser = await puppeteer.connect({ browserURL, defaultViewport });
  } catch (err) {
    console.log("Unable to connect, launching a new browser instance...");

    await launchDetachedChrome(headed);
    const maxRetries = 5;
    const retryDelay = 1000;
    let connected = false;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        browser = await puppeteer.connect({ browserURL, defaultViewport });
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

  const handleDialog = async (dialog) => {
    console.log(
      `Automatically accepting dialog: [${dialog.type()}] ${dialog.message()}`
    );
    await dialog.accept().catch(() => {});
  };

  // Attach to existing pages
  const existingPages = await browser.pages();
  for (const page of existingPages) {
    page.on("dialog", handleDialog);
  }

  // Attach to future pages
  browser.on("targetcreated", async (target) => {
    if (target.type() === "page") {
      const page = await target.page();
      if (page) {
        page.on("dialog", handleDialog);
      }
    }
  });

  return browser;
}

let _browser = null;
let _onDisconnect = null;
let _currentHeaded = false;

export function getStatus() {
  return {
    port: DEBUG_PORT,
    mode: _currentHeaded ? "headed" : "headless",
    profile: USER_DATA_DIR,
  };
}

export async function getBrowser(options) {
  _currentHeaded = options?.headed ?? _currentHeaded;
  if (options?.headed && _browser && _browser.isConnected()) {
    // Detach the exit-on-disconnect handler first, otherwise this intentional
    // close fires it and kills the daemon mid-request (headed relaunch race).
    if (_onDisconnect) _browser.off("disconnected", _onDisconnect);
    await _browser.close().catch(() => {});
    _browser = null;
    _onDisconnect = null;
  }
  if (_browser && _browser.isConnected()) return _browser;
  _browser = await launchOrConnectBrowser(options);
  _onDisconnect = () => process.exit(0);
  _browser.on("disconnected", _onDisconnect);
  return _browser;
}

export async function withActivePage(handler, { url } = {}) {
  const browser = await getBrowser();
  const page = await getOrOpenPage(browser, url);

  if (!page) {
    throw "Failed to get active page";
  }
  return await handler(page, browser);
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
