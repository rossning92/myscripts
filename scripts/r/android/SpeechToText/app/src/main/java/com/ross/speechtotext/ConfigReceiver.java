package com.ross.speechtotext;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import androidx.preference.PreferenceManager;

/**
 * A shell-only provisioning endpoint used by deploy.sh.
 *
 * The manifest protects this receiver with android.permission.DUMP. That
 * permission is held by adb/rish's shell user, but cannot be requested by an
 * ordinary third-party app.
 */
public class ConfigReceiver extends BroadcastReceiver {
    static final String ACTION_SET_OPENAI_API_KEY =
            "com.ross.speechtotext.action.SET_OPENAI_API_KEY";
    static final String EXTRA_OPENAI_API_KEY = "openai_api_key";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!ACTION_SET_OPENAI_API_KEY.equals(intent.getAction())) {
            setResultCode(1);
            setResultData("Unsupported action");
            return;
        }

        String apiKey = intent.getStringExtra(EXTRA_OPENAI_API_KEY);
        if (apiKey == null || apiKey.trim().isEmpty()) {
            setResultCode(1);
            setResultData("Missing API key");
            return;
        }

        boolean saved = PreferenceManager.getDefaultSharedPreferences(context)
                .edit()
                .putString(MainActivity.KEY_OPENAI_API_KEY, apiKey)
                .commit();
        if (!saved) {
            setResultCode(1);
            setResultData("Failed to save API key");
            return;
        }

        setResultCode(0);
        setResultData("OpenAI API key configured");
        FloatingService.startIfReady(context);
    }
}
