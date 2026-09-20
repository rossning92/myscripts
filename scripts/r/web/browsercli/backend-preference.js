import { homedir } from "os";
import { dirname, join } from "path";
import { mkdir, readFile, rename, writeFile } from "fs/promises";

const VALID_BACKENDS = new Set(["browser", "extension"]);

export function getBackendPreferencePath(env = process.env) {
  const configRoot =
    env.XDG_CONFIG_HOME ||
    env.APPDATA ||
    join(homedir(), ".config");
  return join(configRoot, "browsercli", "backend");
}

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
