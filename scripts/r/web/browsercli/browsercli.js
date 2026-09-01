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
    } else if (entry.name.endsWith(".js") || entry.name.endsWith(".html")) {
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
    console.warn("browsercli source changed; restarting browser and daemon");
    await postCommand("close-browser").catch(() => {});
    await waitForDaemon(false);
  } catch {}

  const child = spawn("node", [path.join(__dirname, "daemon.js")], {
    detached: true,
    stdio: "ignore",
    env: process.env,
  });
  child.unref();
  await waitForDaemon(true, { retries: 30, delay: 200 });
}

async function sendCommand(command, args = {}) {
  await ensureDaemon();
  return postCommand(command, args);
}

function addTargetOptions(command) {
  return command
    .option(
      "--ref <ref>",
      "Snapshot element ref (preferred for agents; e.g. @e0)",
    )
    .option(
      "--role <role>",
      "Accessible role for reusable automation (requires --name)",
    )
    .option(
      "--name <name>",
      "Accessible name for reusable automation (requires --role)",
    );
}

function targetArgs(options, { optional = false } = {}) {
  const { ref, role, name } = options;
  if (ref && (role || name)) {
    throw new Error("Use either --ref or --role with --name, not both");
  }
  if ((role && !name) || (!role && name)) {
    throw new Error("--role and --name must be used together");
  }
  if (!optional && !ref && !role) {
    throw new Error("Specify --ref, or both --role and --name");
  }
  return { ref, role, name };
}

function describeTarget({ ref, role, name }) {
  if (ref) return ref;
  if (role) return `${role} ${JSON.stringify(name)}`;
  return "focused element";
}

function printSuccess(message) {
  console.error(`[browsercli] ${message}`);
}

program
  .name("browsercli")
  .description("CLI to control a browser via CDP")
  .version("1.0.0");

program
  .command("open")
  .description("Open a URL")
  .argument("<url>", "URL to open")
  .option(
    "--extension",
    "Open in the active tab of Chrome running the browsercli extension"
  )
  .action(async (url, options) => {
    const status = await sendCommand("open", {
      url,
      extension: options.extension,
    });
    if (status) {
      if (status.mode === "extension") {
        console.error("[browsercli] extension active-tab");
      } else {
        console.error(
          `[browsercli] :${status.port} ${status.mode} profile=${status.profile}`,
        );
      }
    }
  });

program
  .command("connect")
  .description("Explicitly select a browser backend.")
  .argument("<backend>", "Backend to use: browser or extension")
  .option("--headed", "Open the managed browser in headed mode")
  .action(async (backend, options) => {
    const status = await sendCommand("connect", {
      backend,
      headed: options.headed,
    });
    console.error(`[browsercli] connected to ${status.backend}`);
  });

program
  .command("viewport")
  .description("Set the active page viewport resolution")
  .argument("<WIDTHxHEIGHT>", "Viewport resolution (for example 390x844)")
  .action(async (viewport) => {
    const result = await sendCommand("set-viewport", { viewport });
    console.log(`${result.width}x${result.height}`);
  });

program
  .command("close-browser")
  .description("Close the whole browser (quits Chrome and all its tabs)")
  .action(async () => {
    await sendCommand("close-browser");
    printSuccess("browser closed");
  });

program
  .command("get-text")
  .description("Get text from the active page")
  .action(async () => {
    const text = await sendCommand("get-text");
    console.log(text);
  });

program
  .command("get-html")
  .description("Get raw HTML content from the active page")
  .action(async () => {
    const html = await sendCommand("get-html");
    console.log(html);
  });

program
  .command("get-markdown")
  .description("Get markdown content from the active page")
  .action(async () => {
    const markdown = await sendCommand("get-markdown");
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
    printSuccess("scrolled to bottom");
  });

program
  .command("back")
  .description("Navigate back in the active page")
  .action(async () => {
    await sendCommand("back");
    printSuccess("navigated back");
  });

program
  .command("forward")
  .description("Navigate forward in the active page")
  .action(async () => {
    await sendCommand("forward");
    printSuccess("navigated forward");
  });

program
  .command("reload")
  .description("Reload the active page")
  .action(async () => {
    await sendCommand("reload");
    printSuccess("page reloaded");
  });

addTargetOptions(program.command("click"))
  .description("Click an element by ref or accessible role and name")
  .action(async (options) => {
    const target = targetArgs(options);
    await sendCommand("click", target);
    printSuccess(`clicked ${describeTarget(target)}`);
  });

addTargetOptions(program.command("type"))
  .description("Type text into the focused or specified element")
  .argument("<text>", "Text to type")
  .action(async (text, options) => {
    const target = targetArgs(options, { optional: true });
    await sendCommand("type", { text, ...target });
    printSuccess(
      `typed ${text.length} characters into ${describeTarget(target)}`,
    );
  });

addTargetOptions(program.command("fill"))
  .description("Clear and type text into an element")
  .argument("<text>", "Text to fill")
  .action(async (text, options) => {
    const target = targetArgs(options);
    await sendCommand("fill", { text, ...target });
    printSuccess(
      `filled ${describeTarget(target)} with ${text.length} characters`,
    );
  });

program
  .command("press")
  .description("Press a key")
  .argument("<key>", "Key to press")
  .action(async (key) => {
    await sendCommand("press", { key });
    printSuccess(`pressed ${JSON.stringify(key)}`);
  });

addTargetOptions(program.command("select"))
  .description("Select an option in a dropdown")
  .argument("<val>", "Value to select")
  .action(async (val, options) => {
    const target = targetArgs(options);
    await sendCommand("select", { value: val, ...target });
    printSuccess(`selected ${JSON.stringify(val)} in ${describeTarget(target)}`);
  });

addTargetOptions(program.command("upload"))
  .description("Upload a file to a file input element")
  .argument("<filePath>", "Path to the file to upload")
  .action(async (filePath, options) => {
    const target = targetArgs(options);
    await sendCommand("upload", { filePath, ...target });
    printSuccess(
      `uploaded ${JSON.stringify(filePath)} to ${describeTarget(target)}`,
    );
  });

addTargetOptions(program.command("screenshot"))
  .description("Take a page or element screenshot")
  .option("-o, --output <path>", "Save to this path instead of a temporary file")
  .action(async (options) => {
    const { output, ...targetOptions } = options;
    const savedPath = await sendCommand(
      "screenshot",
      {
        ...targetArgs(targetOptions, { optional: true }),
        output: output ? path.resolve(output) : undefined,
      },
    );
    console.log(savedPath);
  });

program
  .command("screencast")
  .description("Open a screencast viewer for the page")
  .action(async () => {
    const result = await sendCommand("screencast");
    if (result) console.log(result);
  });

await program.parseAsync(process.argv);
