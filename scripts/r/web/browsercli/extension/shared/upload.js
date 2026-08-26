import { releaseTarget, resolveTarget } from "./target.js";

export async function upload(send, target, filePath) {
  const objectId = await resolveTarget(send, target);
  try {
    await send("DOM.setFileInputFiles", {
      objectId,
      files: [filePath],
    });
  } finally {
    await releaseTarget(send, objectId);
  }
}
