package com.ross.keylab;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.InputMethod;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.accessibility.AccessibilityEvent;

import java.util.Map;

/**
 * Intercepts hardware keyboard events for tap-vs-hold gestures. A tracked key
 * that is tapped types its normal character; held past its threshold it runs a
 * hold action instead - typing a mapped symbol, or (for Space) launching the
 * browser.
 *
 * The normal character is deliberately deferred until key-up (or the hold fires),
 * which is the only way to tell a tap from a hold.
 *
 * Forcing landscape while a keyboard is attached is a separate concern, delegated
 * to {@link KeyboardOrientationController}.
 */
public class LongPressAccessibilityService extends AccessibilityService {

    private static LongPressAccessibilityService instance;

    public static LongPressAccessibilityService getInstance() {
        return instance;
    }

    // How long Space must be held to fire the global hotkey action.
    private static final long SPACE_HOLD_MS = 600;

    private static final String TERMUX_PACKAGE = "com.termux";

    private final Handler handler = new Handler(Looper.getMainLooper());

    private final Map<Character, String> symbolByBase = Mapping.parse();

    // State for the key currently being tracked for tap-vs-hold.
    private int pendingKeyCode = -1;
    private String pendingNormal;   // char to emit on a tap
    private boolean longPressFired;
    private Runnable longPressRunnable;

    private KeyboardOrientationController orientation;
    private KeyguardManager keyguardManager;

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
        keyguardManager = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
        orientation = new KeyboardOrientationController(this);
        orientation.start(handler);
    }

    @Override
    public boolean onKeyEvent(KeyEvent event) {
        // On the lock screen our commit() can't reach the secure PIN field, so
        // consuming keys would just swallow them. Let the system handle them.
        if (keyguardManager != null && keyguardManager.isKeyguardLocked()) {
            return passThrough();
        }

        int meta = event.getMetaState();

        android.util.Log.d("KeyLab", "onKeyEvent code=" + event.getKeyCode()
                + " action=" + event.getAction() + " meta=" + meta);

        // Win+T launches Termux, overriding the system default. Fire once on key-down.
        if (event.getKeyCode() == KeyEvent.KEYCODE_T && (meta & KeyEvent.META_META_ON) != 0) {
            android.util.Log.d("KeyLab", "Win+T matched, action=" + event.getAction());
            if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
                launchApp(TERMUX_PACKAGE);
            }
            return true;
        }

        // Never intercept modifier combos (Ctrl/Alt/Meta) so shortcuts keep working.
        if ((meta & (KeyEvent.META_CTRL_ON | KeyEvent.META_ALT_ON | KeyEvent.META_META_ON)) != 0) {
            return passThrough();
        }

        // Resolve what this key does when tracked: the char to type on a tap, the
        // action to run on a hold, and the hold threshold. Untracked keys pass through.
        String normalOnTap;
        Runnable holdAction;
        long holdMs;

        if (event.getKeyCode() == KeyEvent.KEYCODE_SPACE) {
            normalOnTap = " ";
            holdAction = this::launchBrowser;
            holdMs = SPACE_HOLD_MS;
        } else {
            int base = event.getUnicodeChar(0);
            if (base == 0) return passThrough(); // non-printable key (Enter, arrows, ...)
            String symbol = symbolByBase.get(Character.toLowerCase((char) base));
            if (symbol == null) return passThrough(); // unmapped -> normal behavior
            int normal = event.getUnicodeChar(meta); // respect Shift/CapsLock
            normalOnTap = normal == 0 ? null : new String(Character.toChars(normal));
            holdAction = () -> commit(symbol);
            holdMs = Mapping.LONGPRESS_MS;
        }

        if (event.getAction() == KeyEvent.ACTION_DOWN) {
            // Arm on the first press; consume auto-repeats so the key can't repeat.
            if (event.getRepeatCount() == 0) {
                beginPending(event.getKeyCode(), normalOnTap, holdAction, holdMs);
            }
            return true;
        }

        if (event.getAction() == KeyEvent.ACTION_UP
                && event.getKeyCode() == pendingKeyCode) {
            if (!longPressFired) {
                cancelPending();
                commit(pendingNormal); // released before the threshold -> it was a tap
            }
            resetPending();
            return true;
        }

        return true; // tracked key, other action -> consume defensively
    }

    /**
     * Arms tap-vs-hold tracking for a key. Released early it types {@code normalOnTap};
     * held past {@code holdMs} it runs {@code holdAction} instead (type a symbol,
     * launch the browser, ...). Every event of a tracked key is consumed, so the
     * input dispatcher never generates its own character auto-repeat.
     */
    private void beginPending(int keyCode, String normalOnTap, Runnable holdAction, long holdMs) {
        flushPendingAsTap(); // a different key was still pending -> resolve it as a tap
        pendingKeyCode = keyCode;
        pendingNormal = normalOnTap;
        longPressFired = false;
        longPressRunnable = () -> {
            holdAction.run();
            longPressFired = true;
        };
        handler.postDelayed(longPressRunnable, holdMs);
    }

    // The action bound to the Space hotkey. Kept trivial on purpose - swap this
    // body (or make it configurable) to change what the hotkey does.
    private void launchBrowser() {
        try {
            startActivity(new Intent(Intent.ACTION_MAIN)
                    .addCategory(Intent.CATEGORY_APP_BROWSER)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        } catch (Exception e) {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com"))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } catch (Exception ignored) {
            }
        }
    }

    private void launchApp(String pkg) {
        Intent intent = getPackageManager().getLaunchIntentForPackage(pkg);
        android.util.Log.d("KeyLab", "launchApp " + pkg + " intent=" + intent);
        if (intent == null) return;
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            startActivity(intent);
        } catch (Exception e) {
            android.util.Log.e("KeyLab", "launchApp failed", e);
        }
    }

    private boolean passThrough() {
        // If another key interrupts a pending mapped key, emit its tap first.
        flushPendingAsTap();
        return false;
    }

    private void flushPendingAsTap() {
        if (pendingKeyCode != -1 && !longPressFired) {
            cancelPending();
            commit(pendingNormal);
        }
        resetPending();
    }

    private void cancelPending() {
        if (longPressRunnable != null) {
            handler.removeCallbacks(longPressRunnable);
            longPressRunnable = null;
        }
    }

    private void resetPending() {
        pendingKeyCode = -1;
        pendingNormal = null;
        longPressFired = false;
        longPressRunnable = null;
    }

    private void commit(String text) {
        if (text == null || text.isEmpty()) return;
        InputMethod im = getInputMethod();
        if (im == null) return;
        InputMethod.AccessibilityInputConnection ic = im.getCurrentInputConnection();
        if (ic == null) return;
        ic.commitText(text, 1, null);
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        // The foreground app changed - a portrait-locked one may have reset our lock.
        if (orientation != null) orientation.onForegroundChanged();
    }

    @Override
    public void onInterrupt() {
        cancelPending();
        resetPending();
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (orientation != null) orientation.stop();
        if (instance == this) instance = null;
    }
}
