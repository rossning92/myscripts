import TurndownService from "turndown";
import { withActivePage } from "../browser-core.js";
import { extractPageContent } from "../extension/page-content.js";

export function htmlToMarkdown(html) {
  const turndownService = new TurndownService({
    blankReplacement: () => "",
    defaultReplacement: (content, node) =>
      node.isBlock ? `\n${content.trim()}\n` : content,
  });
  turndownService.remove("script");
  turndownService.remove("style");
  turndownService.addRule("remove-base64-images", {
    filter: (node) =>
      node.nodeName === "IMG" &&
      node.getAttribute("src")?.startsWith("data:"),
    replacement: () => "",
  });
  turndownService.addRule("normalize-bracketed", {
    filter: ["a", "button"],
    replacement: (content, node) => {
      const cleaned = content.trim().replace(/\s+/g, " ");
      if (node.nodeName === "A") {
        const href = node.getAttribute("href");
        if (href) return `[${cleaned}](${href})`;
      }
      return `[${cleaned}]`;
    },
  });
  return turndownService.turndown(html);
}

export async function getPageHtml(page) {
  return page.evaluate(extractPageContent, "get-markdown");
}

export async function getMarkdown() {
  return withActivePage(
    async (page) => htmlToMarkdown(await getPageHtml(page)),
  );
}
