function copyStyles(source, target) {
  for (const styleSheet of source.styleSheets) {
    try {
      const css = [...styleSheet.cssRules]
        .map((rule) => rule.cssText)
        .join("\n");
      const style = target.createElement("style");
      style.textContent = css;
      target.head.appendChild(style);
    } catch (_e) {}
  }
}

export function setupPictureInPicture({
  button,
  elements,
  videoSource,
  width,
  height,
  title,
}) {
  const supportsDocumentPip = "documentPictureInPicture" in window;
  const supportsVideoPip =
    Boolean(videoSource?.captureStream) &&
    document.pictureInPictureEnabled &&
    "requestPictureInPicture" in HTMLVideoElement.prototype;

  if (!supportsDocumentPip && !supportsVideoPip) {
    button.hidden = true;
    return { refreshVideo() {} };
  }

  const anchors = supportsDocumentPip
    ? elements.map((element) => {
        const anchor = document.createComment("picture-in-picture anchor");
        element.before(anchor);
        return { anchor, element };
      })
    : [];
  let pipWindow = null;
  let pipVideo = null;
  let videoWidth = 0;
  let videoHeight = 0;
  if (!supportsDocumentPip) button.disabled = true;

  function prepareVideo() {
    if (
      supportsDocumentPip ||
      !videoSource.width ||
      !videoSource.height ||
      (videoSource.width === videoWidth && videoSource.height === videoHeight)
    ) {
      return;
    }
    // Changing the stream while PiP is open closes it on Android. Defer the
    // new aspect ratio until the user returns to the page.
    if (document.pictureInPictureElement) return;

    for (const track of pipVideo?.srcObject?.getTracks?.() || []) track.stop();
    pipVideo?.remove();

    // Prepare the video before the click. requestPictureInPicture() must be
    // called directly from the user gesture, after video metadata is ready.
    videoWidth = videoSource.width;
    videoHeight = videoSource.height;
    pipVideo = document.createElement("video");
    const preparedVideo = pipVideo;
    button.disabled = true;
    pipVideo.muted = true;
    pipVideo.playsInline = true;
    pipVideo.width = videoWidth;
    pipVideo.height = videoHeight;
    pipVideo.srcObject = videoSource.captureStream(30);
    pipVideo.style.cssText = [
      "position:fixed",
      "left:-100000px",
      `width:${videoWidth}px`,
      `height:${videoHeight}px`,
      `aspect-ratio:${videoWidth} / ${videoHeight}`,
    ].join(";");
    pipVideo.addEventListener("loadedmetadata", () => {
      if (pipVideo === preparedVideo) button.disabled = false;
    });
    pipVideo.addEventListener("leavepictureinpicture", () => {
      setButtonState(false);
    });
    document.body.appendChild(pipVideo);
    pipVideo.play().catch((error) => {
      console.error("Unable to start picture in picture video", error);
    });
  }

  function setButtonState(active) {
    const action = active ? "Close" : "Open";
    button.setAttribute("aria-pressed", String(active));
    button.title = active ? "Close picture in picture" : "Picture in picture";
    button.setAttribute("aria-label", `${action} picture in picture`);
  }

  function restoreElements() {
    for (const { anchor, element } of anchors) anchor.after(element);
    pipWindow = null;
    setButtonState(false);
  }

  async function toggleVideoPip() {
    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture();
      return;
    }

    // Android Chrome supports video PiP, but not Document PiP. Mirror the
    // screencast canvas into a video so it can use Android's native PiP window.
    await pipVideo.requestPictureInPicture();
    setButtonState(true);
  }

  async function toggle() {
    if (pipWindow) {
      pipWindow.close();
      return;
    }

    try {
      if (supportsDocumentPip) {
        pipWindow = await window.documentPictureInPicture.requestWindow({
          width,
          height,
        });
        copyStyles(document, pipWindow.document);
        pipWindow.document.title = title;
        pipWindow.document.body.append(...elements);
        pipWindow.addEventListener("pagehide", restoreElements, { once: true });
        setButtonState(true);
      } else {
        await toggleVideoPip();
      }
    } catch (error) {
      pipWindow = null;
      setButtonState(false);
      console.error("Unable to open picture in picture", error);
    }
  }

  button.addEventListener("click", toggle);
  return { refreshVideo: prepareVideo };
}
