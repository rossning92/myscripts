import { withActivePage, refToSelector } from "../browser-core.js";
import { deepFind, robustClick } from "./dom.js";

export async function click(ref) {
  return withActivePage(async (page) => {
    const selector = refToSelector(ref);
    if (!selector) {
      throw new Error(`Invalid ref: "${ref}"`);
    }

    const el = await deepFind(page, selector);
    if (!el) {
      throw new Error(`Unable to find element with ref "${ref}"`);
    }

    try {
      const ok = await robustClick(page, el);
      if (!ok) {
        throw new Error(`Clicked ref "${ref}" but its state did not change`);
      }
    } finally {
      await el.dispose();
    }
  });
}
