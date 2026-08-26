import { extractPageContent } from "./extract-page-content.js";

export async function evaluatePageContent(send, command) {
  const response = await send("Runtime.evaluate", {
    expression: `(${extractPageContent.toString()})(${JSON.stringify(command)})`,
    returnByValue: true,
  });

  if (response.exceptionDetails) {
    throw new Error(
      response.exceptionDetails.exception?.description ||
        response.exceptionDetails.text ||
        `Unable to run ${command}`,
    );
  }

  return response.result?.value;
}
