import { randomUUID } from "crypto";
import { createReadStream, createWriteStream } from "fs";
import { mkdir, stat } from "fs/promises";
import { createServer } from "http";
import { tmpdir } from "os";
import { basename, extname, resolve, sep } from "path";
import { pipeline } from "stream/promises";
import { fileURLToPath } from "url";
import {
  getBrowser,
  getOrOpenPage,
  getStatus,
  withActivePage,
} from "./browser-core.js";
import { withActivePageCdp } from "./browser-cdp.js";
import { DAEMON_PORT, DEBUG_PORT } from "./config.js";
import {
  click as clickCdp,
  pressKey as pressKeyCdp,
  scrollToBottom as scrollToBottomCdp,
  select as selectCdp,
  typeText as typeTextCdp,
} from "./extension/shared/actions.js";
import { evaluatePageContent } from "./extension/shared/evaluate-page-content.js";
import { upload as uploadCdp } from "./extension/shared/upload.js";
import { getMarkdownHtml, htmlToMarkdown } from "./get-markdown.js";
import { snapshot } from "./snapshot.js";
import { saveScreenshotData, screenshot } from "./screenshot.js";
import { screencast } from "./screencast.js";
import { extensionBridge } from "./extension-bridge.js";
import { getExtensionSourceVersion } from "./extension-source.js";
import { getViewport, parseViewport, setViewport } from "./viewport.js";
import { goBack, goForward, reload } from "./extension/shared/navigation.js";

const publicDir = resolve(fileURLToPath(new URL("public/", import.meta.url)));
const extensionDir = resolve(fileURLToPath(new URL("extension/", import.meta.url)));
const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
};

let activeBackend = "browser";
const screencastUploadDir = resolve(tmpdir(), "browsercli-screencast-uploads");

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

  async "set-viewport"({ viewport }) {
    if (activeBackend === "extension") {
      throw new Error(
        "Viewport emulation is only available for the managed browser backend",
      );
    }
    const dimensions = parseViewport(viewport);
    await withActivePage((page) =>
      page.setViewport({ ...dimensions, deviceScaleFactor: 1 }),
    );
    setViewport(dimensions);
    return dimensions;
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
    const browser = await getBrowser();
    await browser.close();
    setTimeout(() => process.exit(0), 100);
  },

  async "get-text"() {
    return await runOnActiveBackend("get-text", {}, () =>
      withActivePageCdp((send) => evaluatePageContent(send, "get-text")),
    );
  },

  async "get-html"() {
    return await runOnActiveBackend("get-html", {}, () =>
      withActivePageCdp((send) => evaluatePageContent(send, "get-html")),
    );
  },

  async "get-markdown"() {
    const html = await runOnActiveBackend("get-markdown", {}, getMarkdownHtml);
    return htmlToMarkdown(html);
  },

  async snapshot() {
    return await runOnActiveBackend("snapshot", {}, snapshot);
  },

  async "scroll-bottom"() {
    return await runOnActiveBackend("scroll-bottom", {}, () =>
      withActivePageCdp(scrollToBottomCdp),
    );
  },

  async back() {
    return await runOnActiveBackend("back", {}, () =>
      withActivePageCdp(goBack),
    );
  },

  async forward() {
    return await runOnActiveBackend("forward", {}, () =>
      withActivePageCdp(goForward),
    );
  },

  async reload() {
    return await runOnActiveBackend("reload", {}, () =>
      withActivePageCdp(reload),
    );
  },

  async click(target) {
    return await runOnActiveBackend("click", target, () =>
      withActivePageCdp((send) => clickCdp(send, target)),
    );
  },

  async type({ text, ...target }) {
    return await runOnActiveBackend("type", { text, ...target }, () =>
      withActivePageCdp((send) => typeTextCdp(send, text, target)),
    );
  },

  async fill({ text, ...target }) {
    return await runOnActiveBackend("fill", { text, ...target }, () =>
      withActivePageCdp((send) =>
        typeTextCdp(send, text, target, { clear: true }),
      ),
    );
  },

  async press({ key }) {
    return await runOnActiveBackend("press", { key }, () =>
      withActivePageCdp((send) => pressKeyCdp(send, key)),
    );
  },

  async select({ value, ...target }) {
    return await runOnActiveBackend("select", { value, ...target }, () =>
      withActivePageCdp((send) => selectCdp(send, target, value)),
    );
  },

  async upload({ filePath, ...target }) {
    const absolutePath = resolve(filePath);
    return await runOnActiveBackend(
      "upload",
      { filePath: absolutePath, ...target },
      () => withActivePageCdp((send) => uploadCdp(send, target, absolutePath)),
    );
  },

  async screenshot({ output, ...target } = {}) {
    if (activeBackend === "extension") {
      const { data } = await extensionBridge.send("screenshot", target);
      return await saveScreenshotData(data, output);
    }
    return await screenshot(target, output);
  },

  async screencast() {
    if (activeBackend === "extension") {
      throw new Error("screencast is only available for the managed browser backend");
    }
    return await screencast();
  },
};

function readBody(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (chunk) => (data += chunk));
    req.on("end", () => resolve(data));
  });
}

async function saveScreencastUpload(req, filename) {
  await mkdir(screencastUploadDir, { recursive: true });
  const safeName = basename(filename || "upload").replace(
    /[^a-zA-Z0-9._-]/g,
    "_",
  );
  const filePath = resolve(screencastUploadDir, `${randomUUID()}-${safeName}`);
  await pipeline(req, createWriteStream(filePath, { flags: "wx" }));
  return filePath;
}

const startTime = Date.now();

const server = createServer(async (req, res) => {
  const requestUrl = new URL(req.url, "http://localhost");
  const { pathname } = requestUrl;

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
    const requestedSourceVersion = requestUrl.searchParams.get("sourceVersion");
    let sourceVersion = await getExtensionSourceVersion(extensionDir);
    if (requestedSourceVersion !== sourceVersion) {
      res.end(JSON.stringify({ reload: true, sourceVersion }));
      return;
    }
    const command = await extensionBridge.poll();
    sourceVersion = await getExtensionSourceVersion(extensionDir);
    if (requestedSourceVersion !== sourceVersion) {
      extensionBridge.requeue(command);
      res.end(JSON.stringify({ reload: true, sourceVersion }));
      return;
    }
    res.end(JSON.stringify(command));
    return;
  }

  if (pathname === "/extension/source-version" && req.method === "GET") {
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ sourceVersion: await getExtensionSourceVersion(extensionDir) }));
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
      let ws = null;
      if (page) {
        ws = new URL(page.webSocketDebuggerUrl);
        ws.hostname = new URL(`http://${req.headers.host}`).hostname;
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ws: ws ? ws.href : null }));
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

  if (pathname === "/screencast/upload" && req.method === "POST") {
    try {
      const filePath = await saveScreencastUpload(
        req,
        decodeURIComponent(req.headers["x-file-name"] || "upload"),
      );
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ result: { filePath } }));
    } catch (err) {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: err.message || String(err) }));
    }
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

  if (pathname === "/viewport" && req.method === "GET") {
    res.end(JSON.stringify(getViewport()));
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
