package com.ross.launcher;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.pm.LauncherApps;
import android.content.pm.ShortcutInfo;
import android.os.Bundle;

public class PinShortcutActivity extends Activity {

    private LauncherApps.PinItemRequest request;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LauncherApps launcherApps =
                (LauncherApps) getSystemService(Context.LAUNCHER_APPS_SERVICE);
        request = launcherApps == null ? null : launcherApps.getPinItemRequest(getIntent());
        if (request == null
                || request.getRequestType()
                != LauncherApps.PinItemRequest.REQUEST_TYPE_SHORTCUT) {
            finish();
            return;
        }

        ShortcutInfo shortcut = request.getShortcutInfo();
        CharSequence label = shortcut.getShortLabel();
        if (label == null || label.length() == 0) {
            label = shortcut.getLongLabel();
        }
        if (label == null || label.length() == 0) {
            label = shortcut.getPackage();
        }

        new AlertDialog.Builder(this)
                .setTitle("Add to Home screen?")
                .setMessage(label)
                .setPositiveButton("Add", (dialog, which) -> accept())
                .setNegativeButton("Cancel", (dialog, which) -> finish())
                .setOnCancelListener(dialog -> finish())
                .show();
    }

    private void accept() {
        if (request != null && request.isValid() && request.accept()) {
            setResult(RESULT_OK);
        }
        finish();
    }
}
