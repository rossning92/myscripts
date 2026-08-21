import { randomUUID } from "crypto";
import { writeFile } from "fs/promises";
import path from "path";
import os from "os";
import { withActivePage } from "../browser-core.js";

function temporaryScreenshotPath() {
  return path.join(
    os.tmpdir(),
    `browsercli-screenshot-${randomUUID()}.png`,
  );
}

export async function saveScreenshotData(data) {
  if (typeof data !== "string" || data.length === 0) {
    throw new Error("Browser extension returned an empty screenshot");
  }
  const filePath = temporaryScreenshotPath();
  await writeFile(filePath, Buffer.from(data, "base64"));
  return filePath;
}

export async function screenshot() {
  return withActivePage(async (page) => {
    const filePath = temporaryScreenshotPath();
    await page.screenshot({ path: filePath, fullPage: false });
    return filePath;
  });
}
