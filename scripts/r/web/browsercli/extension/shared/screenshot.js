import { callFunction } from "./cdp-utils.js";
import { releaseTarget, resolveTarget } from "./target.js";

export async function captureScreenshot(send, args = {}) {
  let clip;
  let objectId;
  if (args.ref || (args.role && args.name)) {
    objectId = await resolveTarget(send, args);
    try {
      const rect = await callFunction(send, objectId, function () {
        this.scrollIntoView({ block: "center", inline: "center" });
        const bounds = this.getBoundingClientRect();
        if (bounds.width <= 0 || bounds.height <= 0) {
          throw new Error("Target element has no visible area");
        }
        return {
          x: bounds.left + window.scrollX,
          y: bounds.top + window.scrollY,
          width: bounds.width,
          height: bounds.height,
        };
      });
      clip = { ...rect, scale: 1 };
    } finally {
      await releaseTarget(send, objectId);
    }
  }
  const { data } = await send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    ...(clip ? { clip, captureBeyondViewport: true } : {}),
  });
  return { data };
}
