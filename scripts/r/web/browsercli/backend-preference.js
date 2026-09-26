import { dirname } from "path";
import { mkdir, readFile, rename, writeFile } from "fs/promises";
import { getBackendPreferencePath } from "./app-paths.js";

export { getBackendPreferencePath } from "./app-paths.js";

const VALID_BACKENDS = new Set(["browser", "extension"]);

export async function loadBackendPreference(filePath = getBackendPreferencePath()) {
  try {
    const backend = (await readFile(filePath, "utf8")).trim();
    return VALID_BACKENDS.has(backend) ? backend : "browser";
  } catch {
    return "browser";
  }
}

export async function saveBackendPreference(
  backend,
  filePath = getBackendPreferencePath(),
) {
  if (!VALID_BACKENDS.has(backend)) {
    throw new Error(`Unsupported browser backend: ${backend}`);
  }

  await mkdir(dirname(filePath), { recursive: true });
  const temporaryPath = `${filePath}.${process.pid}.tmp`;
  await writeFile(temporaryPath, `${backend}\n`, { mode: 0o600 });
  await rename(temporaryPath, filePath);
}
