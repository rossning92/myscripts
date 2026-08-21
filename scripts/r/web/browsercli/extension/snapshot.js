export const INTERACTIVE_ROLES = new Set([
  "button", "link", "checkbox", "combobox", "listbox", "menuitem",
  "menuitemcheckbox", "menuitemradio", "option", "radio", "searchbox",
  "slider", "spinbutton", "switch", "textbox", "treeitem", "tab",
  "ColorWell", "DisclosureTriangle",
]);

const STRUCTURAL_ROLES = new Set([
  "banner", "complementary", "contentinfo", "form", "main", "navigation",
  "region", "search", "menu", "menubar", "tree", "scrollbar",
]);

export function isInteractive(node) {
  return INTERACTIVE_ROLES.has(node.role) || node.focusable;
}

export function buildSnapshotTree(nodes) {
  const nodeMap = new Map(nodes.map((node) => [node.nodeId, node]));

  function buildTree(nodeId) {
    const node = nodeMap.get(nodeId);
    if (!node) return null;

    const role = node.role?.value || "Unknown";
    const name = node.name?.value || "";
    const value = node.value?.value || node.value?.valuetext || "";
    const props = {};
    for (const property of node.properties || []) {
      props[property.name.toLowerCase()] = property.value.value;
    }

    const children = [];
    for (const childId of node.childIds || []) {
      const child = buildTree(childId);
      if (Array.isArray(child)) children.push(...child);
      else if (child) children.push(child);
    }

    if (node.ignored || props.hidden) return children.length ? children : null;

    const interesting =
      props.focusable || INTERACTIVE_ROLES.has(role) ||
      STRUCTURAL_ROLES.has(role) || (role === "heading" && name) ||
      (role === "StaticText" && (name || value)) ||
      role === "RootWebArea" || role === "WebArea";
    if (!interesting && !children.length) return null;

    return {
      role, name, value, backendDOMNodeId: node.backendDOMNodeId,
      children: children.length ? children : undefined,
      ...props,
    };
  }

  const built = buildTree(nodes.find((node) => !node.parentId)?.nodeId);
  return Array.isArray(built) ? built[0] : built;
}

export function formatSnapshot(node, state = { index: 0 }, depth = 0) {
  let line = `${"  ".repeat(depth)}- ${node.role}`;
  const interactive = isInteractive(node);
  const ref = interactive ? `@e${state.index++}` : null;
  if (node.name) line += ` "${node.name}"`;

  const attributes = [];
  const is = (value, expected) => String(value) === String(expected);
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
  if (attributes.length) line += ` [${attributes.join("] [")}]`;

  const value = node.value !== undefined ? node.value : node.valuetext;
  if (value !== undefined && value !== "" && value !== null) line += `: ${value}`;
  if (ref) line += ` [ref=${ref}]`;

  let result = `${line}\n`;
  for (const child of node.children || []) {
    if (interactive && child.role === "StaticText" && child.name === node.name &&
        (!child.children || child.children.length === 0)) continue;
    result += formatSnapshot(child, state, depth + 1);
  }
  return result;
}
