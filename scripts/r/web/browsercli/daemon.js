import { randomUUID } from "crypto";
import { createReadStream, createWriteStream } from "fs";
import { mkdir, stat } from "fs/promises";
import { createServer } from "http";
import { tmpdir } from "os";
import { basename, extname, resolve, sep } from "path";
import { pipeline } from "stream/promises";
import { fileURLToPath } from "url";
import { listSessions } from "./browser/browser-core.js";
import { commands } from "./command-dispatch.js";
import {
  DAEMON_PORT,
  debugPort,
  sessionContext,
  validateSessionName,
} from "./config.js";
import { extensionBridge } from "./extension-bridge.js";
import { getExtensionSourceVersion } from "./extension-source.js";
import { serveScreencastSignaling } from "./screencast/signaling.js";
import { getViewport } from "./browser/viewport.js";

const publicDir = resolve(fileURLToPath(new URL("public/", import.meta.url)));
const extensionDir = resolve(fileURLToPath(new URL("extension/", import.meta.url)));
const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
};

const screencastUploadDir = resolve(tmpdir(), "browsercli-screencast-uploads");

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

async function handleRequest(req, res) {
  const requestUrl = new URL(req.url, "http://localhost");
  const { pathname } = requestUrl;

  if (pathname === "/" && (req.method === "GET" || req.method === "HEAD")) {
    res.writeHead(302, { Location: `/screencast${requestUrl.search}` });
    res.end();
    return;
  }

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
      const r = await fetch(`http://127.0.0.1:${debugPort()}/json`);
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

  if (pathname === "/sessions" && req.method === "GET") {
    res.end(JSON.stringify(listSessions()));
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
}

const server = createServer(async (req, res) => {
  let session;
  try {
    session = validateSessionName(
      new URL(req.url, "http://localhost").searchParams.get("session"),
    );
  } catch (err) {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: err.message }));
    return;
  }
  await sessionContext.run(session, () => handleRequest(req, res));
});

serveScreencastSignaling(server);
server.listen(DAEMON_PORT, "127.0.0.1");
