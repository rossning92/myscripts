import { buildSnapshotTree, formatSnapshot, isInteractive } from "./snapshot.js";

async function assignRefs(send, node, state) {
  if (isInteractive(node)) {
    const ref = `e${state.index++}`;
    if (node.backendDOMNodeId) {
      try {
        const { object } = await send("DOM.resolveNode", {
          backendNodeId: node.backendDOMNodeId,
        });
        await send("Runtime.callFunctionOn", {
          objectId: object.objectId,
          functionDeclaration:
            "function(r) { this.setAttribute('data-agent-ref', r); }",
          arguments: [{ value: ref }],
        });
      } catch {
        // Some accessibility nodes do not resolve to live DOM elements.
      }
    }
  }
  for (const child of node.children || []) {
    await assignRefs(send, child, state);
  }
}

export async function collectSnapshot(send, { title = "", url = "" } = {}) {
  await send("Runtime.evaluate", {
    expression:
      "document.querySelectorAll('[data-agent-ref]').forEach(el => el.removeAttribute('data-agent-ref'))",
  });
  await send("DOM.getDocument", { depth: -1, pierce: true });
  const { nodes } = await send("Accessibility.getFullAXTree");
  const tree = buildSnapshotTree(nodes);
  if (tree) await assignRefs(send, tree, { index: 0 });

  let output = `Title: ${title}\nURL: ${url}\n\n`;
  output += tree ? formatSnapshot(tree).trim() : "(No accessibility data)";
  return output;
}
