import path from "path";
import { withActivePage } from "../browser-core.js";
import { describeTarget, findTarget } from "./dom.js";

export async function upload(target, filePath) {
  return withActivePage(async (page) => {
    const absolutePath = path.resolve(filePath);

    const el = await findTarget(page, target);
    if (!el) {
      throw new Error(`Unable to find element with ${describeTarget(target)}`);
    }

    try {
      await el.uploadFile(absolutePath);
    } finally {
      await el.dispose();
    }
  });
}
