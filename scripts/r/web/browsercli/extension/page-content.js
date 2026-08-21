// This function is self-contained so Puppeteer can serialize it and the
// extension can inject its source through Runtime.evaluate.
export function extractPageContent(command) {
  const content = document.getElementById("content");

  if (command === "get-text") {
    return (content || document.body).innerText;
  }
  if (command === "get-html") {
    const doctype = document.doctype
      ? `<!DOCTYPE ${document.doctype.name}>`
      : "";
    return doctype + document.documentElement.outerHTML;
  }
  if (command === "get-markdown") {
    return (content || document.body).innerHTML;
  }
  throw new Error(`Unsupported content command: ${command}`);
}
