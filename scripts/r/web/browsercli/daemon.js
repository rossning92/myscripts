import { createServer } from "http";
import { createReadStream } from "fs";
import { stat } from "fs/promises";
import { extname, resolve, sep } from "path";
import { fileURLToPath } from "url";
import { getBrowser, getOrOpenPage, getStatus } from "./browser-core.js";
import { DAEMON_PORT, DEBUG_PORT } from "./config.js";
import { close } from "./commands/close.js";
import { getText } from "./commands/getText.js";
import { getHtml } from "./commands/getHtml.js";
import { getMarkdown, htmlToMarkdown } from "./commands/getMarkdown.js";
import { snapshot } from "./commands/snapshot.js";
import { scrollToBottom } from "./commands/scrollToBottom.js";
import { click } from "./commands/click.js";
import { typeText } from "./commands/typeText.js";
import { fill } from "./commands/fill.js";
import { pressKey } from "./commands/pressKey.js";
import { select } from "./commands/select.js";
import { upload } from "./commands/upload.js";
import { saveScreenshotData, screenshot } from "./commands/screenshot.js";
import { inspect } from "./commands/inspect.js";
import { extensionBridge } from "./extension-bridge.js";

const publicDir = resolve(fileURLToPath(new URL("public/", import.meta.url)));
const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};

let activeBackend = "browser";

async function runOnActiveBackend(command, args, browserHandler) {
  if (activeBackend === "extension") {
    return await extensionBridge.send(command, args);
  }
  return await browserHandler();
}

async function serveStatic(pathname, res) {
  const filePath = resolve(publicDir, pathname.slice("/static/".length));
  if (!filePath.startsWith(publicDir + sep)) return false;

  try {
    const fileStat = await stat(filePath);
    if (!fileStat.isFile()) return false;

    res.writeHead(200, {
      "Content-Type":
        contentTypes[extname(filePath)] || "application/octet-stream",
    });
    createReadStream(filePath).pipe(res);
    return true;
  } catch {
    return false;
  }
}

const commands = {
  async open({ url, headed, extension }) {
    if (extension) {
      await extensionBridge.send("open", { url });
      activeBackend = "extension";
      return { mode: "extension", backend: activeBackend };
    }
    if (activeBackend === "extension") {
      await extensionBridge.send("open", { url });
      return { mode: "extension", backend: activeBackend };
    }
    const browser = await getBrowser({ headed });
    await getOrOpenPage(browser, url);
    return getStatus();
  },

  async connect({ backend, headed }) {
    if (backend !== "browser" && backend !== "extension") {
      throw new Error('Backend must be "browser" or "extension"');
    }
    if (backend === "extension") {
      await extensionBridge.send("ping", {});
    } else {
      await getBrowser({ headed });
    }
    activeBackend = backend;
    return { backend };
  },

  async "close-browser"() {
    await close();
    setTimeout(() => process.exit(0), 100);
  },

  async "get-text"({ url }) {
    return await runOnActiveBackend("get-text", { url }, () => getText(url));
  },

  async "get-html"({ url }) {
    return await runOnActiveBackend("get-html", { url }, () => getHtml(url));
  },

  async "get-markdown"({ url }) {
    if (activeBackend === "extension") {
      return htmlToMarkdown(await extensionBridge.send("get-markdown", { url }));
    }
    return await getMarkdown(url);
  },

  async snapshot() {
    if (activeBackend === "extension") {
      return await extensionBridge.send("snapshot", {});
    }
    return await snapshot();
  },

  async "scroll-bottom"() {
    return await runOnActiveBackend("scroll-bottom", {}, scrollToBottom);
  },

  async click({ ref }) {
    return await runOnActiveBackend("click", { ref }, () => click(ref));
  },

  async type({ text, ref }) {
    return await runOnActiveBackend("type", { text, ref }, () => typeText(text, ref));
  },

  async fill({ ref, text }) {
    return await runOnActiveBackend("fill", { ref, text }, () => fill(ref, text));
  },

  async press({ key }) {
    return await runOnActiveBackend("press", { key }, () => pressKey(key));
  },

  async select({ ref, value }) {
    return await runOnActiveBackend("select", { ref, value }, () => select(ref, value));
  },

  async upload({ ref, filePath }) {
    return await runOnActiveBackend("upload", { ref, filePath }, () => upload(ref, filePath));
  },

  async screenshot() {
    if (activeBackend === "extension") {
      const { data } = await extensionBridge.send("screenshot", {});
      return await saveScreenshotData(data);
    }
    return await screenshot();
  },

  async inspect() {
    return await runOnActiveBackend("inspect", {}, inspect);
  },
};

function readBody(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (chunk) => (data += chunk));
    req.on("end", () => resolve(data));
  });
}

const startTime = Date.now();

const server = createServer(async (req, res) => {
  const { pathname } = new URL(req.url, "http://localhost");

  // Only extension service workers may consume or complete bridge commands.
  if (pathname.startsWith("/extension/")) {
    const origin = req.headers.origin || "";
    // Extension service-worker fetches may omit Origin. Browser-page CORS
    // requests include their http(s) Origin and must not consume commands.
    if (origin && !origin.startsWith("chrome-extension://")) {
      res.writeHead(403, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Chrome extension origin required" }));
      return;
    }
    if (origin) {
      res.setHeader("Access-Control-Allow-Origin", origin);
      res.setHeader("Vary", "Origin");
    }
  }

  if (pathname === "/extension/poll" && req.method === "GET") {
    res.setHeader("Content-Type", "application/json");
    const command = await extensionBridge.poll();
    res.end(JSON.stringify(command));
    return;
  }

  if (pathname === "/extension/result" && req.method === "POST") {
    res.setHeader("Content-Type", "application/json");
    extensionBridge.resolve(JSON.parse(await readBody(req)));
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  if (pathname.startsWith("/extension/") && req.method === "OPTIONS") {
    res.writeHead(204, {
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    });
    res.end();
    return;
  }

  if (pathname === "/active-ws") {
    try {
      const r = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json`);
      const targets = await r.json();
      const page = targets.find((t) => t.type === "page");
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ws: page ? page.webSocketDebuggerUrl : null }));
    } catch (e) {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "browser not available" }));
    }
    return;
  }

  if (pathname === "/screencast") {
    await serveStatic("/static/screencast.html", res);
    return;
  }

  if (pathname.startsWith("/static/")) {
    if (await serveStatic(pathname, res)) return;

    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Static file not found" }));
    return;
  }

  res.setHeader("Content-Type", "application/json");

  if (pathname === "/health") {
    res.end(JSON.stringify({ status: "ok", startTime }));
    return;
  }

  if (pathname === "/command" && req.method === "POST") {
    try {
      const { command, args } = JSON.parse(await readBody(req));
      const handler = commands[command];
      if (!handler) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: `Unknown command: ${command}` }));
        return;
      }
      const result = await handler(args || {});
      res.end(JSON.stringify({ result: result ?? null }));
    } catch (err) {
      res.writeHead(500);
      res.end(JSON.stringify({ error: err.stack || err.message || String(err) }));
    }
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: "Not found" }));
});

server.listen(DAEMON_PORT, "127.0.0.1");
