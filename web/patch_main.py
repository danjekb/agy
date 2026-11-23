#!/usr/bin/env python3
"""
web/patch_main.py - Dynamic patcher for web/main.js.

Locates the Appearance settings block and injects the Desktop Mode toggle
if not already present. Safe, idempotent, and resilient to upstream changes.
"""

import sys
import os
import re

def patch_main(file_path):
    if not os.path.isfile(file_path):
        print(f"[web-patch] file not found: {file_path}", file=sys.stderr)
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    modified = False

    # Resume trajectory stream sync: expose the registry so the resume hook can
    # re-link stalled ConnectRPC streams after Android unfreezes the WebView.
    # Names adapted to our bundle (JSC$9550__states, $ga instead of Hja).
    vka_target = 'this._factory=a}'
    vka_repl = (
        'this._factory=a;'
        'this.refreshTrajectories=()=>{try{if(!this._factory)return;'
        'for(let [c,e]of this.JSC$9550__states.entries()){let f=e;f.link.dispose();f.underlyingProvider.dispose();f.underlyingProvider=this._factory(c);f.link=$ga(f.underlyingProvider,f.provider,{omitInitial:!0});}'
        '}catch(err){console.warn("[AGY ResumeSync] refreshTrajectories err",err)}};'
        'window.__agTrajectoriesRegistry=this;'
        'window.__agRefreshTrajectories=s=>{console.log("[AGY ResumeSync] Refreshing active trajectories triggered by",s);this.refreshTrajectories()}};'
    )
    if vka_target in content and "agTrajectoriesRegistry" not in content:
        content = content.replace(vka_target, vka_repl, 1)
        modified = True
        print("[web-patch] Exposed trajectory refresh registry")

    vka_disp_target = 'dispose(){for(let [a]of this.JSC$9550__states.entries())this._disposeEntry(a)}'
    vka_disp_repl = 'dispose(){if(window.__agTrajectoriesRegistry===this){window.__agTrajectoriesRegistry=void 0;window.__agRefreshTrajectories=void 0}for(let [a]of this.JSC$9550__states.entries())this._disposeEntry(a)}'
    if vka_disp_target in content:
        content = content.replace(vka_disp_target, vka_disp_repl, 1)
        modified = True
        print("[web-patch] Cleaned up trajectory registry on dispose")

    # Inject a "Custom Models" button into Models & Usage that opens the local
    # model-proxy management panel (state.json written by entry.js at runtime).
    models_target = 'description:"Manage your model quota and credits."},'
    models_repl = (
        'description:"Manage your model quota and credits."},'
        'E.createElement(PU,{title:"Custom Models"},'
        'E.createElement(NU,null,E.createElement(OU,{label:"Antigravity Model Manager",'
        'description:"Open the local web panel to add, discover, and manage AI models.",'
        'rightElement:E.createElement(BI,{variant:"primary",size:"sm",onClick:function(){'
        'if(window.Android&&typeof window.Android.openModelManager==="function"){window.Android.openModelManager();return;}'
        'var u=(window.Android&&typeof window.Android.getModelManagerUrl==="function"&&window.Android.getModelManagerUrl())'
        '||(window.__APP_CONFIG__&&window.__APP_CONFIG__.modelManagerUrl)||"http://127.0.0.1:50996/_addon/";'
        'window.open(u,"_blank");'
        '}},"Open Dashboard")}))),'
    )
    if models_target in content and "Antigravity Model Manager" not in content:
        content = content.replace(models_target, models_repl, 1)
        print("[web-patch] Injected Custom Models manager button")
        modified = True

    # Expose the web "Developer" settings screen in release builds.
    # Upstream gates it behind window.__APP_CONFIG__.devMode (build --dev),
    # but the developerMode feature itself is activated by the custom flag
    # "enable-developer-mode" in Va. Force that flag on so the same screen is
    # available in the normal com.agy release without changing package/ports.
    target_dev = 'Va=[...(S9()?["enable-developer-mode"]:[])'
    replacement_dev = 'Va=[...["enable-developer-mode"]'
    if target_dev in content:
        content = content.replace(target_dev, replacement_dev, 1)
        print("[web-patch] Enabled Developer settings screen in release build")
        modified = True

    # ---- AMOLED Black theme (4th option in Appearance > Theme) ----------
    # The bundled UI has three modes (1=system, 2=light, 3=dark). Add 4=amoled
    # to the option list, labels, icons and the string->int map used by
    # onThemeChange, then tag <body> with theme-amoled so our theme_sync
    # resolver reports 'amoled' back to the native Android bridge.
    amoled_rules = [
        ('const KKd=[1,2,3],', 'const KKd=[1,2,3,4],'),
        ('case 2:return"Light";case 3:return"Dark";default:return"System"',
         'case 2:return"Light";case 3:return"Dark";case 4:return"Amoled";default:return"System"'),
        ('case 2:return"light_mode";case 3:return"dark_mode";default:return"monitor"',
         'case 2:return"light_mode";case 3:return"dark_mode";case 4:return"dark_mode";default:return"monitor"'),
        ('["system",1],["light",2],["dark",3]]',
         '["system",1],["light",2],["dark",3],["amoled",4]]'),
        ('themeMode:c}):a?3:2;',
         'themeMode:c}):a?3:2;document.body.classList.toggle("theme-amoled",c===4);if(c===4){try{window.__AG_RESOLVED_THEME__="amoled"}catch(_){}}'),
        # The core themeModeProvider only knows 1/2/3. For 4 handle the click
        # locally: paint natively through the bridge and tag the DOM ourselves
        # instead of pushing an unsupported value to core (which makes the
        # selector snap back and look unclickable).
        # On startup the picker reads its value from core's themeModeProvider,
        # which only knows 1/2/3 and therefore falls back to Dark (3) even
        # though native persisted AMOLED. Read our injected marker instead.
        ('Cfc=()=>{var {themeModeProvider:a}=Bfc();return gl(a)}',
         'Cfc=()=>{if(typeof window!=="undefined"&&window.__AG_RESOLVED_THEME__==="amoled")return 4;var {themeModeProvider:a}=Bfc();return gl(a)}'),
        ('var g=(0,E.useCallback)(G=>{d(G)},[d])',
         'var g=(0,E.useCallback)(G=>{if(G===4){try{if(window.Android&&typeof window.Android.setThemeByUser==="function")window.Android.setThemeByUser("amoled");window.__AG_RESOLVED_THEME__="amoled";document.body.classList.add("theme-amoled");document.documentElement.classList.add("dark","amoled");document.documentElement.classList.remove("light")}catch(_){}return}d(G)},[d])'),
    ]
    for target_amoled, replacement_amoled in amoled_rules:
        if target_amoled in content:
            content = content.replace(target_amoled, replacement_amoled, 1)
            print("[web-patch] Added AMOLED theme option")
            modified = True

    # Make developer overrides actually apply in release builds.
    # Hna() reads the Mendel experiment flag "enable-developer-mode" from the
    # language server. Without it the Developer screen is visible (Va above)
    # but every toggle is ignored: Wna() only forwards jetski.developer.*
    # overrides to fj().flagOverrideSync when this returns true. Force it on.
    target_hna = 'function Hna(){try{return hj(fj(),"enable-developer-mode")}catch{return!1}}'
    replacement_hna = 'function Hna(){try{return hj(fj(),"enable-developer-mode")||!0}catch{return!0}}'
    if target_hna in content:
        content = content.replace(target_hna, replacement_hna, 1)
        print("[web-patch] Forced enable-developer-mode Mendel flag on")
        modified = True

    # Fix voice left_home unmount abort bug
    target_unmount = 'E.current!==YU||DU||kV("left_home")'
    replacement_unmount = 'E.current!==YU||DU||XU||kV("left_home")'
    if target_unmount in content:
        content = content.replace(target_unmount, replacement_unmount)
        print("[web-patch] Patched voice left_home unmount race condition")
        modified = True

    # Separate AbortError from NotReadableError in $Nb
    target_err = 'case "NotReadableError":case "AbortError":return oU("Microphone is in use or unavailable.");'
    replacement_err = 'case "NotReadableError":return oU("Microphone is in use or unavailable.");case "AbortError":return oU("Microphone connection was aborted. Please retry.");'
    if target_err in content:
        content = content.replace(target_err, replacement_err)
        print("[web-patch] Patched voice AbortError message")
        modified = True

    # Use Blob URL fallback for AudioWorklet addModule
    target_worklet = 'G(await E(I.audioWorklet.addModule("data:application/javascript;base64,"+btoa(W1a))))'
    replacement_worklet = 'G(await E(I.audioWorklet.addModule(window.URL&&window.Blob?URL.createObjectURL(new Blob([W1a],{type:"application/javascript"})):"data:application/javascript;base64,"+btoa(W1a))))'
    if target_worklet in content:
        content = content.replace(target_worklet, replacement_worklet)
        print("[web-patch] Patched audioWorklet addModule to use Blob URL fallback")
        modified = True

    if "Desktop Mode" in content or "ag_desktop_mode" in content:
        print("[web-patch] Desktop Mode toggle already present in main.js")
        if modified:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        return True

    # 1. JSX Theme element injection: find Theme element in Appearance
    theme_idx = content.find('{label:"Theme"')
    theme_match = None
    react_id = "A"
    if theme_idx != -1:
        # Search backwards within a reasonable window for createElement
        window_start = max(0, theme_idx - 100)
        window_end = min(len(content), theme_idx + 500)
        window_text = content[window_start:window_end]
        theme_pattern = re.compile(
            r'([A-Za-z0-9_$]+)\.createElement\(([A-Za-z0-9_$]+),\{label:"Theme",.*?onSelect:[A-Za-z0-9_$]+\}\)'
        )
        theme_match = theme_pattern.search(window_text)
        if theme_match:
            react_id = theme_match.group(1)

    if not theme_match:
        print("[web-patch] pattern not matched: theme element not found", file=sys.stderr)
        return False

    # 2. State hook injection pattern in Appearance component:
    # Pattern A (legacy): Matches var C=g!==3,D=g!==2,E=F=>G=>{F===t&&v(G)};
    # Search within reasonable distance from theme_idx to avoid slow regex scanning
    search_window = content[max(0, theme_idx - 1200):theme_idx]
    hook_pattern = re.compile(r'(var\s+[A-Za-z0-9_$]+=[A-Za-z0-9_$]+!==3,\s*[A-Za-z0-9_$]+=[A-Za-z0-9_$]+!==2,\s*[A-Za-z0-9_$]+=[A-Za-z0-9_$]+=>\s*[A-Za-z0-9_$]+=>\{.*?\};)')
    hook_match = hook_pattern.search(search_window)

    ret_target = None
    if not hook_match:
        # Pattern B (v2.33.0+): Hook right before the component return statement
        ret_needle = f"return {react_id}.createElement("
        if ret_needle in search_window:
            ret_target = ret_needle

    if not hook_match and not ret_target:
        print(f"[web-patch] patterns not matched: hook=False, ret_target=False", file=sys.stderr)
        return False

    hook_code = (
        f"var [isDesktop,setIsDesktop]=(0,{react_id}.useState)(()=>{{"
        "try{if(window.Android&&typeof window.Android.isDesktopMode==='function')return window.Android.isDesktopMode();"
        "var s=localStorage.getItem('ag_desktop_mode');return s===null?!1:s==='true'}catch(_){return !1}});"
        f"var onDesktopToggle=(0,{react_id}.useCallback)(v=>{{"
        "setIsDesktop(v);try{localStorage.setItem('ag_desktop_mode',String(v));"
        "if(window.Android&&typeof window.Android.setDesktopMode==='function')window.Android.setDesktopMode(v)}catch(_){}},[]);"
    )

    # Detect switch and setting item components
    item_comp = "v3"
    switch_comp = "dX"
    sw_m = re.search(r'createElement\(([A-Za-z0-9_$]+),\{[^\}]*label:[^,]+,[^\}]*rightElement:([A-Za-z0-9_$]+)\.createElement\(([A-Za-z0-9_$]+),\{checked:', content)
    if sw_m:
        item_comp = sw_m.group(1)
        switch_comp = sw_m.group(3)
    else:
        # Fallback to secondary pattern
        re_idx = content.find('rightElement:')
        if re_idx != -1:
            re_window = content[max(0, re_idx - 150):min(len(content), re_idx + 150)]
            item_m = re.search(r'([A-Za-z0-9_$]+)\.createElement\(([A-Za-z0-9_$]+),\{label:[^,]+,description:[^,]+,rightElement:', re_window)
            if item_m:
                item_comp = item_m.group(2)
            sw_m2 = re.search(r'rightElement:[A-Za-z0-9_$]+\.createElement\(([A-Za-z0-9_$]+),\{checked:', re_window)
            if sw_m2:
                switch_comp = sw_m2.group(1)

    orig_theme = theme_match.group(0)
    injected_theme = (
        orig_theme
        + f',{react_id}.createElement({item_comp},{{label:"Desktop Mode",description:"Use desktop viewport and user agent for the workspace",'
        + f'rightElement:{react_id}.createElement({switch_comp},{{checked:isDesktop,onCheckedChange:onDesktopToggle}})}})'
    )

    if hook_match:
        orig_hook = hook_match.group(1)
        content = content.replace(orig_hook, hook_code + orig_hook, 1)
    else:
        pre_theme = content[:theme_idx]
        post_theme = content[theme_idx:]
        last_ret_pos = pre_theme.rfind(ret_target)
        if last_ret_pos == -1:
            print("[web-patch] failed to locate return statement before theme element", file=sys.stderr)
            return False
        pre_theme = pre_theme[:last_ret_pos] + hook_code + ret_target + pre_theme[last_ret_pos + len(ret_target):]
        content = pre_theme + post_theme

    content = content.replace(orig_theme, injected_theme, 1)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("[web-patch] Successfully patched Desktop Mode toggle into main.js (mobile by default, English)")
    return True

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "main.js")
    if not patch_main(path):
        sys.exit(1)
