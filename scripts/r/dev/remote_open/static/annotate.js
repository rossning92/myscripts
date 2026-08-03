// Text annotation layer for the ropen viewer.
// Select text in a markdown/plain-text view to attach a note; click an
// existing highlight to edit or delete it; a Copy button dumps every note
// as a ready-to-paste LLM edit instruction.
//
// Notes persist per-file in localStorage and are re-applied by searching for
// the quoted text after each re-render, so they survive the viewer's reloads.
(function () {
    var STYLE = [
        "mark.ropen-annot{background:#5a4a00;color:inherit;border-radius:2px;",
        "box-shadow:0 0 0 1px #b89000 inset;cursor:pointer;padding:0 1px;}",
        "#annot-copy{display:none;padding:5px 8px;color:#888;background:#2a2a2a;",
        "border:1px solid #333;border-radius:4px;cursor:pointer;font:12px/1 sans-serif;}",
        "#annot-copy:hover{background:#383838;color:#e0e0e0;}",
        "#annot-copy.ok{color:#4ade80;border-color:#4ade80;}",
        "#annot-popup{position:fixed;z-index:21;display:none;width:280px;padding:10px;",
        "background:#252525;border:1px solid #444;border-radius:6px;",
        "box-shadow:0 4px 16px rgba(0,0,0,.6);}",
        "#annot-popup input{width:100%;background:#1a1a1a;color:#e0e0e0;",
        "border:1px solid #444;border-radius:4px;padding:6px;",
        "font:13px/1.4 sans-serif;box-sizing:border-box;}",
        "#annot-popup .row{display:flex;gap:6px;margin-top:8px;justify-content:flex-end;}",
        "#annot-popup button{padding:5px 12px;border-radius:4px;border:1px solid #444;",
        "background:#333;color:#e0e0e0;cursor:pointer;font:12px/1 sans-serif;}",
        "#annot-popup button.save{background:#b89000;color:#1a1a1a;border-color:#b89000;",
        "font-weight:600;}",
        "#annot-popup button.del{margin-right:auto;background:#4a1f1f;color:#ff9b9b;",
        "border-color:#5a2a2a;}",
        ".annot-key{opacity:.6;font-size:11px;margin-left:4px;}",
    ].join("");

    function injectStyle() {
        if (document.getElementById("annot-style")) return;
        var s = document.createElement("style");
        s.id = "annot-style";
        s.textContent = STYLE;
        document.head.appendChild(s);
    }

    var isMac = /Mac/i.test(navigator.platform || "");
    var ALT = isMac ? "⌥" : "Alt+";

    var container = null;
    var filePath = null;
    var annots = [];
    var editingId = null;
    var editingNew = false; // true while the edited annotation is unsaved (drives discard-on-cancel)
    var selectionTimer = null;
    var els = {};

    function storageKey() {
        return "ropen_annot:" + filePath;
    }

    function load() {
        try {
            annots = JSON.parse(localStorage.getItem(storageKey())) || [];
        } catch (e) {
            annots = [];
        }
    }

    function save() {
        try {
            if (annots.length) {
                localStorage.setItem(storageKey(), JSON.stringify(annots));
            } else {
                localStorage.removeItem(storageKey());
            }
        } catch (e) {}
    }

    function newId() {
        return "a" + Date.now() + Math.floor(Math.random() * 1000);
    }

    function findAnnot(id) {
        return annots.filter(function (x) { return x.id === id; })[0];
    }

    function unwrapAll() {
        container.querySelectorAll("mark.ropen-annot").forEach(function (m) {
            var p = m.parentNode;
            while (m.firstChild) p.insertBefore(m.firstChild, m);
            p.removeChild(m);
            p.normalize();
        });
    }

    function collectTextNodes() {
        var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
            acceptNode: function (n) {
                if (n.parentElement && n.parentElement.closest("mark.ropen-annot")) {
                    return NodeFilter.FILTER_REJECT;
                }
                return n.nodeValue ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
            },
        });
        var nodes = [], full = "", n;
        while ((n = walker.nextNode())) {
            nodes.push({ node: n, start: full.length });
            full += n.nodeValue;
        }
        return { nodes: nodes, full: full };
    }

    // idx/end are offsets into the concatenated text of `nodes`; a selection can
    // span several nodes, so wrap each node's overlapping slice separately.
    // Keep line-break characters outside the inline marks. In a pre-wrap view,
    // putting newlines inside an inline element can change line-box layout and
    // make a multiline annotation appear to add blank lines.
    function wrapSpan(nodes, idx, end, a) {
        for (var i = 0; i < nodes.length; i++) {
            var node = nodes[i].node;
            var ns = nodes[i].start;
            var s = Math.max(idx, ns);
            var e = Math.min(end, ns + node.nodeValue.length);
            if (s >= e) continue;

            var from = s - ns;
            var to = e - ns;
            var parts = [];
            var re = /[^\r\n]+/g;
            var match;
            while ((match = re.exec(node.nodeValue))) {
                var partStart = Math.max(from, match.index);
                var partEnd = Math.min(to, match.index + match[0].length);
                if (partStart < partEnd) parts.push({ start: partStart, end: partEnd });
            }

            // Work backwards so splitting the text node does not invalidate the
            // offsets of portions that still need to be wrapped.
            for (var j = parts.length - 1; j >= 0; j--) {
                var r = document.createRange();
                r.setStart(node, parts[j].start);
                r.setEnd(node, parts[j].end);
                var m = document.createElement("mark");
                m.className = "ropen-annot";
                m.dataset.id = a.id;
                m.title = a.note || "(no note)";
                try {
                    r.surroundContents(m);
                } catch (err) {}
            }
        }
    }

    // Find `quote` in `full` ignoring whitespace differences (a selection that
    // crosses block boundaries carries newlines that the DOM text lacks).
    // Returns [start,end) offsets into `full` spanning the matched region.
    function locate(full, quote) {
        var stripped = "", map = [];
        for (var i = 0; i < full.length; i++) {
            if (!/\s/.test(full[i])) {
                map.push(i);
                stripped += full[i];
            }
        }
        var needle = quote.replace(/\s+/g, "");
        if (!needle) return null;
        var at = stripped.indexOf(needle);
        if (at < 0) return null;
        return { start: map[at], end: map[at + needle.length - 1] + 1 };
    }

    // Drop notes whose quoted text no longer exists in the file (it was edited
    // away). Runs on (re)load against the freshly rendered content, so a live
    // edit picked up by the file watcher clears its now-orphaned notes. No marks
    // exist yet at this point, so one text scan covers every annotation.
    function pruneStale() {
        if (!container) return;
        var full = collectTextNodes().full;
        var before = annots.length;
        annots = annots.filter(function (a) {
            return a.id === editingId || locate(full, a.quote);
        });
        if (annots.length !== before) save();
    }

    function applyHighlights() {
        if (!container) return;
        unwrapAll();
        annots.forEach(function (a) {
            // Re-scan per annotation so already-wrapped text is skipped (the
            // walker rejects nodes inside existing marks).
            var t = collectTextNodes();
            var m = locate(t.full, a.quote);
            if (m) wrapSpan(t.nodes, m.start, m.end, a);
        });
        container.querySelectorAll("mark.ropen-annot").forEach(function (m) {
            m.onclick = function (e) {
                e.stopPropagation();
                var a = findAnnot(m.dataset.id);
                if (a) openPopup(a, m.getBoundingClientRect(), false);
            };
        });
    }

    function currentSelection() {
        var sel = window.getSelection();
        if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
        var text = sel.toString();
        if (!text.trim()) return null;
        var range = sel.getRangeAt(0);
        var anc = range.commonAncestorContainer;
        var node = anc.nodeType === 1 ? anc : anc.parentElement;
        if (!node || !container.contains(node)) return null;
        return { text: text, rect: lastClientRect(range) };
    }

    // A range/inline element can have one client rect per rendered line. Anchor
    // the dialog to the final fragment instead of the bounding box (or first
    // generated mark), so a multiline selection opens beside its last line.
    function lastClientRect(target) {
        var rects = target.getClientRects();
        for (var i = rects.length - 1; i >= 0; i--) {
            if (rects[i].width || rects[i].height) return rects[i];
        }
        return target.getBoundingClientRect();
    }

    function onSelectionDone() {
        if (!container || els.popup.style.display === "block") return;
        var sel = currentSelection();
        if (!sel) return;
        // Create the annotation up front so the text stays visibly highlighted
        // while the dialog is open (focusing the input hides the native selection).
        var a = { id: newId(), quote: sel.text, note: "" };
        annots.push(a);
        window.getSelection().removeAllRanges();
        applyHighlights();
        var marks = container.querySelectorAll('mark.ropen-annot[data-id="' + a.id + '"]');
        var mark = marks.length ? marks[marks.length - 1] : null;
        openPopup(a, mark ? lastClientRect(mark) : sel.rect, true);
    }

    function openPopup(a, rect, isNew) {
        editingId = a.id;
        editingNew = isNew;
        els.input.value = a.note || "";
        els.del.style.display = isNew ? "none" : "block";
        els.popup.style.display = "block";

        rect = rect || { bottom: 80, top: 80, left: window.innerWidth / 2 - 140 };
        var top = rect.bottom + 6;
        if (top + 180 > window.innerHeight) top = Math.max(4, rect.top - 186);
        els.popup.style.top = top + "px";
        els.popup.style.left = Math.max(4, Math.min(rect.left, window.innerWidth - 292)) + "px";
        els.input.focus();
    }

    function closePopup() {
        els.popup.style.display = "none";
        editingId = null;
        editingNew = false;
    }

    function commitPopup() {
        findAnnot(editingId).note = els.input.value.trim();
        save();
        closePopup();
        refresh();
    }

    function cancelPopup() {
        if (editingNew) removeCurrent();
        else closePopup();
    }

    function removeCurrent() {
        annots = annots.filter(function (x) { return x.id !== editingId; });
        save();
        closePopup();
        refresh();
    }

    function buildCopyText() {
        var lines = ["Edits for `" + filePath + "`:", ""];
        annots.forEach(function (a, i) {
            var quote = a.quote.replace(/\s+/g, " ").trim();
            lines.push(i + 1 + '. "' + quote + '" -> ' + (a.note || "(no note)"));
        });
        return lines.join("\n") + "\n";
    }

    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise(function (res, rej) {
            var ta = document.createElement("textarea");
            ta.value = text;
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            var ok = false;
            try { ok = document.execCommand("copy"); } catch (e) {}
            document.body.removeChild(ta);
            ok ? res() : rej();
        });
    }

    function copyAll() {
        if (!annots.length) return;
        copyText(buildCopyText()).then(function () {
            els.copy.classList.add("ok");
            setTimeout(function () { els.copy.classList.remove("ok"); }, 1200);
        });
    }

    function refresh() {
        applyHighlights();
        els.copy.style.display = annots.length ? "block" : "none";
        els.copy.innerHTML =
            "Copy annotations (" + annots.length + ')<span class="annot-key">' + ALT + "N</span>";
    }

    function buildUi() {
        if (els.built) return;
        injectStyle();

        var copy = document.createElement("button");
        copy.id = "annot-copy";
        copy.title = "Copy annotations as LLM instructions (" + ALT + "N)";
        (document.getElementById("toolbar") || document.body).appendChild(copy);

        var popup = document.createElement("div");
        popup.id = "annot-popup";
        popup.innerHTML =
            '<input type="text" placeholder="Your note / requested change...">' +
            '<div class="row">' +
            '<button class="del">Delete<span class="annot-key">' + ALT + "D</span></button>" +
            '<button class="cancel">Cancel<span class="annot-key">Esc</span></button>' +
            '<button class="save">Save<span class="annot-key">⏎</span></button>' +
            "</div>";
        document.body.appendChild(popup);

        els = {
            built: true,
            copy: copy,
            popup: popup,
            input: popup.querySelector("input"),
            save: popup.querySelector(".save"),
            cancel: popup.querySelector(".cancel"),
            del: popup.querySelector(".del"),
        };

        copy.onclick = copyAll;
        els.save.onclick = commitPopup;
        els.cancel.onclick = cancelPopup;
        els.del.onclick = removeCurrent;

        // Selection handles emit intermediate ranges while they are being adjusted.
        document.addEventListener("selectionchange", function () {
            clearTimeout(selectionTimer);
            selectionTimer = setTimeout(onSelectionDone, 1000);
        });
        // Keep clicks on the dialog buttons from stealing focus from the input,
        // so they don't trip the blur-to-cancel below.
        popup.addEventListener("mousedown", function (e) {
            if (e.target !== els.input) e.preventDefault();
        });
        // The input losing focus while the dialog is open means the user pressed
        // Esc (browsers swallow that keydown to blur the field) or clicked away -
        // both cancel. This is the only reliable signal for that first Esc.
        els.input.addEventListener("blur", function () {
            if (els.popup.style.display === "block") cancelPopup();
        });
        // Dialog keys, handled in the capture phase (before the browser acts on
        // the focused input). Note: the first Esc's keydown gets swallowed by
        // the browser to blur the input, so Esc is primarily handled by the blur
        // above; this handler covers Enter, Alt+D, and Esc when unfocused.
        document.addEventListener("keydown", function (e) {
            if (els.popup.style.display !== "block") return;
            var handled = true;
            if (e.key === "Enter") commitPopup();
            else if (e.key === "Escape") cancelPopup();
            else if (e.altKey && e.code === "KeyD" && !editingNew) removeCurrent();
            else handled = false;
            if (handled) {
                e.preventDefault();
                e.stopPropagation();
            }
        }, true);
        document.addEventListener("keydown", function (e) {
            if (!e.altKey || e.ctrlKey || e.metaKey) return;
            if (e.code === "KeyN" && container && annots.length) {
                e.preventDefault();
                copyAll();
            }
        });
    }

    window.Annotator = {
        // Bind to a content element (called on every render). Idempotent.
        enable: function (contentEl, path) {
            buildUi();
            container = contentEl;
            filePath = path;
            load();
            pruneStale();
            refresh();
        },
        // Hide UI for non-text views (images, video, pdf).
        disable: function () {
            container = null;
            if (els.built) {
                els.copy.style.display = "none";
                els.popup.style.display = "none";
            }
        },
    };
})();
