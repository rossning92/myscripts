import assert from "node:assert/strict";
import test from "node:test";
import { parseViewport } from "../viewport.js";

test("parseViewport accepts common separators and whitespace", () => {
  assert.deepEqual(parseViewport(" 1280x720 "), { width: 1280, height: 720 });
  assert.deepEqual(parseViewport("390×844"), { width: 390, height: 844 });
});

test("parseViewport rejects invalid and unreasonable dimensions", () => {
  assert.throws(() => parseViewport("wide"), /WIDTHxHEIGHT/);
  assert.throws(() => parseViewport("100x100"), /between 200 and 7680/);
  assert.throws(() => parseViewport("9999x720"), /between 200 and 7680/);
});
