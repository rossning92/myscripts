import { withActivePage } from "../browser-core.js";

const INTERACTIVE_ROLES = new Set([
  "button",
  "link",
  "checkbox",
  "combobox",
  "listbox",
  "menuitem",
  "menuitemcheckbox",
  "menuitemradio",
  "option",
  "radio",
  "searchbox",
  "slider",
  "spinbutton",
  "switch",
  "textbox",
  "treeitem",
  "tab",
  "ColorWell",
  "DisclosureTriangle",
]);

const STRUCTURAL_ROLES = new Set([
  "banner",
  "complementary",
  "contentinfo",
  "form",
  "main",
  "navigation",
  "region",
  "search",
  "menu",
  "menubar",
  "tree",
  "scrollbar",
]);

function isInteractive(node) {
  return INTERACTIVE_ROLES.has(node.role) || node.focusable;
}

export function formatSnapshot(node, state = { index: 0 }, depth = 0) {
  const indent = "  ".repeat(depth);
  let line = indent;

  const interactive = isInteractive(node);
  if (interactive) {
    line += `[@e${state.index++}] `;
  } else {
    line += "- ";
  }

  line += node.role;

  if (node.name) {
    line += ` "${node.name}"`;
  }

  const attributes = [];
  const is = (val, expected) => String(val) === String(expected);

  if (is(node.focused, true)) attributes.push("active");
  if (node.level) attributes.push(`level=${node.level}`);
  if (is(node.disabled, true)) attributes.push("disabled");
  if (is(node.expanded, true)) attributes.push("expanded");
  if (is(node.expanded, false)) attributes.push("collapsed");
  if (is(node.checked, true)) attributes.push("checked");
  if (is(node.checked, false)) attributes.push("unchecked");
  if (is(node.selected, true)) attributes.push("selected");
  if (is(node.pressed, true)) attributes.push("pressed");
  if (is(node.readonly, true)) attributes.push("readonly");
  if (is(node.required, true)) attributes.push("required");

  if (attributes.length > 0) {
    line += " [" + attributes.join("] [") + "]";
  }

  const value = node.value !== undefined ? node.value : node.valuetext;
  if (value !== undefined && value !== "" && value !== null) {
    line += `: ${value}`;
  }

  let result = line + "\n";
  if (node.children) {
    for (const child of node.children) {
      if (
        interactive &&
        child.role === "StaticText" &&
        child.name === node.name &&
        (!child.children || child.children.length === 0)
      ) {
        continue;
      }
      result += formatSnapshot(child, state, depth + 1);
    }
  }
  return result;
}

export async function snapshot() {
  return withActivePage(async (page) => {
    // Clear old refs
    await page.evaluate(() => {
      document.querySelectorAll("[data-agent-ref]").forEach((el) =>
        el.removeAttribute("data-agent-ref"),
      );
    });

    const title = await page.title();
    const url = await page.url();
    let output = `Title: ${title}\nURL: ${url}\n\n`;

    const client = await page.createCDPSession();
    let snapshotData;
    try {
      // Pierce shadow DOMs so DOM.resolveNode works for shadow DOM elements
      await client.send("DOM.getDocument", { depth: -1, pierce: true });
      const { nodes } = await client.send("Accessibility.getFullAXTree");

      const nodeMap = new Map();
      for (const node of nodes) {
        nodeMap.set(node.nodeId, node);
      }

      function buildTree(nodeId) {
        const node = nodeMap.get(nodeId);
        if (!node) return null;

        const role = node.role?.value || "Unknown";
        const name = node.name?.value || "";
        const value = node.value?.value || node.value?.valuetext || "";

        const props = {};
        if (node.properties) {
          for (const p of node.properties) {
            props[p.name.toLowerCase()] = p.value.value;
          }
        }

        if (node.ignored || props.hidden) {
          const children = [];
          if (node.childIds) {
            for (const childId of node.childIds) {
              const child = buildTree(childId);
              if (Array.isArray(child)) {
                children.push(...child);
              } else if (child) {
                children.push(child);
              }
            }
          }
          return children.length > 0 ? children : null;
        }

        const children = [];
        if (node.childIds) {
          for (const childId of node.childIds) {
            const child = buildTree(childId);
            if (Array.isArray(child)) {
              children.push(...child);
            } else if (child) {
              children.push(child);
            }
          }
        }

        const isInteresting =
          props.focusable ||
          INTERACTIVE_ROLES.has(role) ||
          STRUCTURAL_ROLES.has(role) ||
          (role === "heading" && name) ||
          (role === "StaticText" && (name || value)) ||
          role === "RootWebArea" ||
          role === "WebArea";

        if (isInteresting || children.length > 0) {
          return {
            role,
            name,
            value,
            backendDOMNodeId: node.backendDOMNodeId,
            children: children.length > 0 ? children : undefined,
            ...props,
          };
        }
        return null;
      }

      const rootNode = nodes.find((n) => !n.parentId);
      const built = buildTree(rootNode?.nodeId);
      snapshotData = Array.isArray(built) ? built[0] : built;

      if (snapshotData) {
        // Assign refs and set attributes in DOM
        const assignRefs = async (node, state) => {
          if (isInteractive(node)) {
            const ref = `e${state.index++}`;
            if (node.backendDOMNodeId) {
              try {
                const { object } = await client.send("DOM.resolveNode", {
                  backendNodeId: node.backendDOMNodeId,
                });
                await client.send("Runtime.callFunctionOn", {
                  objectId: object.objectId,
                  functionDeclaration: `function(r) { this.setAttribute('data-agent-ref', r); }`,
                  arguments: [{ value: ref }],
                });
              } catch (e) {
                // Ignore resolve errors
              }
            }
          }
          if (node.children) {
            for (const child of node.children) {
              await assignRefs(child, state);
            }
          }
        };
        await assignRefs(snapshotData, { index: 0 });
      }
    } finally {
      await client.detach();
    }

    if (!snapshotData) return output + "(No accessibility data)";

    output += formatSnapshot(snapshotData).trim();
    return output;
  });
}

