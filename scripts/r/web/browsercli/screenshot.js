import { randomUUID } from "crypto";
import { writeFile } from "fs/promises";
import path from "path";
import os from "os";
import { withActivePageCdp } from "./browser-cdp.js";
import { captureScreenshot } from "./extension/shared/screenshot.js";

function temporaryScreenshotPath() {
  return path.join(
    os.tmpdir(),
    `browsercli-screenshot-${randomUUID()}.png`,
  );
}

export async function saveScreenshotData(data, outputPath) {
  if (typeof data !== "string" || data.length === 0) {
    throw new Error("Browser extension returned an empty screenshot");
  }
  const filePath = outputPath || temporaryScreenshotPath();
  await writeFile(filePath, Buffer.from(data, "base64"));
  return filePath;
}

export async function screenshot(target = {}, outputPath) {
  const { data } = await withActivePageCdp((send) =>
    captureScreenshot(send, target));
  return saveScreenshotData(data, outputPath);
}
