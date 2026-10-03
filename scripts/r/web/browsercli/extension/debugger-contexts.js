const AUTO_ATTACH_OPTIONS = {
  autoAttach: true,
  waitForDebuggerOnStart: false,
  flatten: true,
  filter: [{ type: "iframe", exclude: false }],
};

const CONTEXT_SETTLE_MS = 25;
const CONTEXT_TIMEOUT_MS = 1000;

function sameRootTarget(source, target) {
  return source.tabId === target.tabId &&
    source.targetId === target.targetId &&
    source.extensionId === target.extensionId;
}

export async function attachFrameContexts(debuggerApi, target) {
  const contexts = [];
  let lastChange = Date.now();
  let pending = 0;

  const onEvent = (source, method, params) => {
    if (method !== "Target.attachedToTarget" ||
        !sameRootTarget(source, target) || !params?.sessionId ||
        params.targetInfo?.type !== "iframe") return;

    const session = { ...target, sessionId: params.sessionId };
    const send = (command, commandParams = {}) =>
      debuggerApi.sendCommand(session, command, commandParams);
    contexts.push({ send, url: params.targetInfo.url || "about:blank" });
    lastChange = Date.now();
    pending++;
    send("Target.setAutoAttach", AUTO_ATTACH_OPTIONS)
      .catch(() => {})
      .finally(() => {
        pending--;
        lastChange = Date.now();
      });
  };

  debuggerApi.onEvent.addListener(onEvent);
  try {
    await debuggerApi.sendCommand(
      target,
      "Target.setAutoAttach",
      AUTO_ATTACH_OPTIONS,
    );
    const deadline = Date.now() + CONTEXT_TIMEOUT_MS;
    while (Date.now() < deadline &&
           (pending > 0 || Date.now() - lastChange < CONTEXT_SETTLE_MS)) {
      await new Promise((resolve) => setTimeout(resolve, CONTEXT_SETTLE_MS));
    }
    return {
      contexts,
      detach: () => debuggerApi.onEvent.removeListener(onEvent),
    };
  } catch (error) {
    debuggerApi.onEvent.removeListener(onEvent);
    throw error;
  }
}
