import { buildSnapshotTree, formatSnapshot, isInteractive } from "./snapshot.js";

async function getFrameLabel(send, frame) {
  try {
    const { backendNodeId } = await send("DOM.getFrameOwner", {
      frameId: frame.id,
    });
    const { nodes } = await send("Accessibility.getPartialAXTree", {
      backendNodeId,
      fetchRelatives: false,
    });
    return nodes[0]?.name?.value || frame.name || frame.url || "about:blank";
  } catch {
    return frame.name || frame.url || "about:blank";
  }
}

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
  const { frameTree } = await send("Page.getFrameTree");
  const frames = [];
  const visitFrames = (item, depth = 0) => {
    if (!item?.frame) return;
    frames.push({ ...item.frame, depth });
    for (const child of item.childFrames || []) visitFrames(child, depth + 1);
  };
  visitFrames(frameTree);

  const state = { index: 0 };
  const snapshots = [];
  for (const frame of frames.length ? frames : [{ id: undefined, url }]) {
    const { nodes = [] } = await send("Accessibility.getFullAXTree", {
      ...(frame.id ? { frameId: frame.id } : {}),
    });
    const tree = buildSnapshotTree(nodes);
    if (tree) await assignRefs(send, tree, state);
    snapshots.push({ frame, tree, label: await getFrameLabel(send, frame) });
  }
  for (const context of (send.contexts || []).slice(1)) {
    await context.send("DOM.getDocument", { depth: -1, pierce: true });
    const { nodes = [] } = await context.send("Accessibility.getFullAXTree");
    const tree = buildSnapshotTree(nodes);
    if (tree) await assignRefs(context.send, tree, state);
    snapshots.push({ frame: { url: context.url }, tree });
  }

  let output = `Title: ${title}\nURL: ${url}\n\n`;
  const formatState = { index: 0 };
  output += snapshots[0]?.tree
    ? formatSnapshot(snapshots[0].tree, formatState).trim()
    : "(No accessibility data)";
  for (const { frame, tree, label } of snapshots.slice(1)) {
    const indent = "  ".repeat(frame.depth ?? 1);
    output += `\n${indent}- iframe "${label || frame.url || "about:blank"}"\n`;
    const content = tree
      ? formatSnapshot(tree, formatState).trim()
      : "(No accessibility data)";
    output += content.replace(/^/gm, `${indent}  `);
  }
  return output;
}
