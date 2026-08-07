package com.ross.keylab;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.InputMethod;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.accessibility.AccessibilityEvent;
import android.widget.Toast;

import java.util.HashSet;
import java.util.Set;

/**
 * Intercepts hardware keyboard events for tap-vs-hold gestures. A tracked key
 * that is tapped types its normal character; held past its threshold it runs a
 * hold action instead - typing a mapped symbol.
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

    private static final String TERMUX_PACKAGE = "com.termux";

    private final Handler handler = new Handler(Looper.getMainLooper());

    private Mapping mapping;

    // State for the key currently being tracked for tap-vs-hold.
    private int pendingKeyCode = -1;
    private Runnable pendingTapAction;
    private boolean longPressFired;
    private Runnable longPressRunnable;

    // Accessibility cannot replace a modifier in Android's input mapper. Track Right Alt and
    // rewrite each affected non-modifier key as a complete Left-Alt chord instead. Keys rewritten
    // on ACTION_DOWN are also consumed on ACTION_UP so the target never sees half of the original.
    private boolean rightAltHeld;
    private boolean rightShiftHeld;
    private final Set<Integer> rewrittenKeys = new HashSet<>();

    private KeyboardOrientationController orientation;
    private KeyguardManager keyguardManager;

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
        reloadMappings();
        keyguardManager = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
        orientation = new KeyboardOrientationController(this);
        orientation.start(handler);
    }

    /** Turn auto-landscape on/off while the service is running (called from the UI toggle). */
    public void setAutoLandscapeEnabled(boolean enabled) {
        if (orientation != null) orientation.setEnabled(enabled);
    }

    /** Reload edits immediately when the activity saves them. */
    public void reloadMappings() {
        mapping = Mapping.load(this);
    }

    private void toggleAutoLandscape() {
        if (orientation == null) return;
        boolean on = orientation.toggle();
        Toast.makeText(this, "Auto-landscape " + (on ? "on" : "off"), Toast.LENGTH_SHORT).show();
    }

    @Override
    public boolean onKeyEvent(KeyEvent event) {
        // On the lock screen our commit() can't reach the secure PIN field, so
        // consuming keys would just swallow them. Let the system handle them.
        if (keyguardManager != null && keyguardManager.isKeyguardLocked()) {
            resetPhysicalRemapState();
            return passThrough();
        }

        int meta = event.getMetaState();

        android.util.Log.d("KeyLab", "onKeyEvent code=" + event.getKeyCode()
                + " action=" + event.getAction() + " meta=" + meta);

        // These used to be provided by a bundled physical-keyboard layout. Doing them here makes
        // setup simpler, but delivery is limited to apps with an accessibility input connection.
        if (event.getKeyCode() == KeyEvent.KEYCODE_SHIFT_RIGHT) {
            rightShiftHeld = event.getAction() != KeyEvent.ACTION_UP;
            if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
                sendKey(KeyEvent.KEYCODE_ESCAPE, 0);
            }
            return true;
        }
        if (event.getKeyCode() == KeyEvent.KEYCODE_ALT_RIGHT) {
            rightAltHeld = event.getAction() != KeyEvent.ACTION_UP;
            return true;
        }

        boolean rewriteRightAlt = rightAltHeld
                || (meta & KeyEvent.META_ALT_RIGHT_ON) != 0;
        boolean stripRightShift = rightShiftHeld
                || (meta & KeyEvent.META_SHIFT_RIGHT_ON) != 0;
        if (rewriteRightAlt || stripRightShift || rewrittenKeys.contains(event.getKeyCode())) {
            if (event.getAction() == KeyEvent.ACTION_DOWN) {
                rewrittenKeys.add(event.getKeyCode());
                int rewrittenMeta = meta;
                if (rewriteRightAlt) {
                    rewrittenMeta &= ~KeyEvent.META_ALT_MASK;
                    rewrittenMeta |= KeyEvent.META_ALT_ON | KeyEvent.META_ALT_LEFT_ON;
                }
                if (stripRightShift) {
                    boolean leftShiftHeld = (meta & KeyEvent.META_SHIFT_LEFT_ON) != 0;
                    rewrittenMeta &= ~KeyEvent.META_SHIFT_MASK;
                    if (leftShiftHeld) {
                        rewrittenMeta |= KeyEvent.META_SHIFT_ON | KeyEvent.META_SHIFT_LEFT_ON;
                    }
                }
                sendKey(event.getKeyCode(), rewrittenMeta);
            } else if (event.getAction() == KeyEvent.ACTION_UP) {
                rewrittenKeys.remove(event.getKeyCode());
            }
            return true;
        }

        // Win+T launches Termux, overriding the system default. Fire once on key-down.
        if (event.getKeyCode() == KeyEvent.KEYCODE_T && (meta & KeyEvent.META_META_ON) != 0) {
            android.util.Log.d("KeyLab", "Win+T matched, action=" + event.getAction());
            if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
                launchApp(TERMUX_PACKAGE);
            }
            return true;
        }

        // Win+R toggles auto-landscape. Fire once on key-down, overriding the default.
        if (event.getKeyCode() == KeyEvent.KEYCODE_R && (meta & KeyEvent.META_META_ON) != 0) {
            if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
                toggleAutoLandscape();
            }
            return true;
        }

        // Never intercept modifier combos (Ctrl/Alt/Meta) so shortcuts keep working.
        if ((meta & (KeyEvent.META_CTRL_ON | KeyEvent.META_ALT_ON | KeyEvent.META_META_ON)) != 0) {
            return passThrough();
        }

        if (mapping == null) reloadMappings();
        KeyAction tap = mapping.tapActions.get(event.getKeyCode());
        KeyAction hold = mapping.holdActions.get(event.getKeyCode());
        if (tap == null && hold == null) return passThrough();
        if (hold == null) {
            if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
                flushPendingAsTap();
                perform(tap);
            }
            return true;
        }
        Runnable tapAction = tap == null
                ? () -> commitUnicode(event.getUnicodeChar(meta)) : () -> perform(tap);
        Runnable holdAction = () -> perform(hold);
        return handleTrackedEvent(event, tapAction, holdAction);
    }

    private boolean handleTrackedEvent(KeyEvent event, Runnable tapAction, Runnable holdAction) {
        if (event.getAction() == KeyEvent.ACTION_DOWN) {
            // Arm on the first press; consume auto-repeats so the key can't repeat.
            if (event.getRepeatCount() == 0) {
                beginPending(event.getKeyCode(), tapAction, holdAction, Mapping.LONGPRESS_MS);
            }
            return true;
        }

        if (event.getAction() == KeyEvent.ACTION_UP
                && event.getKeyCode() == pendingKeyCode) {
            if (!longPressFired) {
                cancelPending();
                pendingTapAction.run(); // released before the threshold -> it was a tap
            }
            resetPending();
            return true;
        }

        return true; // tracked key, other action -> consume defensively
    }

    /**
     * Arms tap-vs-hold tracking for a key. Released early it types {@code normalOnTap};
     * held past {@code holdMs} it runs {@code holdAction} instead (type a symbol).
     * Every event of a tracked key is consumed, so the input dispatcher never
     * generates its own character auto-repeat.
     */
    private void beginPending(int keyCode, Runnable tapAction, Runnable holdAction, long holdMs) {
        flushPendingAsTap(); // a different key was still pending -> resolve it as a tap
        pendingKeyCode = keyCode;
        pendingTapAction = tapAction;
        longPressFired = false;
        longPressRunnable = () -> {
            holdAction.run();
            longPressFired = true;
        };
        handler.postDelayed(longPressRunnable, holdMs);
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
            pendingTapAction.run();
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
        pendingTapAction = null;
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

    private void commitUnicode(int codePoint) {
        if (codePoint != 0) commit(new String(Character.toChars(codePoint)));
    }

    /** Sends a complete key stroke to the focused editor through the accessibility IME. */
    private void sendKey(int keyCode, int metaState) {
        InputMethod im = getInputMethod();
        if (im == null) return;
        InputMethod.AccessibilityInputConnection ic = im.getCurrentInputConnection();
        if (ic == null) return;
        long now = android.os.SystemClock.uptimeMillis();
        int[] modifierCodes = {
                KeyEvent.KEYCODE_CTRL_LEFT, KeyEvent.KEYCODE_ALT_LEFT,
                KeyEvent.KEYCODE_SHIFT_LEFT, KeyEvent.KEYCODE_META_LEFT
        };
        int[] modifierMasks = {
                KeyEvent.META_CTRL_ON, KeyEvent.META_ALT_ON,
                KeyEvent.META_SHIFT_ON, KeyEvent.META_META_ON
        };
        int activeMeta = 0;
        for (int i = 0; i < modifierCodes.length; i++) {
            if ((metaState & modifierMasks[i]) != 0) {
                activeMeta |= modifierMasks[i];
                ic.sendKeyEvent(new KeyEvent(now, now, KeyEvent.ACTION_DOWN,
                        modifierCodes[i], 0, activeMeta));
            }
        }
        ic.sendKeyEvent(new KeyEvent(now, now, KeyEvent.ACTION_DOWN, keyCode, 0, metaState));
        ic.sendKeyEvent(new KeyEvent(now, now, KeyEvent.ACTION_UP, keyCode, 0, metaState));
        for (int i = modifierCodes.length - 1; i >= 0; i--) {
            if ((metaState & modifierMasks[i]) != 0) {
                activeMeta &= ~modifierMasks[i];
                ic.sendKeyEvent(new KeyEvent(now, now, KeyEvent.ACTION_UP,
                        modifierCodes[i], 0, activeMeta));
            }
        }
    }

    private void perform(KeyAction action) {
        if (action.text != null) commit(action.text);
        else sendKey(action.keyCode, action.modifiers);
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
        resetPhysicalRemapState();
    }

    private void resetPhysicalRemapState() {
        rightAltHeld = false;
        rightShiftHeld = false;
        rewrittenKeys.clear();
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (orientation != null) orientation.stop();
        if (instance == this) instance = null;
    }
}
