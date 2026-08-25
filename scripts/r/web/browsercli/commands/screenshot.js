import { randomUUID } from "crypto";
import { writeFile } from "fs/promises";
import path from "path";
import os from "os";
import { withActivePage } from "../browser-core.js";
import { describeTarget, findTarget } from "./dom.js";

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

export async function screenshot(target = {}) {
  return withActivePage(async (page) => {
    const filePath = temporaryScreenshotPath();
    if (!target.ref && !(target.role && target.name)) {
      await page.screenshot({ path: filePath, fullPage: false });
      return filePath;
    }

    const element = await findTarget(page, target);
    if (!element) {
      throw new Error(`Unable to find element with ${describeTarget(target)}`);
    }
    try {
      await element.screenshot({ path: filePath });
    } finally {
      await element.dispose();
    }
    return filePath;
  });
}
