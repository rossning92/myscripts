import { cdpError, sleep, TargetNotFoundError } from "./cdp-utils.js";

export { TargetNotFoundError } from "./cdp-utils.js";

const DEFAULT_WAIT_TIMEOUT_MS = 10000;
const DEFAULT_WAIT_INTERVAL_MS = 100;

// Self-contained because it is serialized into Runtime.evaluate.
export function findElementByRef(ref) {
  const wanted = String(ref).replace(/^@/, "");
  const walk = (root) => {
    const found = root.querySelector(
      `[data-agent-ref="${CSS.escape(wanted)}"]`,
    );
    if (found) return found;
    for (const element of root.querySelectorAll("*")) {
      if (element.shadowRoot) {
        const nested = walk(element.shadowRoot);
        if (nested) return nested;
      }
    }
    return null;
  };
  return walk(document);
}

export function describeTarget({ ref, role, name }) {
  return ref ? `ref "${ref}"` : `${role} named "${name}"`;
}

async function evaluateTarget(send, expression, description) {
  const response = await send("Runtime.evaluate", { expression });
  cdpError(response, "Unable to resolve target element");
  if (!response.result?.objectId || response.result.subtype === "null") {
    throw new TargetNotFoundError(
      `Unable to find element with ${description}`,
    );
  }
  return response.result.objectId;
}

async function resolveAccessibilityTarget(send, { role, name }) {
  await send("Accessibility.enable");
  const { root } = await send("DOM.getDocument", { depth: 0 });
  const { nodes = [] } = await send("Accessibility.queryAXTree", {
    nodeId: root.nodeId,
    accessibleName: name,
    role,
  });
  const node = nodes.find(
    (item) =>
      !item.ignored &&
      item.backendDOMNodeId &&
      item.role?.value === role &&
      item.name?.value === name,
  );
  if (!node) {
    throw new TargetNotFoundError(
      `Unable to find element with ${role} named "${name}"`,
    );
  }
  const { object } = await send("DOM.resolveNode", {
    backendNodeId: node.backendDOMNodeId,
  });
  if (!object?.objectId) {
    throw new TargetNotFoundError("Unable to resolve accessibility node");
  }
  return object.objectId;
}

async function resolveTargetOnce(send, args, { focused = false } = {}) {
  if (args.role && args.name) {
    return resolveAccessibilityTarget(send, args);
  }
  if (args.ref) {
    return evaluateTarget(
      send,
      `(${findElementByRef.toString()})(${JSON.stringify(args.ref)})`,
      `ref "${args.ref}"`,
    );
  }
  if (focused) {
    return evaluateTarget(send, "document.activeElement", "focused element");
  }
  throw new Error("No element target specified");
}

export async function resolveTarget(
  send,
  args,
  {
    focused = false,
    waitTimeoutMs = DEFAULT_WAIT_TIMEOUT_MS,
    waitIntervalMs = DEFAULT_WAIT_INTERVAL_MS,
  } = {},
) {
  if (focused && !args.ref && !(args.role && args.name)) {
    return resolveTargetOnce(send, args, { focused });
  }
  const deadline = Date.now() + waitTimeoutMs;
  while (true) {
    try {
      return await resolveTargetOnce(send, args, { focused });
    } catch (error) {
      if (!(error instanceof TargetNotFoundError)) throw error;
      const remainingMs = deadline - Date.now();
      if (remainingMs <= 0) throw error;
      await sleep(Math.min(waitIntervalMs, remainingMs));
    }
  }
}

export async function releaseTarget(send, objectId) {
  if (!objectId) return;
  await send("Runtime.releaseObject", { objectId }).catch(() => {});
}
