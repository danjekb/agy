package com.agy.offline;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * Persists the "offline mode" preference: when enabled, a local placeholder
 * OAuth token is seeded so the app skips the Google sign-in screen. The core
 * and generation already run through the local model proxy without Google.
 */
public final class OfflinePrefs {

    private static final String PREFS = "agy_prefs";
    private static final String KEY_OFFLINE = "offline_mode";

    private OfflinePrefs() {
    }

    public static boolean isEnabled(Context appContext) {
        if (appContext == null) {
            return false;
        }
        return appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getBoolean(KEY_OFFLINE, false);
    }

    public static void setEnabled(Context appContext, boolean enabled) {
        if (appContext == null) {
            return;
        }
        appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putBoolean(KEY_OFFLINE, enabled).apply();
    }
}
