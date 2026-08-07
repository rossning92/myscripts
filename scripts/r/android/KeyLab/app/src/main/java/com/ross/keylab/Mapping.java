package com.ross.keylab;

import android.content.Context;
import android.content.SharedPreferences;
import android.view.KeyEvent;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

/** Persisted tap and hold mappings, plus the small text format used by the editor UI. */
public final class Mapping {

    static final long LONGPRESS_MS = 250;
    private static final String PREFS = "keylab_mappings";
    private static final String TAP_SPEC = "tap_spec";
    private static final String HOLD_SPEC = "hold_spec";

    static final String DEFAULT_HOLD_SPEC =
            "A = Ctrl+A\n" +
            "Q = Esc\nH = Home\nE = End\nU = PageUp\nD = PageDown\n" +
            "I = Up\nJ = Left\nK = Down\nL = Right\n" +
            "1 = !\n2 = @\n3 = #\n4 = $\n5 = %\n6 = ^\n7 = &\n8 = *\n9 = (\n0 = )\n" +
            "C = ¢\nY = ¥\nMinus = _\nW = |\nR = ®\nT = ™";

    final Map<Integer, KeyAction> tapActions;
    final Map<Integer, KeyAction> holdActions;

    private Mapping(Map<Integer, KeyAction> taps, Map<Integer, KeyAction> holds) {
        tapActions = taps;
        holdActions = holds;
    }

    static Mapping load(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        return new Mapping(parseSpec(prefs.getString(TAP_SPEC, "")),
                parseSpec(prefs.getString(HOLD_SPEC, DEFAULT_HOLD_SPEC)));
    }

    static String getTapSpec(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(TAP_SPEC, "");
    }

    static String getHoldSpec(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(HOLD_SPEC, DEFAULT_HOLD_SPEC);
    }

    static void save(Context context, String taps, String holds) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString(TAP_SPEC, taps.trim())
                .putString(HOLD_SPEC, holds.trim())
                .apply();
    }

    /** Validates a spec and returns null when valid, otherwise a UI-friendly error. */
    static String validate(String spec) {
        String[] lines = spec.split("\\r?\\n", -1);
        for (int i = 0; i < lines.length; i++) {
            String line = lines[i].trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            int equals = line.indexOf('=');
            if (equals <= 0 || equals == line.length() - 1) return "Line " + (i + 1) + ": use Key = Action";
            if (keyCode(line.substring(0, equals)) == KeyEvent.KEYCODE_UNKNOWN)
                return "Line " + (i + 1) + ": unknown input key";
            String error = KeyAction.validate(line.substring(equals + 1));
            if (error != null) return "Line " + (i + 1) + ": " + error;
        }
        return null;
    }

    private static Map<Integer, KeyAction> parseSpec(String spec) {
        Map<Integer, KeyAction> result = new LinkedHashMap<>();
        for (String raw : spec.split("\\r?\\n")) {
            String line = raw.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            int equals = line.indexOf('=');
            if (equals <= 0 || equals == line.length() - 1) continue;
            int code = keyCode(line.substring(0, equals));
            KeyAction action = KeyAction.parse(line.substring(equals + 1));
            if (code != KeyEvent.KEYCODE_UNKNOWN && action != null) result.put(code, action);
        }
        return result;
    }

    static int keyCode(String name) {
        String value = name.trim().toUpperCase(Locale.ROOT).replace(" ", "_").replace("-", "_");
        switch (value) {
            case "ESC": value = "ESCAPE"; break;
            case "UP": value = "DPAD_UP"; break;
            case "DOWN": value = "DPAD_DOWN"; break;
            case "LEFT": value = "DPAD_LEFT"; break;
            case "RIGHT": value = "DPAD_RIGHT"; break;
            case "HOME": value = "MOVE_HOME"; break;
            case "END": value = "MOVE_END"; break;
            case "PAGEUP": value = "PAGE_UP"; break;
            case "PAGEDOWN": value = "PAGE_DOWN"; break;
            case "MINUS": value = "MINUS"; break;
            case "SPACE": value = "SPACE"; break;
        }
        return KeyEvent.keyCodeFromString(value.startsWith("KEYCODE_") ? value : "KEYCODE_" + value);
    }
}
