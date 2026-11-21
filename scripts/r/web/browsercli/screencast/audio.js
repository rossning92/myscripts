import { execFile } from "child_process";
import { promisify } from "util";
import { debugPort } from "../config.js";

const exec = promisify(execFile);
export const sinkName = () => `browsercli_${debugPort()}`;

export async function hasAudioSink() {
  if (process.platform !== "linux") return false;
  try {
    const { stdout } = await exec("pactl", ["list", "short", "sinks"], {
      timeout: 2000,
    });
    return stdout.split("\n").some((line) => line.split("\t")[1] === sinkName());
  } catch {
    return false;
  }
}

export async function prepareBrowserAudioEnv() {
  if (process.platform !== "linux") return process.env;

  const sink = sinkName();
  try {
    await exec("parec", ["--version"], { timeout: 2000 });
    if (!(await hasAudioSink())) {
      await exec("pactl", [
        "load-module", "module-null-sink", `sink_name=${sink}`,
      ], { timeout: 2000 });
    }
  } catch {
    return process.env;
  }

  // Keep PulseAudio's saved routing separate from desktop Chrome.
  const applicationId = `application.id=org.browsercli.capture.${debugPort()}`;
  return {
    ...process.env,
    PULSE_SINK: sink,
    PULSE_PROP: [process.env.PULSE_PROP, applicationId].filter(Boolean).join("\n"),
  };
}

