import { EventEmitter } from "events";
import { connectToBrowser } from "./cdp-client.js";

const NAVIGATION_TIMEOUT_MS = 30_000;

class CdpSession {
  constructor(page) {
    this.page = page;
  }

  send(method, params = {}) {
    return this.page.send(method, params);
  }

  // Page sessions are shared and retained so dialog handling and subsequent
  // commands do not repeatedly attach to the same target.
  async detach() {}
}

class CdpResponse {
  constructor(response) {
    this.response = response;
  }

  ok() {
    return this.response.status >= 200 && this.response.status <= 299;
  }

  status() {
    return this.response.status;
  }

  statusText() {
    return this.response.statusText;
  }
}

export class CdpPage {
  constructor(browser, targetInfo, sessionId) {
    this.browser = browser;
    this.targetInfo = targetInfo;
    this.sessionId = sessionId;
  }

  send(method, params = {}) {
    return this.browser.connection.send(method, params, this.sessionId);
  }

  async evaluate(fn, ...args) {
    const expression = `(${fn.toString()})(...${JSON.stringify(args)})`;
    const { result, exceptionDetails } = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (exceptionDetails) {
      throw new Error(
        exceptionDetails.exception?.description ||
          exceptionDetails.text ||
          "Page evaluation failed",
      );
    }
    return result?.value;
  }

  async goto(url, { waitUntil = "domcontentloaded" } = {}) {
    await Promise.all([
      this.send("Page.enable"),
      this.send("Network.enable"),
    ]);

    let mainResponse;
    let frameId;
    const lifecycleMethod =
      waitUntil === "domcontentloaded"
        ? "Page.domContentEventFired"
        : "Page.loadEventFired";

    const onResponse = (params, sessionId) => {
      if (
        sessionId === this.sessionId &&
        params.type === "Document" &&
        (!frameId || params.frameId === frameId)
      ) {
        mainResponse = params.response;
      }
    };
    this.browser.connection.on("Network.responseReceived", onResponse);

    try {
      const navigationDone = this.browser.waitForSessionEvent(
        lifecycleMethod,
        this.sessionId,
        NAVIGATION_TIMEOUT_MS,
      );
      const navigation = await this.send("Page.navigate", { url });
      frameId = navigation.frameId;
      if (navigation.errorText) {
        throw new Error(`Failed to navigate: ${navigation.errorText}`);
      }
      await navigationDone;
      this.targetInfo = { ...this.targetInfo, url };
      return mainResponse ? new CdpResponse(mainResponse) : null;
    } finally {
      this.browser.connection.off("Network.responseReceived", onResponse);
    }
  }

  async setViewport({ width, height, deviceScaleFactor = 1 }) {
    await this.send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor,
      mobile: false,
    });
  }

  async title() {
    return this.evaluate(() => document.title);
  }

  async url() {
    return this.evaluate(() => location.href);
  }

  async close() {
    await this.browser.connection.send("Target.closeTarget", {
      targetId: this.targetInfo.targetId,
    });
  }

  async createCDPSession() {
    return new CdpSession(this);
  }
}

export class CdpBrowser extends EventEmitter {
  constructor(connection) {
    super();
    this.connection = connection;
    this.pageCache = new Map();
    this.pagePromises = new Map();
    connection.on("disconnected", () => this.emit("disconnected"));
    connection.on("Target.targetDestroyed", ({ targetId }) => {
      this.pageCache.delete(targetId);
      this.pagePromises.delete(targetId);
    });
    connection.on("Target.targetCreated", ({ targetInfo }) => {
      if (targetInfo.type === "page") this.#getPage(targetInfo).catch(() => {});
    });
    connection.on(
      "Page.javascriptDialogOpening",
      ({ type, message }, sessionId) => {
        console.log(`Automatically accepting dialog: [${type}] ${message}`);
        connection
          .send("Page.handleJavaScriptDialog", { accept: true }, sessionId)
          .catch(() => {});
      },
    );
  }

  static async connect(browserUrl) {
    const browser = new CdpBrowser(await connectToBrowser(browserUrl));
    await browser.connection.send("Target.setDiscoverTargets", {
      discover: true,
    });
    return browser;
  }

  isConnected() {
    return this.connection.isConnected();
  }

  async pages() {
    const { targetInfos } = await this.connection.send("Target.getTargets");
    const pageInfos = targetInfos.filter((target) => target.type === "page");
    return Promise.all(pageInfos.map((target) => this.#getPage(target)));
  }

  async newPage() {
    const { targetId } = await this.connection.send("Target.createTarget", {
      url: "about:blank",
    });
    const { targetInfo } = await this.connection.send("Target.getTargetInfo", {
      targetId,
    });
    return this.#getPage(targetInfo);
  }

  async close() {
    try {
      await this.connection.send("Browser.close");
    } catch (error) {
      if (this.connection.isConnected()) throw error;
    } finally {
      this.connection.close();
    }
  }

  waitForSessionEvent(method, sessionId, timeoutMs) {
    return new Promise((resolve, reject) => {
      const listener = (params, eventSessionId) => {
        if (eventSessionId !== sessionId) return;
        clearTimeout(timeout);
        this.connection.off(method, listener);
        resolve(params);
      };
      const timeout = setTimeout(() => {
        this.connection.off(method, listener);
        reject(new Error(`Timed out waiting for ${method}`));
      }, timeoutMs);
      this.connection.on(method, listener);
    });
  }

  async #getPage(targetInfo) {
    const cached = this.pageCache.get(targetInfo.targetId);
    if (cached) {
      cached.targetInfo = targetInfo;
      return cached;
    }

    const pending = this.pagePromises.get(targetInfo.targetId);
    if (pending) return pending;

    const pagePromise = this.#attachPage(targetInfo);
    this.pagePromises.set(targetInfo.targetId, pagePromise);
    try {
      return await pagePromise;
    } finally {
      this.pagePromises.delete(targetInfo.targetId);
    }
  }

  async #attachPage(targetInfo) {
    const { sessionId } = await this.connection.send("Target.attachToTarget", {
      targetId: targetInfo.targetId,
      flatten: true,
    });
    const page = new CdpPage(this, targetInfo, sessionId);
    this.pageCache.set(targetInfo.targetId, page);
    await page.send("Page.enable");
    return page;
  }
}
