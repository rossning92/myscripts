export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export class TargetNotFoundError extends Error {}

export function cdpError(response, fallback) {
  if (!response?.exceptionDetails) return;
  throw new Error(
    response.exceptionDetails.exception?.description ||
      response.exceptionDetails.text ||
      fallback,
  );
}

export async function callFunction(send, objectId, fn, args = []) {
  const response = await send("Runtime.callFunctionOn", {
    objectId,
    functionDeclaration: fn.toString(),
    arguments: args.map((value) => ({ value })),
    awaitPromise: true,
    returnByValue: true,
  });
  cdpError(response, "Page command failed");
  return response.result?.value;
}
