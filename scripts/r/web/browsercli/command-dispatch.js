import { resolve } from "path";
import {
  getBrowser,
  getOrOpenPage,
  closeBrowser,
  getStatus,
  restoreOpenerPage,
  withActivePage,
} from "./browser/browser-core.js";
import { withActivePageCdp } from "./browser/active-page-cdp.js";
import { currentSession } from "./config.js";
import {
  click as clickCdp,
  pressKey as pressKeyCdp,
  scroll as scrollCdp,
  select as selectCdp,
  typeText as typeTextCdp,
} from "./extension/shared/actions.js";
import { evaluatePageContent } from "./extension/shared/evaluate-page-content.js";
import { upload as uploadCdp } from "./extension/shared/upload.js";
import { getMarkdownHtml, htmlToMarkdown } from "./page/get-markdown.js";
import { snapshot } from "./page/snapshot.js";
import { saveScreenshotData, screenshot } from "./page/screenshot.js";
import { printPdf } from "./page/pdf.js";
import { screencast } from "./screencast/screencast.js";
import { extensionBridge } from "./extension-bridge.js";
import { parseViewport, setViewport } from "./browser/viewport.js";
import {
  loadBackendPreference,
  saveBackendPreference,
} from "./backend-preference.js";
import {
  goBackOrRestore,
  goForward,
  reload,
} from "./extension/shared/navigation.js";

let defaultBackend = await loadBackendPreference();
const activeBackend = () => (currentSession() ? "browser" : defaultBackend);

async function runOnActiveBackend(command, args, browserHandler) {
  if (activeBackend() === "extension") {
    return await extensionBridge.send(command, args);
  }
  return await browserHandler();
}

export const commands = {
  async open({ url, headed }) {
    if (activeBackend() === "extension") {
      await extensionBridge.send("open", { url });
      return { mode: "extension", backend: activeBackend() };
    }
    const browser = await getBrowser({ headed });
    await getOrOpenPage(browser, url);
    return getStatus();
  },

  async "set-viewport"({ viewport }) {
    if (activeBackend() === "extension") {
      throw new Error(
        "Viewport emulation is only available for the managed browser backend",
      );
    }
    const dimensions = parseViewport(viewport);
    await withActivePage((page) =>
      page.setViewport({ ...dimensions, deviceScaleFactor: 1 }),
    );
    setViewport(dimensions);
    return dimensions;
  },

  async connect({ backend, headed }) {
    if (backend !== "browser" && backend !== "extension") {
      throw new Error('Backend must be "browser" or "extension"');
    }
    if (currentSession() && backend === "extension") {
      throw new Error(
        "Named sessions are only supported by the managed browser backend",
      );
    }
    if (backend === "extension") {
      await extensionBridge.send("ping", {});
    } else {
      await getBrowser({ headed });
    }
    if (!currentSession()) {
      defaultBackend = backend;
      await saveBackendPreference(defaultBackend);
    }
    return { backend };
  },

  async close() {
    return await runOnActiveBackend("close", {}, () =>
      withActivePage((page) => page.close()),
    );
  },

  async "close-browser"() {
    await closeBrowser();
  },

  async "shutdown-daemon"() {
    setTimeout(() => process.exit(0), 100);
  },

  async "get-text"() {
    return await runOnActiveBackend("get-text", {}, () =>
      withActivePageCdp((send) => evaluatePageContent(send, "get-text")),
    );
  },

  async "get-html"() {
    return await runOnActiveBackend("get-html", {}, () =>
      withActivePageCdp((send) => evaluatePageContent(send, "get-html")),
    );
  },

  async "get-markdown"() {
    const html = await runOnActiveBackend("get-markdown", {}, getMarkdownHtml);
    return htmlToMarkdown(html);
  },

  async snapshot() {
    return await runOnActiveBackend("snapshot", {}, snapshot);
  },

  async scroll({ direction, pixels }) {
    const args = { direction, pixels };
    return await runOnActiveBackend("scroll", args, () =>
      withActivePageCdp((send) => scrollCdp(send, args)),
    );
  },

  async back() {
    return await runOnActiveBackend("back", {}, () =>
      withActivePage(async (page, browser) => {
        const session = await page.createCDPSession();
        return goBackOrRestore(
          session.send.bind(session),
          () => restoreOpenerPage(page, browser),
        );
      }),
    );
  },

  async forward() {
    return await runOnActiveBackend("forward", {}, () =>
      withActivePageCdp(goForward),
    );
  },

  async reload() {
    return await runOnActiveBackend("reload", {}, () =>
      withActivePageCdp(reload),
    );
  },

  async click(target) {
    return await runOnActiveBackend("click", target, () =>
      withActivePageCdp((send) => clickCdp(send, target)),
    );
  },

  async type({ text, ...target }) {
    return await runOnActiveBackend("type", { text, ...target }, () =>
      withActivePageCdp((send) => typeTextCdp(send, text, target)),
    );
  },

  async fill({ text, ...target }) {
    return await runOnActiveBackend("fill", { text, ...target }, () =>
      withActivePageCdp((send) =>
        typeTextCdp(send, text, target, { clear: true }),
      ),
    );
  },

  async press({ key }) {
    return await runOnActiveBackend("press", { key }, () =>
      withActivePageCdp((send) => pressKeyCdp(send, key)),
    );
  },

  async select({ value, ...target }) {
    return await runOnActiveBackend("select", { value, ...target }, () =>
      withActivePageCdp((send) => selectCdp(send, target, value)),
    );
  },

  async upload({ filePath, ...target }) {
    const absolutePath = resolve(filePath);
    return await runOnActiveBackend(
      "upload",
      { filePath: absolutePath, ...target },
      () => withActivePageCdp((send) => uploadCdp(send, target, absolutePath)),
    );
  },

  async screenshot({ output, ...target } = {}) {
    if (activeBackend() === "extension") {
      const { data } = await extensionBridge.send("screenshot", target);
      return await saveScreenshotData(data, output);
    }
    return await screenshot(target, output);
  },

  async pdf({ output } = {}) {
    if (activeBackend() === "extension") {
      throw new Error("pdf is only available for the managed browser backend");
    }
    return await printPdf(output);
  },

  async screencast() {
    if (activeBackend() === "extension") {
      throw new Error("screencast is only available for the managed browser backend");
    }
    return await screencast();
  },
};
