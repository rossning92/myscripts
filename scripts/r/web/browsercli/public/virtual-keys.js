export function setupVirtualKeys(container, send) {
  container.addEventListener("pointerdown", (event) => {
    const button = event.target.closest("button[data-key]");
    if (!button) return;

    // Preserve focus on the text proxy so the mobile keyboard stays open.
    event.preventDefault();
    const keyCode = Number(button.dataset.keyCode);
    const params = {
      key: button.dataset.key,
      code: button.dataset.code,
      windowsVirtualKeyCode: keyCode,
      nativeVirtualKeyCode: keyCode,
    };
    send("Input.dispatchKeyEvent", { type: "rawKeyDown", ...params });
    send("Input.dispatchKeyEvent", { type: "keyUp", ...params });
  });
}
