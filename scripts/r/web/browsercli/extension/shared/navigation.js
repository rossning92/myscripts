export function normalizeUrl(url) {
  if (!url) return null;
  if (/^[a-z][a-z\d+.-]*:/i.test(url)) return url;
  return `http://${url}`;
}

async function navigateHistory(send, delta) {
  const { currentIndex, entries } = await send("Page.getNavigationHistory");
  const entry = entries[currentIndex + delta];
  if (!entry) return false;
  await send("Page.navigateToHistoryEntry", { entryId: entry.id });
  return true;
}

export async function goBack(send) {
  return navigateHistory(send, -1);
}

export async function goForward(send) {
  return navigateHistory(send, 1);
}

export async function reload(send) {
  await send("Page.reload");
}
