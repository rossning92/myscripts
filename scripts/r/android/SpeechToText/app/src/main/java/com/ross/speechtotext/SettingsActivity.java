package com.ross.speechtotext;

import android.content.Intent;
import android.os.Bundle;

import androidx.appcompat.app.AppCompatActivity;
import androidx.preference.EditTextPreference;
import androidx.preference.PreferenceFragmentCompat;
import androidx.preference.PreferenceManager;

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
    }

    @Override
    public void finish() {
        String key = PreferenceManager.getDefaultSharedPreferences(this)
                .getString(MainActivity.KEY_OPENAI_API_KEY, "");
        if (!key.isEmpty()) {
            startForegroundService(new Intent(this, FloatingService.class));
        }
        super.finish();
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
        }
    }
}
