package com.ross.keylab;

import android.content.Context;
import android.hardware.input.InputManager;
import android.os.Handler;
import android.provider.Settings;
import android.view.InputDevice;
import android.view.Surface;

/**
 * Pins the display to landscape while an external physical keyboard is connected,
 * and restores the user's prior rotation settings when it disconnects.
 *
 * Mechanism: USER_ROTATION is honored only while auto-rotate is off, so we toggle
 * both. This needs the "Modify system settings" permission and only affects surfaces
 * that don't pin their own orientation - the launcher forces portrait and even
 * rewrites USER_ROTATION back, so we re-assert on every foreground change to recover
 * landscape once such an app is left. The home screen itself cannot be forced.
 */
final class KeyboardOrientationController {

    private static final int LANDSCAPE = Surface.ROTATION_90;

    private final Context context;
    private final InputManager inputManager;

    // While forcing landscape we hold the user's pre-existing settings to restore them.
    private boolean forced;
    private int savedAutoRotate;
    private int savedUserRotation;

    private final InputManager.InputDeviceListener inputListener =
            new InputManager.InputDeviceListener() {
                @Override public void onInputDeviceAdded(int id) { sync(); }
                @Override public void onInputDeviceRemoved(int id) { sync(); }
                @Override public void onInputDeviceChanged(int id) { sync(); }
            };

    KeyboardOrientationController(Context context) {
        this.context = context;
        this.inputManager = (InputManager) context.getSystemService(Context.INPUT_SERVICE);
    }

    /** Begin watching for keyboard connect/disconnect. Callbacks run on {@code handler}. */
    void start(Handler handler) {
        if (inputManager != null) inputManager.registerInputDeviceListener(inputListener, handler);
        sync(); // handle a keyboard already connected at startup
    }

    /** Stop watching and hand rotation back to the user's original settings. */
    void stop() {
        if (inputManager != null) inputManager.unregisterInputDeviceListener(inputListener);
        restore();
    }

    /**
     * Re-assert the landscape lock after a foreground app reset it. The launcher
     * rewrites USER_ROTATION back to portrait while auto-rotate is off, so leaving it
     * for another app needs the lock reapplied. Writes only when a value has drifted.
     */
    void onForegroundChanged() {
        if (!forced || !canWrite()) return;
        if (get(Settings.System.ACCELEROMETER_ROTATION, 1) != 0) {
            put(Settings.System.ACCELEROMETER_ROTATION, 0);
        }
        if (get(Settings.System.USER_ROTATION, Surface.ROTATION_0) != LANDSCAPE) {
            put(Settings.System.USER_ROTATION, LANDSCAPE);
        }
    }

    // Reconciles the current lock with whether a keyboard is present.
    private void sync() {
        if (!canWrite()) return;
        if (hasExternalKeyboard()) {
            if (forced) return; // already forced -> don't re-snapshot our own values
            savedAutoRotate = get(Settings.System.ACCELEROMETER_ROTATION, 1);
            savedUserRotation = get(Settings.System.USER_ROTATION, Surface.ROTATION_0);
            forced = true;
            put(Settings.System.ACCELEROMETER_ROTATION, 0);
            put(Settings.System.USER_ROTATION, LANDSCAPE);
        } else {
            restore();
        }
    }

    private void restore() {
        if (!forced) return;
        forced = false;
        if (!canWrite()) return;
        put(Settings.System.USER_ROTATION, savedUserRotation);
        put(Settings.System.ACCELEROMETER_ROTATION, savedAutoRotate);
    }

    private boolean hasExternalKeyboard() {
        if (inputManager == null) return false;
        for (int id : inputManager.getInputDeviceIds()) {
            InputDevice d = inputManager.getInputDevice(id);
            if (d == null || d.isVirtual() || !d.isExternal()) continue;
            if (d.getKeyboardType() == InputDevice.KEYBOARD_TYPE_ALPHABETIC) return true;
        }
        return false;
    }

    private boolean canWrite() {
        return Settings.System.canWrite(context);
    }

    private int get(String key, int def) {
        return Settings.System.getInt(context.getContentResolver(), key, def);
    }

    private void put(String key, int value) {
        Settings.System.putInt(context.getContentResolver(), key, value);
    }
}
