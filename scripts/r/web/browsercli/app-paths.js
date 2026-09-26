import os from "os";
import path from "path";

export function getAppDataDir({
  platform = process.platform,
  env = process.env,
  homedir = os.homedir(),
} = {}) {
  if (platform === "win32") {
    return path.join(
      env.LOCALAPPDATA || env.APPDATA || path.join(homedir, "AppData", "Local"),
      "browsercli",
    );
  }
  if (platform === "darwin") {
    return path.join(homedir, "Library", "Application Support", "browsercli");
  }
  const dataRoot =
    env.XDG_DATA_HOME || path.join(homedir, ".local", "share");
  return path.join(dataRoot, "browsercli");
}

export function getProfileDir(session, options) {
  return path.join(getAppDataDir(options), "profiles", session || "default");
}

export function getBackendPreferencePath(options) {
  return path.join(getAppDataDir(options), "backend");
}
