import { currentSession, WINDOW_HEIGHT, WINDOW_WIDTH } from "./config.js";

const VIEWPORT_PATTERN = /^(\d+)\s*[xX×]\s*(\d+)$/;

export function parseViewport(value) {
  if (typeof value !== "string") {
    throw new Error('Viewport must use the format "WIDTHxHEIGHT"');
  }
  const match = value.trim().match(VIEWPORT_PATTERN);
  if (!match) throw new Error('Viewport must use the format "WIDTHxHEIGHT"');

  const width = Number(match[1]);
  const height = Number(match[2]);
  if (width < 200 || height < 200 || width > 7680 || height > 7680) {
    throw new Error("Viewport dimensions must be between 200 and 7680 pixels");
  }
  return { width, height };
}

const defaultViewport = { width: WINDOW_WIDTH, height: WINDOW_HEIGHT };
const viewports = new Map();

export function getViewport() {
  return { ...(viewports.get(currentSession()) ?? defaultViewport) };
}

export function setViewport(viewport) {
  viewports.set(currentSession(), { width: viewport.width, height: viewport.height });
  return getViewport();
}
