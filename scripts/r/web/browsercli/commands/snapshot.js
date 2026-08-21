import { withActivePage } from "../browser-core.js";
import { collectSnapshot } from "../extension/snapshot-cdp.js";

export { formatSnapshot } from "../extension/snapshot.js";

export async function snapshot() {
  return withActivePage(async (page) => {
    const title = await page.title();
    const url = await page.url();
    const client = await page.createCDPSession();
    try {
      return await collectSnapshot(
        (method, params) => client.send(method, params),
        { title, url },
      );
    } finally {
      await client.detach();
    }
  });
}
