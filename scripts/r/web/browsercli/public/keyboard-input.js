export function isPasteShortcut(event) {
  return (event.ctrlKey || event.metaKey) &&
    !event.altKey &&
    event.key.toLowerCase() === "v";
}

export function forwardPaste(event, send) {
  const text = event.clipboardData?.getData("text/plain");
  if (text === undefined) return false;
  event.preventDefault();
  if (text) send("Input.insertText", { text });
  return true;
}
