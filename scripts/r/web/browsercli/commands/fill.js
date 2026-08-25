import { withActivePage } from "../browser-core.js";
import { describeTarget, findTarget } from "./dom.js";

export async function fill(target, text) {
  return withActivePage(async (page) => {
    const el = await findTarget(page, target);
    if (!el) throw new Error(`Unable to find element with ${describeTarget(target)}`);
    try {
      await el.focus();
      await el.evaluate((element) => { if ("value" in element) element.value = ""; });
      await page.keyboard.type(text);
    } finally {
      await el.dispose();
    }
  });
}
