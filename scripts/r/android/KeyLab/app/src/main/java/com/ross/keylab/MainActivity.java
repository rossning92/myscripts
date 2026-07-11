package com.ross.keylab;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import rikka.shizuku.Shizuku;

public class MainActivity extends Activity {

    private static final int SHIZUKU_REQ = 1001;

    private TextView status;
    private Switch autoLandscape;

    private final Shizuku.OnRequestPermissionResultListener shizukuPermListener =
            (requestCode, grantResult) -> {
                if (requestCode != SHIZUKU_REQ) return;
                if (grantResult == PackageManager.PERMISSION_GRANTED) {
                    applyLayoutViaShizuku();
                } else {
                    toast("Shizuku permission denied.");
                }
            };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = dp(20);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("KeyLab");
        title.setTextSize(24);
        root.addView(title);

        TextView blurb = new TextView(this);
        blurb.setText("Tap a mapped key to type its normal character; hold it to type the symbol.");
        blurb.setPadding(0, dp(8), 0, dp(16));
        root.addView(blurb);

        status = new TextView(this);
        status.setPadding(0, 0, 0, dp(12));
        root.addView(status);

        Button enable = new Button(this);
        enable.setText("Open Accessibility settings");
        enable.setOnClickListener(v ->
                startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        root.addView(enable);

        TextView remapBlurb = new TextView(this);
        remapBlurb.setPadding(0, dp(20), 0, dp(4));
        remapBlurb.setText("Right Shift -> Esc uses a bundled keyboard layout (no root, works "
                + "in every app). Enable it under Physical keyboard, pick your keyboard, then "
                + "select \"KeyLab Layout\".");
        root.addView(remapBlurb);

        Button hardKb = new Button(this);
        hardKb.setText("Open Physical keyboard settings");
        hardKb.setOnClickListener(v -> {
            try {
                startActivity(new Intent("android.settings.HARD_KEYBOARD_SETTINGS"));
            } catch (Exception e) {
                startActivity(new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS));
            }
        });
        root.addView(hardKb);

        TextView shizukuBlurb = new TextView(this);
        shizukuBlurb.setPadding(0, dp(20), 0, dp(4));
        shizukuBlurb.setText("Or, with Shizuku running, apply the KeyLab layout to every keyboard "
                + "and IME at once - no per-IME picking. Re-run after enabling a new IME or "
                + "connecting a new keyboard.");
        root.addView(shizukuBlurb);

        Button applyAll = new Button(this);
        applyAll.setText("Apply KeyLab to all IMEs (Shizuku)");
        applyAll.setOnClickListener(v -> applyLayoutViaShizuku());
        root.addView(applyAll);

        TextView stickyBlurb = new TextView(this);
        stickyBlurb.setPadding(0, dp(20), 0, dp(4));
        stickyBlurb.setText("Sticky keys (tap a modifier, then the next key = combo) is built "
                + "into Android. Open the button below, then Physical keyboard accessibility "
                + "-> Sticky keys.");
        root.addView(stickyBlurb);

        Button stickyKeys = new Button(this);
        stickyKeys.setText("Open Sticky keys settings");
        stickyKeys.setOnClickListener(v -> {
            try {
                startActivity(new Intent("android.settings.HARD_KEYBOARD_SETTINGS"));
            } catch (Exception e) {
                startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
            }
        });
        root.addView(stickyKeys);

        TextView rotateBlurb = new TextView(this);
        rotateBlurb.setPadding(0, dp(20), 0, dp(4));
        rotateBlurb.setText("Auto-landscape: when the toggle below is on and an external keyboard "
                + "connects, the screen is pinned to landscape (and auto-rotate returns when it "
                + "disconnects). This needs \"Modify system settings\" - grant it below.");
        root.addView(rotateBlurb);

        autoLandscape = new Switch(this);
        autoLandscape.setText("Auto-landscape with keyboard (Win + R to toggle)");
        autoLandscape.setChecked(KeyboardOrientationController.isEnabled(this));
        autoLandscape.setOnCheckedChangeListener((v, isChecked) -> setAutoLandscape(isChecked));
        root.addView(autoLandscape);

        Button writeSettings = new Button(this);
        writeSettings.setText("Grant Modify system settings");
        writeSettings.setOnClickListener(v ->
                startActivity(new Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS,
                        Uri.parse("package:" + getPackageName()))));
        root.addView(writeSettings);

        TextView tryHere = new TextView(this);
        tryHere.setPadding(0, dp(20), 0, dp(4));
        tryHere.setText("Try it here:");
        root.addView(tryHere);
        EditText sandbox = new EditText(this);
        sandbox.setHint("type here");
        root.addView(sandbox);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);

        Shizuku.addRequestPermissionResultListener(shizukuPermListener);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        Shizuku.removeRequestPermissionResultListener(shizukuPermListener);
    }

    @Override
    protected void onResume() {
        super.onResume();
        boolean on = LongPressAccessibilityService.getInstance() != null;
        status.setText(on
                ? "Service: ENABLED"
                : "Service: OFF - enable \"KeyLab\" under Accessibility.");

        // The Win+R hotkey can flip this while we were backgrounded - reflect the real state.
        autoLandscape.setChecked(KeyboardOrientationController.isEnabled(this));
    }

    // Persist the toggle, and apply it live if the service is already running.
    private void setAutoLandscape(boolean on) {
        LongPressAccessibilityService svc = LongPressAccessibilityService.getInstance();
        if (svc != null) {
            svc.setAutoLandscapeEnabled(on);
        } else {
            KeyboardOrientationController.setEnabledPref(this, on);
        }
    }

    private void applyLayoutViaShizuku() {
        if (!Shizuku.pingBinder()) {
            toast("Shizuku is not running. Start the Shizuku app first.");
            return;
        }
        if (Shizuku.isPreV11()) {
            toast("Shizuku pre-v11 is not supported.");
            return;
        }
        if (Shizuku.checkSelfPermission() != PackageManager.PERMISSION_GRANTED) {
            Shizuku.requestPermission(SHIZUKU_REQ);
            return;
        }
        // The apply loop makes many cross-process binder calls; keep it off the UI thread.
        new Thread(() -> {
            String result;
            try {
                result = ShizukuLayoutApplier.apply(this);
            } catch (Throwable t) {
                Log.e("KeyLab", "Shizuku apply failed", t);
                result = "Failed: " + t;
            }
            String msg = result;
            runOnUiThread(() -> toast(msg));
        }).start();
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
