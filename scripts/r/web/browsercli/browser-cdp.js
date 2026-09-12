import { withActivePage } from "./browser-core.js";

export async function withActivePageCdp(callback) {
  return withActivePage(async (page, browser) => {
    const client = await page.createCDPSession();
    const send = (method, params) => client.send(method, params);
    send.contexts = [{ send, url: await page.url() }];
    const attachedSessions = [];
    try {
      const { targetInfos = [] } = await browser.connection.send(
        "Target.getTargets",
      );
      for (const target of targetInfos) {
        if (target.type !== "iframe") continue;
        try {
          const { sessionId } = await browser.connection.send(
            "Target.attachToTarget",
            { targetId: target.targetId, flatten: true },
          );
          attachedSessions.push(sessionId);
          const contextSend = (method, params = {}) =>
            browser.connection.send(method, params, sessionId);
          send.contexts.push({ send: contextSend, url: target.url });
        } catch {}
      }
      return await callback(send, page);
    } finally {
      await Promise.all(attachedSessions.map((sessionId) =>
        browser.connection.send("Target.detachFromTarget", { sessionId })
          .catch(() => {}),
      ));
      await client.detach();
    }
  });
}
