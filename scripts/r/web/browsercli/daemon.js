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
import { getMarkdown } from "./commands/getMarkdown.js";
import { snapshot } from "./commands/snapshot.js";
import { scrollToBottom } from "./commands/scrollToBottom.js";
import { click } from "./commands/click.js";
import { typeText } from "./commands/typeText.js";
import { fill } from "./commands/fill.js";
import { pressKey } from "./commands/pressKey.js";
import { select } from "./commands/select.js";
import { upload } from "./commands/upload.js";
import { screenshot } from "./commands/screenshot.js";
import { inspect } from "./commands/inspect.js";

const publicDir = resolve(fileURLToPath(new URL("public/", import.meta.url)));
const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};

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
  async open({ url, headed }) {
    const browser = await getBrowser({ headed });
    await getOrOpenPage(browser, url);
    return getStatus();
  },

  async "close-browser"() {
    await close();
    setTimeout(() => process.exit(0), 100);
  },

  async "get-text"({ url }) {
    return await getText(url);
  },

  async "get-html"({ url }) {
    return await getHtml(url);
  },

  async "get-markdown"({ url }) {
    return await getMarkdown(url);
  },

  async snapshot() {
    return await snapshot();
  },

  async "scroll-bottom"() {
    await scrollToBottom();
  },

  async click({ ref }) {
    await click(ref);
  },

  async type({ text, ref }) {
    await typeText(text, ref);
  },

  async fill({ ref, text }) {
    await fill(ref, text);
  },

  async press({ key }) {
    await pressKey(key);
  },

  async select({ ref, value }) {
    await select(ref, value);
  },

  async upload({ ref, filePath }) {
    await upload(ref, filePath);
  },

  async screenshot() {
    return await screenshot();
  },

  async inspect() {
    return await inspect();
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

  // Screencast viewer endpoints
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
