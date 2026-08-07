package com.ross.keylab;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {

    private TextView status;
    private Switch autoLandscape;
    private EditText tapMappings;
    private EditText holdMappings;

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
        blurb.setText("Tap a mapped key for its normal action; hold it for:\n"
                + "Q -> Esc    H -> Home    E -> End\n"
                + "U -> Page Up    D -> Page Down\n"
                + "I -> Up    J -> Left    K -> Down    L -> Right\n\n"
                + "The existing letter and number holds still type their symbols.");
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

        TextView mappingTitle = new TextView(this);
        mappingTitle.setText("Custom key actions");
        mappingTitle.setTextSize(20);
        mappingTitle.setPadding(0, dp(20), 0, dp(4));
        root.addView(mappingTitle);

        TextView mappingHelp = new TextView(this);
        mappingHelp.setText("One mapping per line: Key = Action. Actions can be text, a special "
                + "key (Left, Esc, Home, PageDown), or a combination (Ctrl+A, Ctrl+Shift+B). "
                + "Use text:Home when a word should be typed literally. Hold actions fire after "
                + Mapping.LONGPRESS_MS + " ms.");
        root.addView(mappingHelp);

        TextView tapLabel = new TextView(this);
        tapLabel.setText("Tap overrides");
        tapLabel.setPadding(0, dp(12), 0, 0);
        root.addView(tapLabel);
        tapMappings = mappingEditor("Example: H = Left", Mapping.getTapSpec(this));
        root.addView(tapMappings);

        TextView holdLabel = new TextView(this);
        holdLabel.setText("Long-press actions");
        holdLabel.setPadding(0, dp(12), 0, 0);
        root.addView(holdLabel);
        holdMappings = mappingEditor("Example: B = Ctrl+B", Mapping.getHoldSpec(this));
        root.addView(holdMappings);

        Button saveMappings = new Button(this);
        saveMappings.setText("Save key actions");
        saveMappings.setOnClickListener(v -> saveMappings());
        root.addView(saveMappings);

        Button resetMappings = new Button(this);
        resetMappings.setText("Restore default key actions");
        resetMappings.setOnClickListener(v -> {
            tapMappings.setText("");
            holdMappings.setText(Mapping.DEFAULT_HOLD_SPEC);
            saveMappings();
        });
        root.addView(resetMappings);

        TextView remapBlurb = new TextView(this);
        remapBlurb.setPadding(0, dp(20), 0, dp(4));
        remapBlurb.setText("While the accessibility service is enabled, Right Shift sends Esc "
                + "and Right Alt is treated as Left Alt. These app-level remaps work only where "
                + "Android provides KeyLab an accessibility input connection.");
        root.addView(remapBlurb);

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

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
    }

    private EditText mappingEditor(String hint, String value) {
        EditText editor = new EditText(this);
        editor.setHint(hint);
        editor.setText(value);
        editor.setMinLines(3);
        editor.setGravity(Gravity.TOP | Gravity.START);
        editor.setHorizontallyScrolling(false);
        return editor;
    }

    private void saveMappings() {
        String taps = tapMappings.getText().toString();
        String holds = holdMappings.getText().toString();
        String error = Mapping.validate(taps);
        if (error != null) {
            toast("Tap overrides: " + error);
            return;
        }
        error = Mapping.validate(holds);
        if (error != null) {
            toast("Long-press actions: " + error);
            return;
        }
        Mapping.save(this, taps, holds);
        LongPressAccessibilityService service = LongPressAccessibilityService.getInstance();
        if (service != null) service.reloadMappings();
        toast("Key actions saved" + (service == null ? ". They apply when the service starts." : "."));
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
