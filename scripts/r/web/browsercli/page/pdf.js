import { randomUUID } from "crypto";
import { writeFile } from "fs/promises";
import os from "os";
import path from "path";
import { withActivePageCdp } from "../browser/active-page-cdp.js";

function temporaryPdfPath() {
  return path.join(os.tmpdir(), `browsercli-${randomUUID()}.pdf`);
}

async function savePdfData(data, outputPath) {
  if (typeof data !== "string" || data.length === 0) {
    throw new Error("Browser returned an empty PDF");
  }
  const filePath = outputPath || temporaryPdfPath();
  await writeFile(filePath, Buffer.from(data, "base64"));
  return filePath;
}

export async function printPdf(outputPath) {
  const { data } = await withActivePageCdp((send) =>
    send("Page.printToPDF", {
      paperWidth: 8.5,
      paperHeight: 11,
    }),
  );
  return savePdfData(data, outputPath);
}
