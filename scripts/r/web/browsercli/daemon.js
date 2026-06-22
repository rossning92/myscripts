import { createServer } from "http";
import { readFileSync } from "fs";
import { getBrowser, getOrOpenPage, getStatus } from "./browser-core.js";
import { DAEMON_PORT, DEBUG_PORT } from "./config.js";
import { close } from "./commands/close.js";
import { getText } from "./commands/getText.js";
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

const screencastHtml = readFileSync(
  new URL("commands/screencast.html", import.meta.url),
  "utf-8"
);

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

  async screenshot({ filePath }) {
    return await screenshot(filePath);
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
  // Screencast viewer endpoints
  if (req.url === "/active-ws") {
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

  if (req.url === "/screencast") {
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(screencastHtml);
    return;
  }

  res.setHeader("Content-Type", "application/json");

  if (req.url === "/health") {
    res.end(JSON.stringify({ status: "ok", startTime }));
    return;
  }

  if (req.url === "/command" && req.method === "POST") {
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
      res.end(JSON.stringify({ error: err.message || String(err) }));
    }
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: "Not found" }));
});

server.listen(DAEMON_PORT, "127.0.0.1");
