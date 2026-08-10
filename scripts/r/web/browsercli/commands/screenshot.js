import { randomUUID } from "crypto";
import path from "path";
import os from "os";
import { withActivePage } from "../browser-core.js";

export async function screenshot() {
  return withActivePage(async (page) => {
    const filePath = path.join(
      os.tmpdir(),
      `browsercli-screenshot-${randomUUID()}.png`,
    );
    await page.screenshot({ path: filePath, fullPage: false });
    return filePath;
  });
}
