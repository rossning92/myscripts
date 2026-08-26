import assert from "node:assert/strict";
import test from "node:test";

import {
  parseKeyChord,
  pressKey,
} from "../extension/shared/actions.js";
import { captureScreenshot } from "../extension/shared/screenshot.js";
import {
  describeTarget,
  resolveTarget,
  TargetNotFoundError,
} from "../extension/shared/target.js";
import { upload } from "../extension/shared/upload.js";
import { normalizeUrl } from "../extension/shared/navigation.js";

test("normalizeUrl preserves schemes and defaults bare hosts to HTTP", () => {
  assert.equal(normalizeUrl("example.com"), "http://example.com");
  assert.equal(normalizeUrl("https://example.com"), "https://example.com");
  assert.equal(normalizeUrl("chrome://settings"), "chrome://settings");
});

test("parseKeyChord normalizes modifiers and named keys", () => {
  assert.deepEqual(parseKeyChord("Ctrl+Shift+left"), [
    "Control",
    "Shift",
    "ArrowLeft",
  ]);
});

test("pressKey dispatches a chord with modifier state", async () => {
  const calls = [];
  await pressKey(async (method, params) => calls.push({ method, params }), "Ctrl+A");
  assert.deepEqual(
    calls.map(({ params }) => [params.type, params.key, params.modifiers]),
    [
      ["keyDown", "Control", 2],
      ["keyDown", "A", 2],
      ["keyUp", "A", 2],
      ["keyUp", "Control", 2],
    ],
  );
});

test("resolveTarget reports a missing ref consistently", async () => {
  const send = async () => ({ result: { subtype: "null" } });
  await assert.rejects(
    resolveTarget(send, { ref: "@e9" }, { waitTimeoutMs: 0 }),
    (error) =>
      error instanceof TargetNotFoundError &&
      error.message === 'Unable to find element with ref "@e9"',
  );
  assert.equal(describeTarget({ ref: "@e9" }), 'ref "@e9"');
});

test("captureScreenshot uses CDP and returns base64 data", async () => {
  const calls = [];
  const result = await captureScreenshot(async (method, params) => {
    calls.push({ method, params });
    return { data: "cG5n" };
  });
  assert.deepEqual(result, { data: "cG5n" });
  assert.equal(calls[0].method, "Page.captureScreenshot");
});

test("upload sets files and releases the remote object", async () => {
  const calls = [];
  const send = async (method, params) => {
    calls.push({ method, params });
    if (method === "Runtime.evaluate") {
      return { result: { objectId: "object-1" } };
    }
    return {};
  };
  await upload(send, { ref: "@e0" }, "/tmp/example.txt");
  assert.deepEqual(
    calls.map(({ method }) => method),
    ["Runtime.evaluate", "DOM.setFileInputFiles", "Runtime.releaseObject"],
  );
  assert.deepEqual(calls[1].params, {
    objectId: "object-1",
    files: ["/tmp/example.txt"],
  });
});
