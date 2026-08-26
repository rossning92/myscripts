import { callFunction, cdpError, sleep } from "./cdp-utils.js";
import { describeTarget, releaseTarget, resolveTarget } from "./target.js";

const SCROLL_SETTLE_MS = 500;
const POST_CLICK_DELAY_MS = 500;

async function clickObject(send, objectId, { verifyToggle = true } = {}) {
  const info = await callFunction(send, objectId, function () {
    let target = this;
    if (["INPUT", "SELECT", "TEXTAREA"].includes(this.tagName)) {
      let label = null;
      if (this.id) {
        try {
          label = this.getRootNode().querySelector(
            `label[for="${CSS.escape(this.id)}"]`,
          );
        } catch {}
      }
      if (!label) label = this.closest("label");
      if (label) {
        const rect = label.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) target = label;
      }
    }
    target.scrollIntoView({ block: "center", inline: "center" });
    const { left, top, width, height } = target.getBoundingClientRect();
    if (width <= 0 || height <= 0) {
      throw new Error("Target element has no visible area");
    }
    const isToggle =
      this.tagName === "INPUT" &&
      (this.type === "radio" || this.type === "checkbox");
    return {
      x: left + width / 2,
      y: top + height / 2,
      isToggle,
      inputType: isToggle ? this.type : null,
      wasChecked: isToggle ? Boolean(this.checked) : null,
    };
  });

  await sleep(SCROLL_SETTLE_MS);
  await send("Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: info.x,
    y: info.y,
    button: "left",
    clickCount: 1,
  });
  await send("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: info.x,
    y: info.y,
    button: "left",
    clickCount: 1,
  });
  await sleep(POST_CLICK_DELAY_MS);

  if (!verifyToggle || !info.isToggle) return true;
  return callFunction(
    send,
    objectId,
    function (inputType, wasChecked) {
      const ok = () =>
        inputType === "radio"
          ? this.checked
          : this.checked !== wasChecked;
      if (ok()) return true;
      this.click();
      return ok();
    },
    [info.inputType, info.wasChecked],
  );
}

export async function click(send, target) {
  const objectId = await resolveTarget(send, target);
  try {
    const ok = await clickObject(send, objectId);
    if (!ok) {
      throw new Error(
        `Clicked ${describeTarget(target)} but its state did not change`,
      );
    }
  } finally {
    await releaseTarget(send, objectId);
  }
}

async function focusAndMaybeClear(send, objectId, clear) {
  await callFunction(send, objectId, function (shouldClear) {
    this.focus();
    if (!shouldClear) return;
    if ("value" in this) {
      this.value = "";
    } else if (this.isContentEditable) {
      this.textContent = "";
    }
  }, [clear]);
}

export async function typeText(send, text, target = {}, { clear = false } = {}) {
  const objectId = await resolveTarget(send, target, { focused: !clear });
  try {
    await focusAndMaybeClear(send, objectId, clear);
    await send("Input.insertText", { text });
  } finally {
    await releaseTarget(send, objectId);
  }
}

const KEY_ALIASES = new Map([
  ["ctrl", "Control"], ["control", "Control"], ["alt", "Alt"],
  ["shift", "Shift"], ["meta", "Meta"], ["cmd", "Meta"],
  ["command", "Meta"], ["enter", "Enter"], ["tab", "Tab"],
  ["esc", "Escape"], ["escape", "Escape"], ["backspace", "Backspace"],
  ["delete", "Delete"], ["space", " "], ["up", "ArrowUp"],
  ["down", "ArrowDown"], ["left", "ArrowLeft"], ["right", "ArrowRight"],
]);
const MODIFIER_BITS = { Alt: 1, Control: 2, Meta: 4, Shift: 8 };
const KEY_DEFINITIONS = {
  Alt: ["AltLeft", 18],
  ArrowDown: ["ArrowDown", 40],
  ArrowLeft: ["ArrowLeft", 37],
  ArrowRight: ["ArrowRight", 39],
  ArrowUp: ["ArrowUp", 38],
  Backspace: ["Backspace", 8],
  Control: ["ControlLeft", 17],
  Delete: ["Delete", 46],
  Enter: ["Enter", 13, "\r"],
  Escape: ["Escape", 27],
  Meta: ["MetaLeft", 91],
  Shift: ["ShiftLeft", 16],
  Tab: ["Tab", 9],
  " ": ["Space", 32],
};

function keyEventParams(key, modifiers) {
  const definition = KEY_DEFINITIONS[key];
  if (!definition) return { key, modifiers };
  const [code, virtualKeyCode, definitionText] = definition;
  const params = {
    key,
    code,
    windowsVirtualKeyCode: virtualKeyCode,
    nativeVirtualKeyCode: virtualKeyCode,
    modifiers,
  };
  if (definitionText && !(modifiers & ~MODIFIER_BITS.Shift)) {
    params.text = definitionText;
    params.unmodifiedText = definitionText;
  }
  return params;
}

