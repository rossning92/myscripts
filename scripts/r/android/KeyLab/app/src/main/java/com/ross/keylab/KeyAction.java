package com.ross.keylab;

import android.view.KeyEvent;

import java.util.Locale;

/** A mapping target: literal text, a special key, or a modifier/key combination. */
final class KeyAction {
    final String text;
    final int keyCode;
    final int modifiers;

    private KeyAction(String text, int keyCode, int modifiers) {
        this.text = text;
        this.keyCode = keyCode;
        this.modifiers = modifiers;
    }

    static KeyAction parse(String raw) {
        String value = raw.trim();
        if (value.isEmpty()) return null;
        if (value.regionMatches(true, 0, "text:", 0, 5)) return new KeyAction(value.substring(5), 0, 0);

        String[] pieces = value.split("\\+");
        int modifiers = 0;
        for (int i = 0; i < pieces.length - 1; i++) {
            switch (pieces[i].trim().toLowerCase(Locale.ROOT)) {
                case "ctrl": case "control": modifiers |= KeyEvent.META_CTRL_ON; break;
                case "alt": modifiers |= KeyEvent.META_ALT_ON; break;
                case "shift": modifiers |= KeyEvent.META_SHIFT_ON; break;
                case "meta": case "win": modifiers |= KeyEvent.META_META_ON; break;
                default: return null;
            }
        }
        int code = Mapping.keyCode(pieces[pieces.length - 1]);
        if (code != KeyEvent.KEYCODE_UNKNOWN && (pieces.length > 1 || isNamedKey(value)))
            return new KeyAction(null, code, modifiers);
        // Plain values are literal text. Prefix ambiguous words with text:, e.g. text:Home.
        return pieces.length == 1 ? new KeyAction(value, 0, 0) : null;
    }

    static String validate(String raw) {
        return parse(raw) == null
                ? "unknown action (try Left, Ctrl+A, or text:your text)" : null;
    }

    private static boolean isNamedKey(String value) {
        String v = value.trim().toUpperCase(Locale.ROOT).replace(" ", "").replace("_", "");
        return v.equals("ESC") || v.equals("ESCAPE") || v.equals("ENTER") || v.equals("TAB")
                || v.equals("SPACE") || v.equals("BACKSPACE") || v.equals("DELETE")
                || v.equals("UP") || v.equals("DOWN") || v.equals("LEFT") || v.equals("RIGHT")
                || v.equals("HOME") || v.equals("END") || v.equals("PAGEUP") || v.equals("PAGEDOWN")
                || v.matches("F([1-9]|1[0-2])") || v.startsWith("KEYCODE");
    }
}
