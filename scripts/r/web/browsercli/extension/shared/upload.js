import { releaseTarget, resolveTarget } from "./target.js";

export async function upload(send, target, filePath) {
  const resolved = await resolveTarget(send, target);
  try {
    await resolved.send("DOM.setFileInputFiles", {
      objectId: resolved.objectId,
      files: [filePath],
    });
  } finally {
    await releaseTarget(resolved);
  }
}
