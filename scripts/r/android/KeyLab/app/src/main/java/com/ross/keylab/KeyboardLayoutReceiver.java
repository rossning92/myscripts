package com.ross.keylab;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Exists only so the system can discover the bundled keyboard layout via the
 * QUERY_KEYBOARD_LAYOUTS broadcast. Android reads the layout from the manifest
 * meta-data (@xml/keyboard_layouts), so no runtime handling is needed here.
 */
public class KeyboardLayoutReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
    }
}
