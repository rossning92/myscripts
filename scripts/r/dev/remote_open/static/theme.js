(function () {
    var KEY = "ropen-theme";

    function apply(t) {
        document.documentElement.dataset.theme = t;
        var hl = document.querySelector('link[href*="highlight.js/styles/"]');
        if (hl) hl.href = hl.href.replace(/github(-dark)?\.min\.css$/, hljsStyle());
    }

    function hljsStyle() {
        return document.documentElement.dataset.theme === "light" ? "github.min.css" : "github-dark.min.css";
    }

    function toggle() {
        var t = document.documentElement.dataset.theme === "light" ? "dark" : "light";
        localStorage.setItem(KEY, t);
        apply(t);
    }

    var ICONS = {
        theme: '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/>',
        link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
        copy: '<rect x="8" y="8" width="14" height="14" rx="2"/><path d="M4 16a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2"/>',
        download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
        note: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
        check: '<path d="M20 6 9 17l-5-5"/>',
        x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    };

    window.icon = function (name) {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
            'stroke-linecap="round" stroke-linejoin="round">' + ICONS[name] + "</svg>";
    };

    window.Theme = { toggle: toggle, hljsStyle: hljsStyle };
    apply(localStorage.getItem(KEY) || "dark");

    document.addEventListener("DOMContentLoaded", function () {
        var b = document.getElementById("themebtn");
        b.innerHTML = icon("theme");
        b.title = "Toggle theme (" + (/Mac/i.test(navigator.platform || "") ? "⌥" : "Alt+") + "T)";
        b.onclick = toggle;
    });
    window.addEventListener("storage", function (e) {
        if (e.key === KEY) apply(e.newValue || "dark");
    });
    document.addEventListener("keydown", function (e) {
        if (e.altKey && !e.ctrlKey && !e.metaKey && e.code === "KeyT") {
            e.preventDefault();
            toggle();
        }
    });
})();
