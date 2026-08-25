import { withActivePage } from "../browser-core.js";
import { describeTarget, findTarget, robustClick } from "./dom.js";

export async function click(target) {
  return withActivePage(async (page) => {
    const el = await findTarget(page, target);
    if (!el) {
      throw new Error(`Unable to find element with ${describeTarget(target)}`);
    }

    try {
      const ok = await robustClick(page, el);
      if (!ok) {
        throw new Error(`Clicked ${describeTarget(target)} but its state did not change`);
      }
    } finally {
      await el.dispose();
    }
  });
}
