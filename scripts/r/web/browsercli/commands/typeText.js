import { withActivePage } from "../browser-core.js";
import { describeTarget, findTarget } from "./dom.js";

export async function typeText(text, target) {
  return withActivePage(async (page) => {
    if (target.ref || target.role) {
      const el = await findTarget(page, target);
      if (!el) throw new Error(`Unable to find element with ${describeTarget(target)}`);
      try {
        await el.focus();
      } finally {
        await el.dispose();
      }
    }
    await page.keyboard.type(text);
  });
}
