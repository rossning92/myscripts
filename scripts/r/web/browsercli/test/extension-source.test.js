import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "fs/promises";
import os from "os";
import path from "path";
import test from "node:test";

import { getExtensionSourceVersion } from "../extension-source.js";

test("extension source version changes with extension code", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "browsercli-extension-"));
  await writeFile(path.join(directory, "service-worker.js"), "const version = 1;\n");
  const first = await getExtensionSourceVersion(directory);

  await writeFile(path.join(directory, "service-worker.js"), "const version = 2;\n");
  const second = await getExtensionSourceVersion(directory);

  assert.notEqual(first, second);
});

test("extension source version ignores documentation", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "browsercli-extension-"));
  await writeFile(path.join(directory, "service-worker.js"), "const version = 1;\n");
  const first = await getExtensionSourceVersion(directory);

  await writeFile(path.join(directory, "README.md"), "New docs\n");
  assert.equal(await getExtensionSourceVersion(directory), first);
});
