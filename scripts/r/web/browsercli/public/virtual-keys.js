export function setupVirtualKeys(container, send) {
  container.addEventListener("pointerdown", (event) => {
    const button = event.target.closest("button");
    if (!button) return;

    event.preventDefault();
    if (!button.dataset.key) return;

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