export function parseKeyChord(chord) {
  return chord.split("+").map((part) => {
    const trimmed = part.trim();
    return KEY_ALIASES.get(trimmed.toLowerCase()) || trimmed;
  });
}

export async function pressKey(send, chord) {
  const keys = parseKeyChord(chord);
  let modifiers = 0;
  for (const key of keys) {
    modifiers |= MODIFIER_BITS[key] || 0;
    const params = keyEventParams(key, modifiers);
    await send("Input.dispatchKeyEvent", {
      type: params.text ? "keyDown" : "rawKeyDown",
      ...params,
    });
  }
  for (const key of [...keys].reverse()) {
    await send("Input.dispatchKeyEvent", {
      type: "keyUp",
      ...keyEventParams(key, modifiers),
    });
    modifiers &= ~(MODIFIER_BITS[key] || 0);
  }
}

async function findVisibleOption(send, value) {
  const response = await send("Runtime.evaluate", {
    expression: `(${function (wantedValue) {
      const norm = (text) =>
        (text || "").replace(/\s+/g, " ").trim().toLowerCase();
      const matches = [];
      const walk = (root) => {
        root.querySelectorAll('[role="option"]').forEach((item) =>
          matches.push(item));
        root.querySelectorAll("*").forEach((item) => {
          if (item.shadowRoot) walk(item.shadowRoot);
        });
      };
      walk(document);
      const visible = matches.filter((item) => item.getClientRects().length);
      const text = (item) =>
        norm(item.getAttribute("data-value") || item.textContent);
      const wanted = norm(wantedValue);
      return visible.find((item) => text(item) === wanted) ||
        visible.find((item) => text(item).includes(wanted)) || null;
    }.toString()})(${JSON.stringify(value)})`,
  });
  cdpError(response, "Unable to find dropdown option");
  return response.result?.objectId || null;
}

export async function select(send, target, value) {
  const objectId = await resolveTarget(send, target);
  try {
    const native = await callFunction(send, objectId, function (wanted) {
      if (this.tagName !== "SELECT") return "combobox";
      const options = Array.from(this.options);
      const lower = wanted.toLowerCase();
      const option = options.find((item) => item.value === wanted) ||
        options.find((item) => item.text.trim().toLowerCase() === lower) ||
        options.find((item) => item.text.toLowerCase().includes(lower));
      if (!option) return "nooption";
      this.value = option.value;
      this.dispatchEvent(new Event("change", { bubbles: true }));
      this.dispatchEvent(new Event("input", { bubbles: true }));
      return "ok";
    }, [value]);
    if (native === "ok") return;
    if (native === "nooption") {
      throw new Error(
        `No option matching "${value}" in ${describeTarget(target)}`,
      );
    }

    await clickObject(send, objectId, { verifyToggle: false });
    let optionId = null;
    for (let attempt = 0; attempt < 15 && !optionId; attempt++) {
      await sleep(150);
      optionId = await findVisibleOption(send, value);
    }
    if (!optionId) {
      throw new Error(
        `Option "${value}" not found in ${describeTarget(target)}`,
      );
    }
    try {
      await clickObject(send, optionId, { verifyToggle: false });
    } finally {
      await releaseTarget(send, optionId);
    }
    const landed = await callFunction(send, objectId, function (wanted) {
      const norm = (text) =>
        (text || "").replace(/\s+/g, " ").trim().toLowerCase();
      return norm(this.textContent).includes(norm(wanted));
    }, [value]);
    if (!landed) {
      throw new Error(
        `Selected "${value}" but ${describeTarget(target)} did not update`,
      );
    }
  } finally {
    await releaseTarget(send, objectId);
  }
}

export async function scrollToBottom(send) {
  const response = await send("Runtime.evaluate", {
    expression: `(${async function () {
      await new Promise((resolve) => {
        const distance = 200;
        const interval = 100;
        const timeout = 2000;
        let lastScrollY = window.scrollY;
        let lastChange = Date.now();
        const timer = setInterval(() => {
          window.scrollBy(0, distance);
          if (window.scrollY > lastScrollY) {
            lastScrollY = window.scrollY;
            lastChange = Date.now();
          }
          if (Date.now() - lastChange >= timeout) {
            clearInterval(timer);
            resolve();
          }
        }, interval);
      });
    }.toString()})()`,
    awaitPromise: true,
    returnByValue: true,
  });
  cdpError(response, "Unable to scroll page");
}
