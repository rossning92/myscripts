import { releaseTarget, resolveTarget } from "./target.js";

export async function captureScreenshot(send, args = {}) {
  let clip;
  let resolved;
  if (args.ref || (args.role && args.name)) {
    resolved = await resolveTarget(send, args);
    try {
      await resolved.send("DOM.scrollIntoViewIfNeeded", {
        objectId: resolved.objectId,
      }).catch(() => {});
      const { model } = await resolved.send("DOM.getBoxModel", {
        objectId: resolved.objectId,
      });
      const quad = model?.border;
      if (!quad || quad.length !== 8) {
        throw new Error("Target element has no visible area");
      }
      const xs = [quad[0], quad[2], quad[4], quad[6]];
      const ys = [quad[1], quad[3], quad[5], quad[7]];
      const rect = {
        x: Math.min(...xs),
        y: Math.min(...ys),
        width: Math.max(...xs) - Math.min(...xs),
        height: Math.max(...ys) - Math.min(...ys),
      };
      clip = { ...rect, scale: 1 };
    } finally {
      await releaseTarget(resolved);
    }
  }
  const { data } = await send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    ...(clip ? { clip, captureBeyondViewport: true } : {}),
  });
  return { data };
}
