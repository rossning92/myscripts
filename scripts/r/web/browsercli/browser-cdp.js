import { withActivePage } from "./browser-core.js";

export async function withActivePageCdp(callback) {
  return withActivePage(async (page) => {
    const client = await page.createCDPSession();
    try {
      return await callback(
        (method, params) => client.send(method, params),
        page,
      );
    } finally {
      await client.detach();
    }
  });
}
