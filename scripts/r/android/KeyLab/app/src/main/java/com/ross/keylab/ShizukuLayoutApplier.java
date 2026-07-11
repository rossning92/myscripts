package com.ross.keylab;

import android.content.Context;
import android.hardware.input.InputManager;
import android.os.IBinder;
import android.os.Process;
import android.view.InputDevice;
import android.view.inputmethod.InputMethodInfo;
import android.view.inputmethod.InputMethodManager;
import android.view.inputmethod.InputMethodSubtype;

import org.lsposed.hiddenapibypass.HiddenApiBypass;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

import rikka.shizuku.ShizukuBinderWrapper;
import rikka.shizuku.SystemServiceHelper;

/**
 * Writes the KeyLab physical-keyboard layout selection for every enabled IME (and subtype) via
 * Shizuku's shell privileges, so the user does not have to pick it per-IME in system settings.
 *
 * Android keys the layout selection by (keyboard x IME x subtype). The public settings UI only sets
 * one context at a time; the shell uid holds SET_KEYBOARD_LAYOUT, so through Shizuku we set them all.
 */
final class ShizukuLayoutApplier {

    // The android:name of the <keyboard-layout> in res/xml/keyboard_layouts.xml.
    private static final String LAYOUT_NAME = "keyboard_layout_keylab";

    // UserHandle.PER_USER_RANGE. userId = uid / PER_USER_RANGE.
    private static final int PER_USER_RANGE = 100000;

    private ShizukuLayoutApplier() {}

    static String apply(Context ctx) throws Exception {
        HiddenApiBypass.addHiddenApiExemptions("L");

        // KeyboardLayoutDescriptor.format() = packageName + "/" + receiverName + "/" + keyboardName.
        String descriptor = ctx.getPackageName() + "/"
                + KeyboardLayoutReceiver.class.getName() + "/" + LAYOUT_NAME;

        IBinder inputBinder = new ShizukuBinderWrapper(
                SystemServiceHelper.getSystemService(Context.INPUT_SERVICE));
        Class<?> stubCls = Class.forName("android.hardware.input.IInputManager$Stub");
        Object iim = stubCls.getMethod("asInterface", IBinder.class).invoke(null, inputBinder);
        Class<?> iimCls = Class.forName("android.hardware.input.IInputManager");
        Class<?> idiCls = Class.forName("android.hardware.input.InputDeviceIdentifier");
        Method setLayout = iimCls.getMethod("setKeyboardLayoutForInputDevice",
                idiCls, int.class, InputMethodInfo.class, InputMethodSubtype.class, String.class);

        int userId = Process.myUid() / PER_USER_RANGE;

        List<Object> identifiers = new ArrayList<>();
        List<String> names = new ArrayList<>();
        InputManager im = (InputManager) ctx.getSystemService(Context.INPUT_SERVICE);
        Method getIdentifier = InputDevice.class.getMethod("getIdentifier");
        for (int id : im.getInputDeviceIds()) {
            InputDevice dev = im.getInputDevice(id);
            if (dev == null || dev.isVirtual()) continue;
            boolean fullKeyboard =
                    dev.getKeyboardType() == InputDevice.KEYBOARD_TYPE_ALPHABETIC
                    && (dev.getSources() & InputDevice.SOURCE_KEYBOARD) == InputDevice.SOURCE_KEYBOARD;
            if (!fullKeyboard) continue;
            identifiers.add(getIdentifier.invoke(dev));
            names.add(dev.getName());
        }
        if (identifiers.isEmpty()) {
            return "No physical keyboard detected. Connect the keyboard and try again.";
        }

        InputMethodManager imm =
                (InputMethodManager) ctx.getSystemService(Context.INPUT_METHOD_SERVICE);
        List<InputMethodInfo> imes = imm.getEnabledInputMethodList();

        int combos = 0;
        for (Object identifier : identifiers) {
            for (InputMethodInfo imi : imes) {
                List<InputMethodSubtype> subtypes = imm.getEnabledInputMethodSubtypeList(imi, true);
                if (subtypes == null || subtypes.isEmpty()) {
                    setLayout.invoke(iim, identifier, userId, imi, null, descriptor);
                    combos++;
                } else {
                    for (InputMethodSubtype st : subtypes) {
                        setLayout.invoke(iim, identifier, userId, imi, st, descriptor);
                        combos++;
                    }
                }
            }
        }
        return "Applied KeyLab layout to " + names + " across " + imes.size()
                + " IME(s), " + combos + " combos.";
    }
}
