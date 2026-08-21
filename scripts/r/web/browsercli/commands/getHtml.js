import { withActivePage } from "../browser-core.js";
import { extractPageContent } from "../extension/page-content.js";

export async function getHtml(url) {
  return withActivePage(
    async (page) => await page.evaluate(extractPageContent, "get-html"),
    { url },
  );
}
