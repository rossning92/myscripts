import { refToSelector, sleep } from "../browser-core.js";
import {
  ELEMENT_WAIT_INTERVAL_MS,
  ELEMENT_WAIT_TIMEOUT_MS,
  POST_CLICK_DELAY,
} from "../config.js";

const SCROLL_SETTLE_MS = 500;

// Resolve a CSS selector to an ElementHandle, descending through shadow roots.
// Returns null if nothing matches.
export async function deepFind(page, selector) {
  const handle = await page.evaluateHandle((sel) => {
    const walk = (root) => {
      const el = root.querySelector(sel);
      if (el) return el;
      for (const host of root.querySelectorAll("*")) {
        if (host.shadowRoot) {
          const found = walk(host.shadowRoot);
          if (found) return found;
        }
      }
      return null;
    };
    return walk(document);
  }, selector);
  const el = handle.asElement();
  if (!el) {
    await handle.dispose();
    return null;
  }
  return el;
}

function escapeAriaValue(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

export function describeTarget({ ref, role, name }) {
  return ref ? `ref "${ref}"` : `${role} named "${name}"`;
}

async function findTargetOnce(page, { ref, role, name }) {
  if (ref) {
    const selector = refToSelector(ref);
    return selector ? deepFind(page, selector) : null;
  }
  if (!role || !name) return null;
  return page.$(
    `::-p-aria([name="${escapeAriaValue(name)}"][role="${escapeAriaValue(role)}"])`,
  );
}

// Dynamic interfaces often render the target shortly after the command that
// reveals it. Retry target lookup for a bounded period instead of requiring
// callers to insert arbitrary sleeps between commands.
export async function findTarget(page, target) {
  const deadline = Date.now() + ELEMENT_WAIT_TIMEOUT_MS;
  while (true) {
    const element = await findTargetOnce(page, target);
    if (element) return element;
    const remainingMs = deadline - Date.now();
    if (remainingMs <= 0) return null;
    await sleep(Math.min(ELEMENT_WAIT_INTERVAL_MS, remainingMs));
  }
}

// Find the first *visible* element matching selector (through shadow roots) whose
// text (or data-value) matches `value` - exact first, then substring, case-insensitive.
export async function deepFindByText(page, selector, value) {
  const handle = await page.evaluateHandle((sel, val) => {
    const norm = (s) => (s || "").replace(/\s+/g, " ").trim().toLowerCase();
    const matches = [];
    const walk = (root) => {
      root.querySelectorAll(sel).forEach((e) => matches.push(e));
      root.querySelectorAll("*").forEach((h) => { if (h.shadowRoot) walk(h.shadowRoot); });
    };
    walk(document);
    const visible = matches.filter((o) => o.getClientRects().length);
    const text = (o) => norm(o.getAttribute("data-value") || o.textContent);
    const want = norm(val);
    return (
      visible.find((o) => text(o) === want) ||
      visible.find((o) => text(o).includes(want)) ||
      null
    );
  }, selector, value);
  const el = handle.asElement();
  if (!el) {
    await handle.dispose();
    return null;
  }
  return el;
}

// Click an element with a *trusted* mouse event (preserves anti-bot posture).
// For form controls whose native input is hidden behind a styled label (e.g.
// Salesforce Lightning radios), the input's own center sits under an overlay, so
// aim at the associated <label> instead. When the element is a radio/checkbox,
// verify the click landed and fall back to direct activation if it didn't.
// Returns true on success; false only when a toggle failed to change.
export async function robustClick(page, handle, { verifyToggle = true } = {}) {
  const info = await handle.evaluate((el) => {
    let target = el;
    if (["INPUT", "SELECT", "TEXTAREA"].includes(el.tagName)) {
      let label = null;
      if (el.id) {
        try {
          label = el.getRootNode().querySelector(`label[for="${CSS.escape(el.id)}"]`);
        } catch {}
      }
      if (!label) label = el.closest("label");
      if (label) {
        const lr = label.getBoundingClientRect();
        if (lr.width > 0 && lr.height > 0) target = label;
      }
    }
    target.scrollIntoView({ block: "center", inline: "center" });
    const { left, top, width, height } = target.getBoundingClientRect();
    const isToggle = el.tagName === "INPUT" && (el.type === "radio" || el.type === "checkbox");
    return {
      x: left + width / 2,
      y: top + height / 2,
      isToggle,
      inputType: isToggle ? el.type : null,
      wasChecked: isToggle ? !!el.checked : null,
    };
  });

  await sleep(SCROLL_SETTLE_MS);
  await page.mouse.click(info.x, info.y);
  await sleep(POST_CLICK_DELAY);

  if (verifyToggle && info.isToggle) {
    return await handle.evaluate((el, inputType, wasChecked) => {
      // A radio is "successful" when selected; a checkbox when its state flips.
      const ok = () => (inputType === "radio" ? el.checked : el.checked !== wasChecked);
      if (ok()) return true;
      el.click(); // direct activation, bypasses coordinate hit-testing
      return ok();
    }, info.inputType, info.wasChecked);
  }
  return true;
}
