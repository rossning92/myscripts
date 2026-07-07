import { sleep, withActivePage, refToSelector } from "../browser-core.js";
import { deepFind, deepFindByText, robustClick } from "./dom.js";

const OPTION_POLL_TRIES = 15;
const OPTION_POLL_INTERVAL_MS = 150;

export async function select(ref, value) {
  return withActivePage(async (page) => {
    const selector = refToSelector(ref);
    if (!selector) throw new Error(`Invalid ref: "${ref}"`);

    const el = await deepFind(page, selector);
    if (!el) throw new Error(`Unable to find element with ref "${ref}"`);

    try {
      // Native <select>: set the value directly.
      const native = await el.evaluate((el, val) => {
        if (el.tagName !== "SELECT") return "combobox";
        const options = Array.from(el.options);
        const option =
          options.find((o) => o.value === val) ||
          options.find((o) => o.text.trim().toLowerCase() === val.toLowerCase()) ||
          options.find((o) => o.text.toLowerCase().includes(val.toLowerCase()));
        if (!option) return "nooption";
        el.value = option.value;
        el.dispatchEvent(new Event("change", { bubbles: true }));
        el.dispatchEvent(new Event("input", { bubbles: true }));
        return "ok";
      }, value);

      if (native === "ok") return;
      if (native === "nooption") throw new Error(`No option matching "${value}" in select "${ref}"`);

      // ARIA combobox (e.g. Salesforce Lightning): open it, then click the option.
      // Options render lazily in an overlay, so poll until one appears.
      await robustClick(page, el, { verifyToggle: false });

      let option = null;
      for (let i = 0; i < OPTION_POLL_TRIES && !option; i++) {
        await sleep(OPTION_POLL_INTERVAL_MS);
        option = await deepFindByText(page, '[role="option"]', value);
      }
      if (!option) throw new Error(`Option "${value}" not found in combobox "${ref}"`);

      try {
        await robustClick(page, option, { verifyToggle: false });
      } finally {
        await option.dispose();
      }

      const landed = await el.evaluate((el, val) => {
        const norm = (s) => (s || "").replace(/\s+/g, " ").trim().toLowerCase();
        return norm(el.textContent).includes(norm(val));
      }, value);
      if (!landed) throw new Error(`Selected "${value}" but combobox "${ref}" did not update`);
    } finally {
      await el.dispose();
    }
  });
}
