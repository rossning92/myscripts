package com.ross.speechtotext;

import android.content.ComponentName;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.text.TextUtils;

import androidx.appcompat.app.AppCompatActivity;
import androidx.preference.EditTextPreference;
import androidx.preference.Preference;
import androidx.preference.PreferenceFragmentCompat;
import androidx.preference.SwitchPreferenceCompat;

public class SettingsActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (savedInstanceState == null) {
            getSupportFragmentManager().beginTransaction()
                    .replace(android.R.id.content, new SettingsFragment())
                    .commit();
        }
        if (getSupportActionBar() != null) {
            getSupportActionBar().setTitle("Settings");
        }
        FloatingService.startIfReady(this);
    }

    public static class SettingsFragment extends PreferenceFragmentCompat {
        @Override
        public void onCreatePreferences(Bundle savedInstanceState, String rootKey) {
            setPreferencesFromResource(R.xml.preferences, rootKey);
            EditTextPreference apiKeyPref = findPreference(MainActivity.KEY_OPENAI_API_KEY);
            if (apiKeyPref != null) {
                apiKeyPref.setSummaryProvider(pref -> {
                    String val = ((EditTextPreference) pref).getText();
                    if (val == null || val.isEmpty()) return "Not set";
                    if (val.length() <= 8) return "****";
                    return val.substring(0, 4) + "..." + val.substring(val.length() - 4);
                });
            }
            SwitchPreferenceCompat accessibilityPref = findPreference("accessibility_status");
            if (accessibilityPref != null) {
                accessibilityPref.setOnPreferenceChangeListener((pref, newValue) -> {
                    startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
                    return false;
                });
            }
        }

        @Override
        public void onResume() {
            super.onResume();
            updateAccessibilityStatus();
        }

        private void updateAccessibilityStatus() {
            SwitchPreferenceCompat pref = findPreference("accessibility_status");
            if (pref == null) return;
            String enabled = Settings.Secure.getString(
                    requireContext().getContentResolver(),
                    Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
            String component = new ComponentName(requireContext(), TypeAccessibilityService.class).flattenToString();
            pref.setChecked(!TextUtils.isEmpty(enabled) && enabled.contains(component));
        }
    }
}
