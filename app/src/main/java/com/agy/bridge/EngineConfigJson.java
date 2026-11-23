package com.agy.bridge;

import android.content.Context;

import com.agy.runtime.RuntimeConfig;
import com.agy.runtime.RuntimeManager;
import com.agy.shell.ShizukuBridge;

import org.json.JSONObject;

/** Serializes the app config object injected as window.__APP_CONFIG__. */
public final class EngineConfigJson {

    private final Context appContext;
    private final RuntimeManager runtime;
    private final EngineBridge engine;
    private final ShizukuBridge shizuku;
    private final ThemeBridge theme;

    public EngineConfigJson(Context appContext, RuntimeManager runtime, EngineBridge engine,
                            ShizukuBridge shizuku, ThemeBridge theme) {
        this.appContext = appContext;
        this.runtime = runtime;
        this.engine = engine;
        this.shizuku = shizuku;
        this.theme = theme;
    }

    public String get() {
        try {
            JSONObject o = new JSONObject();
            o.put("productName", "antigravity-app");
            o.put("csrfToken", engine.getCsrfToken());
            o.put("appVersion", RuntimeConfig.APP_VERSION_NAME);
            o.put("appVersionCode", RuntimeConfig.APP_VERSION_CODE);
            o.put("coreVersion", RuntimeConfig.CORE_VERSION);
            o.put("releaseChannel", RuntimeConfig.DEBUG ? "dev" : "stable");
            o.put("devMode", RuntimeConfig.DEBUG);
            o.put("enginePort", runtime.getHttpsPort());
            o.put("engineBaseUrl", engine.getBaseUrl());
            o.put("filesDir", appContext.getFilesDir().getAbsolutePath());
            o.put("runtimeDir", runtime.getRuntimeDir().getAbsolutePath());
            o.put("home", appContext.getFilesDir().getAbsolutePath());
            o.put("tmpDir", appContext.getCacheDir().getAbsolutePath());
            o.put("appDataDir", runtime.getAppDataDir().getAbsolutePath());
            o.put("shizukuAvailable", shizuku.isAvailable());
            o.put("theme", theme.getTheme());
            return o.toString();
        } catch (Exception e) {
            return "{}";
        }
    }

    /** Reads the local model-proxy management URL from its state file. */
    public static String readModelManagerUrl(Context appContext) {
        if (appContext == null) {
            return "http://127.0.0.1:50996/_addon/";
        }
        java.io.File[] candidates = new java.io.File[] {
            new java.io.File(appContext.getFilesDir(), ".gemini/antigravity-app/.ide-proxy/state.json"),
            new java.io.File(appContext.getFilesDir(), ".gemini/antigravity/.ide-proxy/state.json")
        };
        for (java.io.File stateFile : candidates) {
            if (stateFile.isFile()) {
                try {
                    String sc = new String(java.nio.file.Files.readAllBytes(stateFile.toPath()), java.nio.charset.StandardCharsets.UTF_8);
                    org.json.JSONObject st = new org.json.JSONObject(sc);
                    String mUrl = st.optString("managementUrl", "");
                    if (!mUrl.isEmpty()) {
                        return mUrl;
                    }
                } catch (Exception ignored) {}
            }
        }
        return "http://127.0.0.1:50996/_addon/";
    }
}
