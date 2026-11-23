(function () {
  const THEME_KEY = "lila-theme";

  function getStoredTheme() {
    try {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === "light" || saved === "dark") return saved;
    } catch {
      /* ignore blocked storage */
    }
    return "dark";
  }

  function applyTheme(theme, persist) {
    const resolved = theme === "light" ? "light" : "dark";
    const root = document.documentElement;
    root.classList.toggle("dark", resolved === "dark");
    root.dataset.theme = resolved;

    const meta = document.querySelector('meta[name="color-scheme"]');
    if (meta) {
      meta.setAttribute("content", resolved);
    }

    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(resolved === "dark"));
    });

    if (persist) {
      try {
        localStorage.setItem(THEME_KEY, resolved);
      } catch {
        /* ignore blocked storage */
      }
    }
  }

  // Ensure initial DOM state matches stored preference (dark by default)
  applyTheme(getStoredTheme(), false);

  document.addEventListener("click", (e) => {
    const toggleBtn = e.target.closest("[data-theme-toggle]");
    if (toggleBtn) {
      const isDark = document.documentElement.classList.contains("dark");
      applyTheme(isDark ? "light" : "dark", true);
      return;
    }

    const btn = e.target.closest("button, a[role='button']");
    if (!btn || btn.classList.contains("fab") || btn.classList.contains("lila-copy-btn")) return;

    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;

    const ripple = document.createElement("span");
    ripple.className = "ripple";
    ripple.style.width = ripple.style.height = size + "px";
    ripple.style.left = x + "px";
    ripple.style.top = y + "px";

    btn.appendChild(ripple);
    ripple.addEventListener("animationend", () => ripple.remove());
  });

  window.addEventListener("storage", (e) => {
    if (e.key === THEME_KEY) {
      applyTheme(e.newValue === "light" ? "light" : "dark", false);
    }
  });

  // Mobile documentation drawer
  function initDrawer() {
    const mainEl = document.querySelector("main");
    const aside = mainEl ? mainEl.querySelector(":scope > aside") : null;
    if (!aside || document.querySelector(".lila-drawer")) return;

    const overlay = document.createElement("div");
    overlay.className = "lila-drawer-overlay";
    document.body.appendChild(overlay);

    const drawer = document.createElement("div");
    drawer.className = "lila-drawer";
    drawer.setAttribute("aria-label", "Documentation menu");
    drawer.innerHTML = aside.innerHTML;
    document.body.appendChild(drawer);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "lila-drawer-toggle";
    toggle.innerHTML = "☰";
    toggle.setAttribute("aria-label", "Toggle documentation menu");
    toggle.setAttribute("aria-expanded", "false");

    const header = document.querySelector("header");
    if (header) {
      const nav = header.querySelector("nav");
      if (nav) {
        nav.insertBefore(toggle, nav.firstChild);
      } else {
        header.prepend(toggle);
      }
    } else {
      document.body.prepend(toggle);
    }

    function openDrawer() {
      drawer.classList.add("open");
      overlay.classList.add("open");
      toggle.setAttribute("aria-expanded", "true");
      document.body.style.overflow = "hidden";
    }

    function closeDrawer() {
      drawer.classList.remove("open");
      overlay.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    }

    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      if (drawer.classList.contains("open")) {
        closeDrawer();
      } else {
        openDrawer();
      }
    });

    overlay.addEventListener("click", closeDrawer);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && drawer.classList.contains("open")) {
        closeDrawer();
        toggle.focus();
      }
    });

    drawer.addEventListener("click", (e) => {
      if (e.target.closest("a")) {
        closeDrawer();
      }
    });

    document.addEventListener("lila:aside-loaded", () => {
      drawer.innerHTML = aside.innerHTML;
    });
  }

  // Accessible Copy Buttons for Code Blocks (Invoker Commands + progressive fallback)
  const copyTimers = new WeakMap();
  let lastCopyMessage = "";

  function legacyCopy(text) {
    const previousFocus = document.activeElement;
    const field = Object.assign(document.createElement("textarea"), { value: text });
    field.setAttribute("readonly", "");
    field.style.cssText = "position:fixed;inset-block-start:0;opacity:0";
    document.body.append(field);
    field.select();
    try {
      return document.execCommand("copy");
    } finally {
      field.remove();
      previousFocus?.focus({ preventScroll: true });
    }
  }

  function reportCopy(button, ok) {
    const tip = button.nextElementSibling;
    clearTimeout(copyTimers.get(button));
    button.removeAttribute("data-copied");
    button.removeAttribute("data-failed");
    let message = ok ? "Copied" : "Copy failed";
    if (message === lastCopyMessage) message += "\u00A0";
    lastCopyMessage = message;
    if (tip) tip.textContent = "";
    void button.offsetWidth;
    button.setAttribute(ok ? "data-copied" : "data-failed", "");
    if (tip) {
      requestAnimationFrame(() => {
        tip.textContent = message;
      });
    }
    copyTimers.set(
      button,
      setTimeout(() => {
        button.removeAttribute("data-copied");
        button.removeAttribute("data-failed");
        if (tip) tip.textContent = "";
      }, 2000)
    );
  }

  async function copyCode(button, target) {
    if (!button || !target) return;
    const text = target.matches("input, textarea") ? target.value : target.innerText.trim();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      reportCopy(button, true);
    } catch {
      if (legacyCopy(text)) {
        reportCopy(button, true);
      } else {
        reportCopy(button, false);
      }
    }
  }

  // Register only ONE invocation path
  if ("CommandEvent" in window) {
    document.addEventListener(
      "command",
      (event) => {
        if (event.command === "--copy") {
          copyCode(event.source, event.target);
        }
      },
      true
    );
  } else {
    document.addEventListener("click", (event) => {
      if (event.defaultPrevented) return;
      const button = event.target.closest('button[command="--copy"]');
      if (!button) return;
      const target = document.getElementById(button.getAttribute("commandfor"));
      if (target) copyCode(button, target);
    });
  }

  function createCopyControl(targetId, label) {
    const wrap = document.createElement("span");
    wrap.className = "lila-copy";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "lila-copy-btn";
    btn.setAttribute("command", "--copy");
    btn.setAttribute("commandfor", targetId);
    btn.setAttribute("aria-label", label);
    btn.innerHTML =
      '<svg class="lila-icon-copy" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>' +
      '<svg class="lila-icon-check" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';

    const tip = document.createElement("span");
    tip.className = "lila-copy-tip";
    tip.setAttribute("role", "status");

    wrap.append(btn, tip);
    return wrap;
  }

  function initCopyButtons() {
    const blocks = document.querySelectorAll("pre > code");
    let counter = 0;

    blocks.forEach((code) => {
      const pre = code.parentElement;
      if (!pre || pre.dataset.copyInit) return;
      pre.dataset.copyInit = "1";
      counter += 1;
      const id = code.id || `lila-code-${counter}`;
      code.id = id;

      const card = pre.closest(".bg-gray-900");
      const titleEl = card ? card.querySelector(".editor-title") : null;
      const headerBar = card ? card.querySelector(":scope > .flex.items-center.justify-between") : null;
      const titleText = titleEl ? titleEl.textContent.trim() : "code snippet";
      const control = createCopyControl(id, `Copy ${titleText}`);

      if (headerBar) {
        headerBar.appendChild(control);
      } else {
        const wrapper = document.createElement("div");
        wrapper.className = "lila-copyable";
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.append(pre, control);
      }
    });
  }

  function onReady() {
    applyTheme(getStoredTheme(), false);
    initCopyButtons();
    setTimeout(initDrawer, 50);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", onReady);
  } else {
    onReady();
  }
})();

function lila(component, options) {
  if (component === "snackbar") {
    snackbar(options);
  }
}

function snackbar(options) {
  let snackbarEl = document.getElementById("snackbar");

  if (!snackbarEl) {
    snackbarEl = document.createElement("div");
    snackbarEl.id = "snackbar";
    document.body.appendChild(snackbarEl);
  }

  snackbarEl.className = "show";
  snackbarEl.classList.add(options.type || "info");
  snackbarEl.textContent = options.message || "";

  const duration = options.duration || 3000;
  if (snackbarEl.timeoutId) {
    clearTimeout(snackbarEl.timeoutId);
  }

  snackbarEl.timeoutId = setTimeout(() => {
    snackbarEl.className = "";
  }, duration);
}
