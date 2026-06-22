import { program } from "commander";
import { spawn } from "child_process";
import { fileURLToPath } from "url";
import path from "path";
import fs from "fs";
import { DAEMON_PORT } from "./config.js";

const DAEMON_URL = `http://127.0.0.1:${DAEMON_PORT}`;
const __dirname = path.dirname(fileURLToPath(import.meta.url));

function getLatestMtime(dir) {
  let latest = 0;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name === "node_modules") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      latest = Math.max(latest, getLatestMtime(full));
    } else if (entry.name.endsWith(".js")) {
      latest = Math.max(latest, fs.statSync(full).mtimeMs);
    }
  }
  return latest;
}

async function healthCheck() {
  const res = await fetch(`${DAEMON_URL}/health`, { signal: AbortSignal.timeout(500) });
  return await res.json();
}

async function waitForDaemon(alive, { retries = 10, delay = 300 } = {}) {
  for (let i = 0; i < retries; i++) {
    await new Promise((r) => setTimeout(r, delay));
    try {
      await healthCheck();
      if (alive) return;
    } catch {
      if (!alive) return;
    }
  }
  if (alive) throw new Error("Failed to start daemon");
}

async function postCommand(command, args = {}) {
  const res = await fetch(`${DAEMON_URL}/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, args }),
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || "Command failed");
  }
  return data.result;
}

async function ensureDaemon() {
  try {
    const { startTime } = await healthCheck();
    if (getLatestMtime(__dirname) <= startTime) return;
    console.error("Source changed, restarting daemon...");
    await postCommand("close-browser").catch(() => {});
    await waitForDaemon(false);
  } catch {}

  const child = spawn("node", [path.join(__dirname, "daemon.js")], {
    detached: true,
    stdio: "ignore",
  });
  child.unref();
  await waitForDaemon(true, { retries: 30, delay: 200 });
}

async function sendCommand(command, args = {}) {
  await ensureDaemon();
  return postCommand(command, args);
}

program
  .name("browsercli")
  .description("CLI to control browser via Puppeteer")
  .version("1.0.0");

program
  .command("open")
  .description("Open a URL or connect to an existing browser")
  .argument("[url]", "URL to open")
  .option("--headed", "Open browser in headed mode")
  .action(async (url, options) => {
    const status = await sendCommand("open", { url, headed: options.headed });
    if (status) {
      console.error(
        `[browsercli] :${status.port} ${status.mode} profile=${status.profile}`,
      );
    }
  });

program
  .command("close-browser")
  .description("Close the whole browser (quits Chrome and all its tabs)")
  .action(async () => {
    await sendCommand("close-browser");
  });

program
  .command("get-text")
  .description("Get text from a page")
  .argument("[url]", "URL to get text from")
  .action(async (url) => {
    const text = await sendCommand("get-text", { url });
    console.log(text);
  });

program
  .command("get-markdown")
  .description("Get markdown content from a page")
  .argument("[url]", "URL to get markdown from")
  .action(async (url) => {
    const markdown = await sendCommand("get-markdown", { url });
    console.log(markdown);
  });

program
  .command("snapshot")
  .description(
    "Get a snapshot of the page with indices for interactive elements"
  )
  .action(async () => {
    const text = await sendCommand("snapshot");
    console.log(text);
  });

program
  .command("scroll-bottom")
  .description("Scroll to the bottom of the page")
  .action(async () => {
    await sendCommand("scroll-bottom");
  });

program
  .command("click")
  .description("Click on an element by its ref (e.g. @e0, @e1)")
  .argument("<ref>", "Element ref from snapshot (e.g. @e0)")
  .action(async (ref) => {
    await sendCommand("click", { ref });
  });

program
  .command("type")
  .description("Type text into the focused element or a specific element ref")
  .usage("[ref] <text>")
  .argument("[ref]", "Element ref to type into (e.g., @e1)")
  .argument("[text]", "Text to type")
  .action(async (ref, text) => {
    if (text === undefined) {
      await sendCommand("type", { text: ref });
    } else {
      await sendCommand("type", { text, ref });
    }
  });

program
  .command("fill")
  .description("Clear and type text into a specific element ref")
  .argument("<ref>", "Element ref to fill (e.g., @e1)")
  .argument("<text>", "Text to fill")
  .action(async (ref, text) => {
    await sendCommand("fill", { ref, text });
  });

program
  .command("press")
  .description("Press a key")
  .argument("<key>", "Key to press")
  .action(async (key) => {
    await sendCommand("press", { key });
  });

program
  .command("select")
  .description("Select an option in a dropdown")
  .argument("<ref>", "Element ref of the select element (e.g. @e0)")
  .argument("<val>", "Value to select")
  .action(async (ref, val) => {
    await sendCommand("select", { ref, value: val });
  });

program
  .command("upload")
  .description("Upload a file to a file input element")
  .argument("<ref>", "Element ref of the file input (e.g. @e5)")
  .argument("<filePath>", "Path to the file to upload")
  .action(async (ref, filePath) => {
    await sendCommand("upload", { ref, filePath });
  });

program
  .command("screenshot")
  .description("Take a screenshot of the current page")
  .argument("[filePath]", "Path to save the screenshot (default: temp file)")
  .action(async (filePath) => {
    const savedPath = await sendCommand("screenshot", { filePath });
    console.log(savedPath);
  });

program
  .command("inspect")
  .description("Open a screencast viewer for the page")
  .action(async () => {
    const result = await sendCommand("inspect");
    if (result) console.log(result);
  });

await program.parseAsync(process.argv);
