/**
 * patches/theme_sync/resolve.js - theme resolution (classList > storage > host).
 */
function fromClassList() {
  try {
    var body = doc && doc.body;
    if (body && body.classList) {
      if (body.classList.contains('theme-light')) return 'light';
      if (body.classList.contains('theme-amoled')) return 'amoled';
      if (body.classList.contains('theme-dark')) return 'dark';
    }
  } catch (e) { /* ignore */ }
  return null;
}

function resolveTheme() {
  // AMOLED is a native-only marker layered on top of the dark base theme.
  // It arrives via __AG_RESOLVED_THEME__ from ThemeManager.getTheme().
  if (typeof window !== 'undefined' && window.__AG_RESOLVED_THEME__ === 'amoled') {
    return 'amoled';
  }
  var cl = fromClassList();
  if (cl) return cl;
  if (hostTheme === 'light') return 'light';
  if (hostTheme === 'dark') return 'dark';
  if (typeof window !== 'undefined' && window.Android && typeof window.Android.getTheme === 'function') {
    try {
      var t = window.Android.getTheme();
      if (t === 'dark' || t === 'light') return t;
    } catch (e) {}
  }
  if (typeof window !== 'undefined' && window.__AG_RESOLVED_THEME__) {
    return window.__AG_RESOLVED_THEME__;
  }
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
}
