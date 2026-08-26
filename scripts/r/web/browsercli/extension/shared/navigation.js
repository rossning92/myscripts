export function normalizeUrl(url) {
  if (!url) return null;
  if (/^[a-z][a-z\d+.-]*:/i.test(url)) return url;
  return `http://${url}`;
}
