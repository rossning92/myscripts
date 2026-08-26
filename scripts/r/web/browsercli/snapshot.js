import { withActivePageCdp } from "./browser-cdp.js";
import { collectSnapshot } from "./extension/shared/snapshot-cdp.js";

export { formatSnapshot } from "./extension/shared/snapshot.js";

export async function snapshot() {
  return withActivePageCdp(async (send, page) => {
    const title = await page.title();
    const url = await page.url();
    return collectSnapshot(send, { title, url });
  });
}
