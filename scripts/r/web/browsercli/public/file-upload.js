export function setupFileUpload({
  send,
  dialog,
  description,
  chooseButton,
  cancelButton,
  input,
}) {
  let activeChooser = null;

  function close() {
    dialog.hidden = true;
    input.value = "";
    activeChooser = null;
  }

  async function cancel() {
    if (!activeChooser) return;
    await send("Page.setInterceptFileChooserDialog", {
      enabled: true,
      cancel: true,
    });
    close();
  }

  async function open(params) {
    activeChooser = params;
    input.multiple = params.mode === "selectMultiple";
    input.accept = "";
    if (params.backendNodeId) {
      const response = await send("DOM.describeNode", {
        backendNodeId: params.backendNodeId,
      });
      const attributes = response?.result?.node?.attributes || [];
      const acceptIndex = attributes.indexOf("accept");
      if (acceptIndex >= 0) input.accept = attributes[acceptIndex + 1];
    }
    description.textContent = input.multiple
      ? "Select one or more files from this device for the remote page."
      : "Select a file from this device for the remote page.";
    chooseButton.textContent = input.multiple ? "Choose files" : "Choose file";
    dialog.hidden = false;
    chooseButton.focus();
  }

  async function upload(file) {
    const response = await fetch("/screencast/upload", {
      method: "POST",
      headers: { "X-File-Name": encodeURIComponent(file.name) },
      body: file,
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || "Could not upload file");
    }
    return data.result.filePath;
  }

  chooseButton.addEventListener("click", () => input.click());
  cancelButton.addEventListener("click", cancel);
  input.addEventListener("change", async () => {
    if (!activeChooser || !input.files.length) return;
    chooseButton.disabled = true;
    cancelButton.disabled = true;
    try {
      const files = await Promise.all([...input.files].map(upload));
      if (!activeChooser.backendNodeId) {
        throw new Error("The remote page did not expose a file input");
      }
      await send("DOM.setFileInputFiles", {
        backendNodeId: activeChooser.backendNodeId,
        files,
      });
      close();
    } catch (error) {
      console.error(error);
      description.textContent = error.message;
    } finally {
      chooseButton.disabled = false;
      cancelButton.disabled = false;
    }
  });
  dialog.addEventListener("keydown", (event) => {
    if (event.key === "Escape") cancel();
  });

  return { open, close, cancel };
}
