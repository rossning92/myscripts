import { withActivePage } from "../browser-core.js";

export async function getHtml(url) {
  return withActivePage(
    async (page) => await page.content(),
    { url },
  );
}
