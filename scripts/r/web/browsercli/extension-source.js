import { createHash } from "crypto";
import { readdir, readFile } from "fs/promises";
import { extname, join } from "path";

const SOURCE_EXTENSIONS = new Set([".css", ".html", ".js", ".json"]);

async function addDirectoryToHash(hash, directory, relativeDirectory = "") {
  const entries = await readdir(directory, { withFileTypes: true });
  entries.sort((a, b) => a.name.localeCompare(b.name));

  for (const entry of entries) {
    const relativePath = join(relativeDirectory, entry.name);
    const fullPath = join(directory, entry.name);
    if (entry.isDirectory()) {
      await addDirectoryToHash(hash, fullPath, relativePath);
    } else if (SOURCE_EXTENSIONS.has(extname(entry.name))) {
      hash.update(relativePath);
      hash.update("\0");
      hash.update(await readFile(fullPath));
      hash.update("\0");
    }
  }
}

export async function getExtensionSourceVersion(extensionDirectory) {
  const hash = createHash("sha256");
  await addDirectoryToHash(hash, extensionDirectory);
  return hash.digest("hex");
}
