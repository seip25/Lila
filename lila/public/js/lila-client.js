/**
 * Lila Framework Client Runtime v2.0.x
 * Provides client-side SPA routing with View Transitions API,
 * persistent element state, selective React/JS Islands hydration,
 * lightweight global event bus, and modern Tailwind CSS UI components.
 */

/**
 * Escapes any value before inserting it into HTML. Used by the UI components
 * (DataTable, toast, command palette) so database/user content cannot inject
 * markup or scripts.
 */
function lilaEscapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function lilaEscapeAttr(value) {
  return lilaEscapeHtml(value).replace(/`/g, "&#96;");
}

(() => {
  if (typeof window === "undefined" || window.Lila) return;

  /**
   * Global Island component registry.
   */
  window.__LILA_ISLANDS__ = window.__LILA_ISLANDS__ || {};

  /**
   * Global Island root mounter/renderer function.
   */
  window.__LILA_MOUNT__ = window.__LILA_MOUNT__ || null;

  const mountedRoots = new Map();
  const prefetchCache = new Map();
  const prefetchInFlight = new Set();
  const PREFETCH_TTL_MS = 30000;
  const PREFETCH_MAX_ENTRIES = 50;

  function getPrefetchedHtml(url) {
    const entry = prefetchCache.get(url);
    if (!entry) return null;
    if (entry.expiry <= Date.now()) {
      prefetchCache.delete(url);
      return null;
    }
    return entry.html;
  }

  function setPrefetchedHtml(url, html) {
    if (prefetchCache.size >= PREFETCH_MAX_ENTRIES) {
      const oldestKey = prefetchCache.keys().next().value;
      if (oldestKey !== undefined) prefetchCache.delete(oldestKey);
    }
    prefetchCache.set(url, { html, expiry: Date.now() + PREFETCH_TTL_MS });
  }

  const eventListeners = new Map();
  const storeState = new Map();
  const storeListeners = new Map();

  const Lila = {
    emit(event, data) {
      const callbacks = eventListeners.get(event);
      if (callbacks) {
        for (const cb of callbacks) {
          try {
            cb(data);
          } catch (err) {
            console.error(`[LILA EVENT ERROR] Error in listener for "${event}":`, err);
          }
        }
      }
    },

    on(event, callback) {
      if (!eventListeners.has(event)) {
        eventListeners.set(event, new Set());
      }
      eventListeners.get(event).add(callback);
      return () => eventListeners.get(event)?.delete(callback);
    },

    off(event, callback) {
      eventListeners.get(event)?.delete(callback);
    },

    store(key, value) {
      if (arguments.length > 1) {
        storeState.set(key, value);
        const listeners = storeListeners.get(key);
        if (listeners) {
          for (const cb of listeners) {
            try {
              cb(value);
            } catch (err) {
              console.error(`[LILA STORE ERROR] Error in listener for "${key}":`, err);
            }
          }
        }
      }
      return storeState.get(key);
    },

    subscribe(key, callback) {
      if (!storeListeners.has(key)) {
        storeListeners.set(key, new Set());
      }
      storeListeners.get(key).add(callback);
      return () => storeListeners.get(key)?.delete(callback);
    },

    clearPrefetch() {
      prefetchCache.clear();
    },

    onPageLoad(callback) {
      if (typeof callback !== "function") return () => {};
      const handler = (e) => callback(e.detail || { url: window.location.href, initial: false });
      window.addEventListener("lila:page-load", handler);
      if (document.readyState !== "loading") {
        try {
          callback({ url: window.location.href, initial: true });
        } catch (err) {
          console.error("[LILA ON_PAGE_LOAD ERROR]:", err);
        }
      }
      return () => window.removeEventListener("lila:page-load", handler);
    },

    hydrate(container = document) {
      const islands = container.querySelectorAll("[data-island]");
      for (const el of islands) {
        if (el.__lila_mounted__) continue;

        const name = el.getAttribute("data-island");
        const isPersist = el.getAttribute("data-persist") === "true";
        let props = {};

        try {
          const rawProps = el.getAttribute("data-props");
          if (rawProps) props = JSON.parse(rawProps);
        } catch (err) {
          console.warn(`[LILA ISLAND] Failed to parse props for island "${name}":`, err);
        }

        const component = window.__LILA_ISLANDS__[name];
        if (component && typeof window.__LILA_MOUNT__ === "function") {
          try {
            const unmountFn = window.__LILA_MOUNT__(el, component, props);
            el.__lila_mounted__ = true;
            mountedRoots.set(el, {
              unmount: unmountFn,
              persist: isPersist,
              name,
            });
          } catch (err) {
            console.error(`[LILA ISLAND] Error mounting island "${name}":`, err);
          }
        }
      }
    },

    unmountNonPersistent(container = document) {
      for (const [el, item] of mountedRoots.entries()) {
        if (item.persist) continue;
        if (container !== document && !container.contains(el)) continue;
        try {
          if (typeof item.unmount === "function") {
            item.unmount();
          }
        } catch {}
        el.__lila_mounted__ = false;
        mountedRoots.delete(el);
      }
    },

    async renderPartial(url, target, options = {}) {
      const targetEl = typeof target === "string" ? document.querySelector(target) : target;
      if (!targetEl) return false;

      try {
        const res = await fetch(url, {
          headers: {
            "X-Lila-Client-Router": "1",
            "X-Lila-Partial": "1",
          },
          credentials: "include",
        });

        if (!res.ok) return false;

        if (res.redirected && res.url && res.headers.get("X-Lila-Partial") !== "1") {
          await Lila.navigate(res.url);
          return true;
        }

        const html = await res.text();
        // The server always returns a full document; extract the outlet so we
        // never inject <html>/<body>/<head> inside an element.
        let fragment = html;
        try {
          const parsed = new DOMParser().parseFromString(html, "text/html");
          const outlet = parsed.querySelector("[data-lila-outlet]");
          if (outlet) fragment = outlet.innerHTML;
        } catch {}
        const applyPartial = async () => {
          Lila.unmountNonPersistent(targetEl);
          targetEl.innerHTML = fragment;
          await executeScripts(targetEl);
          Lila.hydrate(targetEl);
          if (options.pushUrl) {
            window.history.pushState({}, "", url);
          }
          window.dispatchEvent(
            new CustomEvent("lila:partial-load", { detail: { url, target: targetEl } })
          );
          window.dispatchEvent(
            new CustomEvent("lila:load", { detail: { url, target: targetEl } })
          );
        };

        if (options.transition && document.startViewTransition) {
          await document.startViewTransition(applyPartial).finished;
        } else {
          await applyPartial();
        }
        return true;
      } catch {
        return false;
      }
    },

    async navigate(url, options = {}) {
      try {
        let html = getPrefetchedHtml(url);
        let targetUrl = url;
        if (!html) {
          const res = await fetch(url, {
            headers: { "X-Lila-Client-Router": "1" },
            credentials: "include",
          });
          if (!res.ok) {
            window.location.href = url;
            return;
          }
          if (res.redirected && res.url) {
            try {
              const parsed = new URL(res.url);
              targetUrl = parsed.pathname + parsed.search;
            } catch {}
          }
          html = await res.text();
        } else {
          prefetchCache.delete(url);
        }

        const parser = new DOMParser();
        const nextDoc = parser.parseFromString(html, "text/html");

        if (document.startViewTransition) {
          await document.startViewTransition(() => swapDocument(nextDoc, targetUrl, options)).finished;
        } else {
          await swapDocument(nextDoc, targetUrl, options);
        }
      } catch {
        window.location.href = url;
      }
    },
  };

  async function swapDocument(nextDoc, url, options) {
    // Lets page-scoped resources (LilaWS sockets, timers) clean up before the
    // outlet is replaced. Listeners registered by the *next* page are added
    // after this event, so they are not affected.
    window.dispatchEvent(new CustomEvent("lila:before-swap", { detail: { url } }));
    const currentPersistNodes = new Map();
    const currentPersistElements = document.querySelectorAll('[data-persist="true"]');

    currentPersistElements.forEach((el, index) => {
      const key = el.getAttribute("data-island") || el.getAttribute("data-lila-client") || el.id || `persist-${index}`;
      currentPersistNodes.set(key, el);
    });

    Lila.unmountNonPersistent();

    document.title = nextDoc.title || document.title;
    await updateHeadTags(nextDoc);

    const nextPersistElements = nextDoc.querySelectorAll('[data-persist="true"]');
    nextPersistElements.forEach((nextEl, index) => {
      const key = nextEl.getAttribute("data-island") || nextEl.getAttribute("data-lila-client") || nextEl.id || `persist-${index}`;
      const activeEl = currentPersistNodes.get(key);
      if (activeEl && nextEl.parentNode) {
        syncPersistedLinks(activeEl, nextEl);
        nextEl.parentNode.replaceChild(activeEl, nextEl);
        currentPersistNodes.delete(key);
      }
    });

    const currentOutlet = document.querySelector("[data-lila-outlet]");
    const nextOutlet = nextDoc.querySelector("[data-lila-outlet]");
    const currentLayout = document.body.getAttribute("data-layout");
    const nextLayout = nextDoc.body.getAttribute("data-layout");

    const canSwapOutletOnly =
      currentOutlet &&
      nextOutlet &&
      currentLayout &&
      nextLayout &&
      currentLayout === nextLayout;

    if (canSwapOutletOnly) {
      currentOutlet.innerHTML = nextOutlet.innerHTML;
      await executeScripts(currentOutlet);
      Lila.hydrate(currentOutlet);
    } else {
      // Sync body attributes (classes, styles, layout) so standalone pages like admin login stay centered
      for (const attr of Array.from(nextDoc.body.attributes)) {
        document.body.setAttribute(attr.name, attr.value);
      }
      document.body.innerHTML = nextDoc.body.innerHTML;

      for (const [key, activeEl] of currentPersistNodes.entries()) {
        const placeholder = document.querySelector(
          `[data-persist="true"][data-island="${key}"], [data-persist="true"][data-lila-client="${key}"], [data-persist="true"]#${key}`
        );
        if (placeholder && placeholder.parentNode && placeholder !== activeEl) {
          placeholder.parentNode.replaceChild(activeEl, placeholder);
        }
      }

      await executeScripts(document.body);
      Lila.hydrate();
    }

    if (options.replace) {
      window.history.replaceState({}, "", url);
    } else {
      window.history.pushState({}, "", url);
    }

    if (options.scroll !== false) {
      window.scrollTo(0, 0);
    }

    Lila.hydrate();

    const pageLoadDetail = { url, initial: false };
    window.dispatchEvent(new CustomEvent("lila:navigate", { detail: { url } }));
    window.dispatchEvent(new CustomEvent("lila:page-load", { detail: pageLoadDetail }));
    document.dispatchEvent(new CustomEvent("lila:page-load", { detail: pageLoadDetail }));
    window.dispatchEvent(new CustomEvent("lila:load", { detail: pageLoadDetail }));
  }

  // A persisted element (sidebar, navbar) keeps its DOM state, but its links
  // take the class/aria-current rendered by the server for the new page, so
  // the "active" item follows the navigation.
  function syncPersistedLinks(currentEl, nextEl) {
    const nextLinks = new Map();
    nextEl.querySelectorAll("a[href]").forEach((a) => nextLinks.set(a.getAttribute("href"), a));
    currentEl.querySelectorAll("a[href]").forEach((a) => {
      const fresh = nextLinks.get(a.getAttribute("href"));
      if (!fresh) return;
      a.className = fresh.className;
      if (fresh.hasAttribute("aria-current")) a.setAttribute("aria-current", fresh.getAttribute("aria-current"));
      else a.removeAttribute("aria-current");
    });
  }

  function cloneScript(oldScript) {
    const script = document.createElement("script");
    for (const attr of Array.from(oldScript.attributes)) {
      script.setAttribute(attr.name, attr.value);
    }
    script.textContent = oldScript.textContent;
    return script;
  }

  // Inserts a script and resolves once it ran. External scripts are awaited so
  // the next inline script can use the library (dynamic scripts are async).
  function runScript(script, insert) {
    const isExternal = script.hasAttribute("src");
    const type = (script.getAttribute("type") || "").toLowerCase();
    const executable = !type || type === "module" || type.includes("javascript");
    if (!isExternal || !executable) {
      insert(script);
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      script.async = false;
      script.addEventListener("load", resolve, { once: true });
      script.addEventListener("error", resolve, { once: true });
      insert(script);
    });
  }

  async function executeScripts(container) {
    const scripts = Array.from(container.querySelectorAll("script"));
    for (const oldScript of scripts) {
      if (oldScript.getAttribute("data-persist") === "true") continue;
      const src = oldScript.getAttribute("src") || "";
      if (src.includes("lila-client.js")) continue;
      if (!oldScript.parentNode) continue;
      const newScript = cloneScript(oldScript);
      await runScript(newScript, (el) => oldScript.parentNode && oldScript.parentNode.replaceChild(el, oldScript));
    }
  }

  async function updateHeadTags(nextDoc) {
    const currentMeta = document.head.querySelectorAll("meta[name], meta[property]");
    currentMeta.forEach((el) => el.remove());

    const nextMeta = nextDoc.head.querySelectorAll("meta[name], meta[property]");
    nextMeta.forEach((el) => {
      document.head.appendChild(document.importNode(el, true));
    });

    // Page-specific head assets rendered by render(styles=, scripts=, jsonld=).
    // Identical tags are kept (no re-download / re-execution), others swapped.
    const keep = new Set();
    const nextHeadTags = Array.from(nextDoc.head.querySelectorAll("[data-lila-head]"));
    const nextKeys = new Set(nextHeadTags.map((el) => el.outerHTML));
    document.head.querySelectorAll("[data-lila-head]").forEach((el) => {
      if (nextKeys.has(el.outerHTML)) keep.add(el.outerHTML);
      else el.remove();
    });
    const pendingScripts = [];
    nextHeadTags.forEach((el) => {
      if (keep.has(el.outerHTML)) return;
      if (el.tagName === "SCRIPT") pendingScripts.push(el);
      else document.head.appendChild(document.importNode(el, true));
    });

    const nextLang = nextDoc.documentElement.getAttribute("lang");
    if (nextLang) document.documentElement.setAttribute("lang", nextLang);

    const nextCanonical = nextDoc.head.querySelector("link[rel='canonical']");
    const currentCanonical = document.head.querySelector("link[rel='canonical']");
    if (nextCanonical) {
      if (currentCanonical) {
        currentCanonical.setAttribute("href", nextCanonical.getAttribute("href") || "");
      } else {
        document.head.appendChild(document.importNode(nextCanonical, true));
      }
    } else if (currentCanonical) {
      currentCanonical.remove();
    }

    for (const el of pendingScripts) {
      await runScript(cloneScript(el), (script) => document.head.appendChild(script));
    }
  }

  function isInternalLink(anchor) {
    if (!anchor || anchor.tagName !== "A") return false;
    if (anchor.target && anchor.target !== "_self") return false;
    if (anchor.hasAttribute("download")) return false;
    if (anchor.getAttribute("rel") === "external") return false;
    if (anchor.getAttribute("data-no-router") !== null) return false;
    if (anchor.hasAttribute("data-action")) return false;

    const href = anchor.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("javascript:") || href.startsWith("mailto:") || href.startsWith("tel:")) {
      return false;
    }

    try {
      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin) return false;
      const path = url.pathname.toLowerCase();
      // Exclude API, documentation, and system endpoints from SPA routing
      if (
        path.startsWith("/api") ||
        path.startsWith("/docs") ||
        path.startsWith("/openapi") ||
        path.startsWith("/swagger") ||
        path.startsWith("/_lila") ||
        path.startsWith("/debug")
      ) {
        return false;
      }
      return true;
    } catch {
      return false;
    }
  }

  function canPrefetch(anchor) {
    if (!isInternalLink(anchor)) return false;
    if (anchor.hasAttribute("data-no-prefetch")) return false;
    if (anchor.getAttribute("data-prefetch") === "false") return false;
    if (anchor.hasAttribute("data-no-hover")) return false;
    if (anchor.hasAttribute("data-partial-target")) return false;

    try {
      const url = new URL(anchor.href, window.location.href);
      const pathname = url.pathname.toLowerCase();
      if (
        pathname === "/logout" ||
        pathname.endsWith("/logout") ||
        pathname === "/signout" ||
        pathname.endsWith("/signout") ||
        pathname.startsWith("/api") ||
        pathname.startsWith("/docs") ||
        pathname.startsWith("/openapi") ||
        pathname.startsWith("/swagger")
      ) {
        return false;
      }
    } catch {
      return false;
    }
    return true;
  }

  function initLinkInterception() {
    document.addEventListener("click", (e) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
        return;
      }

      const anchor = e.target.closest("a");
      if (!anchor || !isInternalLink(anchor)) return;

      const partialTarget = anchor.getAttribute("data-partial-target");
      if (partialTarget) {
        e.preventDefault();
        Lila.renderPartial(anchor.href, partialTarget, {
          transition: anchor.getAttribute("data-transition") === "true",
          pushUrl: anchor.getAttribute("data-push-url") === "true",
        });
        return;
      }

      const url = anchor.href;
      if (url === window.location.href) {
        e.preventDefault();
        return;
      }
      // Same page + #hash: let the browser scroll to the anchor.
      try {
        const next = new URL(url, window.location.href);
        if (next.hash && next.pathname === window.location.pathname && next.search === window.location.search) {
          return;
        }
      } catch {}

      e.preventDefault();
      Lila.navigate(url);
    });

    document.addEventListener(
      "mouseover",
      (e) => {
        const anchor = e.target.closest("a");
        if (!anchor || !canPrefetch(anchor)) return;
        const url = anchor.href;
        if (!getPrefetchedHtml(url) && !prefetchInFlight.has(url)) {
          prefetchInFlight.add(url);
          fetch(url, { headers: { "X-Lila-Prefetch": "1" }, credentials: "include" })
            // Never cache redirects (e.g. auth -> /login) under the original URL.
            .then((r) => (r.ok && !r.redirected ? r.text() : null))
            .then((html) => {
              if (html) setPrefetchedHtml(url, html);
            })
            .catch(() => {})
            .finally(() => prefetchInFlight.delete(url));
        }
      },
      { passive: true }
    );

    window.addEventListener("popstate", () => {
      Lila.navigate(window.location.href, { replace: true, scroll: false });
    });
  }

  const $ = (selector, context = document) => context.querySelector(selector);
  const $$ = (selector, context = document) => Array.from(context.querySelectorAll(selector));

  function delegate(selector, type, handler) {
    const listener = (e) => {
      const match = e.target.closest(selector);
      if (match) handler(e, match);
    };
    document.addEventListener(type, listener);
    return () => document.removeEventListener(type, listener);
  }

  Lila.$ = $;
  Lila.$$ = $$;
  Lila.delegate = delegate;
  Lila.event = delegate;

  window.$ = window.$ || $;
  window.$$ = window.$$ || $$;
  window.on = window.on || delegate;
  window.Lila = Lila;

  function initDevReload() {
    if (typeof window === "undefined" || !window.EventSource) return;
    // Injected by render() only when App(debug=True); avoids SSE 404 spam on
    // localhost production servers.
    if (!document.querySelector('meta[name="lila-debug"]')) return;
    if (window.__lilaDevReload) return;
    window.__lilaDevReload = true;
    const isLocalhost =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1" ||
      window.location.hostname === "::1";
    if (!isLocalhost) return;

    let initialBootId = null;
    let es = null;
    let retryTimer = null;

    function cleanup() {
      if (es) {
        try { es.close(); } catch {}
        es = null;
      }
      if (retryTimer) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
    }

    function connect() {
      cleanup();
      try {
        es = new EventSource("/_lila/dev-reload");

        es.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "template") {
              console.log("[Lila] Template/static change detected, reloading page...");
              cleanup();
              window.location.reload();
              return;
            }
            if (data.type === "connected" && data.bootId) {
              if (initialBootId === null) {
                initialBootId = data.bootId;
              } else if (initialBootId !== data.bootId) {
                console.log("[Lila] Server restart detected, reloading page...");
                cleanup();
                window.location.reload();
              }
            }
          } catch {}
        };

        es.onerror = () => {
          cleanup();
          clearTimeout(retryTimer);
          retryTimer = setTimeout(connect, 400);
        };
      } catch {
        clearTimeout(retryTimer);
        retryTimer = setTimeout(connect, 600);
      }
    }

    window.addEventListener("beforeunload", cleanup);
    connect();
  }

  function triggerInitialLoad() {
    try {
      const savedTheme = localStorage.getItem("lila-theme");
      if (savedTheme === "dark" || savedTheme === "light") {
        document.documentElement.setAttribute("data-theme", savedTheme);
        document.documentElement.classList.toggle("dark", savedTheme === "dark");
      }
    } catch {}
    initLinkInterception();
    Lila.hydrate();
    initDevReload();
    const detail = { url: window.location.href, initial: true };
    window.dispatchEvent(new CustomEvent("lila:page-load", { detail }));
    document.dispatchEvent(new CustomEvent("lila:page-load", { detail }));
    window.dispatchEvent(new CustomEvent("lila:load", { detail }));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", triggerInitialLoad);
  } else {
    triggerInitialLoad();
  }
})();

/**
 * Lila UI Components v2.0.0 (Tailwind CSS Native)
 */
function lila(component, options) {
  if (typeof component === "object") {
    options = component;
    component = "snackbar";
  }

  // 1. Toast
  if (component === "toast") {
    const position = (options && options.position) || "bottom-right";
    const posClasses = {
      "bottom-right": "bottom-4 right-4 items-end",
      "bottom-left": "bottom-4 left-4 items-start",
      "top-right": "top-4 right-4 items-end",
      "top-left": "top-4 left-4 items-start",
      "top-center": "top-4 left-1/2 -translate-x-1/2 items-center",
    };
    const chosenPos = posClasses[position] || posClasses["bottom-right"];

    let container = document.querySelector(`.lila-toast-container[data-pos="${position}"]`);
    if (!container) {
      container = document.createElement("div");
      container.className = `lila-toast-container fixed z-[9999] flex flex-col gap-3 p-4 pointer-events-none max-w-sm w-full ${chosenPos}`;
      container.setAttribute("data-pos", position);
      document.body.appendChild(container);
    }

    const type = (options && options.type) || "info";
    const typeThemes = {
      success: {
        classes: "bg-emerald-50/95 dark:bg-emerald-950/90 border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-100",
        icon: '<span class="text-emerald-500 font-bold">✓</span>',
      },
      error: {
        classes: "bg-red-50/95 dark:bg-red-950/90 border-red-200 dark:border-red-800 text-red-900 dark:text-red-100",
        icon: '<span class="text-red-500 font-bold">✕</span>',
      },
      danger: {
        classes: "bg-red-50/95 dark:bg-red-950/90 border-red-200 dark:border-red-800 text-red-900 dark:text-red-100",
        icon: '<span class="text-red-500 font-bold">✕</span>',
      },
      warning: {
        classes: "bg-amber-50/95 dark:bg-amber-950/90 border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-100",
        icon: '<span class="text-amber-500 font-bold">⚠</span>',
      },
      info: {
        classes: "bg-white/95 dark:bg-slate-900/95 border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-100",
        icon: '<span class="text-blue-500 font-bold">ℹ</span>',
      },
    };
    const theme = typeThemes[type] || typeThemes["info"];

    const toastEl = document.createElement("div");
    toastEl.className = `pointer-events-auto flex items-start justify-between gap-3 w-full p-4 rounded-2xl shadow-lg border backdrop-blur-md transition-all duration-300 transform translate-y-0 opacity-100 ${theme.classes}`;

    const title = options && options.title ? `<div class="font-bold text-sm leading-tight">${lilaEscapeHtml(options.title)}</div>` : "";
    const desc = options && options.description ? `<div class="text-xs opacity-90 mt-0.5">${lilaEscapeHtml(options.description)}</div>` : "";

    toastEl.innerHTML = `
      <div class="flex items-start gap-2.5">
        <div class="text-base leading-none mt-0.5">${theme.icon}</div>
        <div class="flex-1">${title}${desc}</div>
      </div>
      <button class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-base leading-none p-1 cursor-pointer transition-colors" aria-label="Dismiss">&times;</button>
    `;

    const closeBtn = toastEl.querySelector("button");
    closeBtn.addEventListener("click", () => dismissToast(toastEl));
    container.appendChild(toastEl);

    const duration = options && options.duration !== undefined ? options.duration : 4000;
    if (duration > 0) {
      setTimeout(() => dismissToast(toastEl), duration);
    }
  }

  // 2. Snackbar
  if (component === "snackbar") {
    let snackbarEl = document.getElementById("lila-snackbar");
    if (!snackbarEl) {
      snackbarEl = document.createElement("div");
      snackbarEl.id = "lila-snackbar";
      document.body.appendChild(snackbarEl);
    }

    const type = (options && options.type) || "info";
    const bg = type === "error" || type === "danger" ? "bg-red-600 text-white" :
               type === "success" ? "bg-emerald-600 text-white" :
               type === "warning" ? "bg-amber-600 text-white" :
               "bg-slate-900 text-white dark:bg-white dark:text-slate-900";

    snackbarEl.className = `fixed bottom-6 left-1/2 -translate-x-1/2 z-[9999] px-5 py-3 rounded-full shadow-2xl font-semibold text-sm flex items-center gap-2 transition-all duration-300 transform translate-y-0 opacity-100 ${bg}`;
    snackbarEl.textContent = (options && options.message) || "";

    const duration = (options && options.duration) || 3000;
    if (snackbarEl.timeoutId) clearTimeout(snackbarEl.timeoutId);
    snackbarEl.timeoutId = setTimeout(() => {
      snackbarEl.className = "fixed bottom-6 left-1/2 -translate-x-1/2 z-[9999] opacity-0 pointer-events-none transition-all duration-300";
    }, duration);
  }

  // 3. Tab
  if (component === "tab") {
    const targetId = options && options.id;
    if (!targetId) return;
    const targetContent = document.getElementById(targetId);
    if (!targetContent) return;
    const tabsContainer = targetContent.closest(".tabs");
    if (!tabsContainer) return;

    tabsContainer.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active", "block"));
    tabsContainer.querySelectorAll(".tab-content").forEach((c) => c.classList.add("hidden"));
    tabsContainer.querySelectorAll(".tab-trigger").forEach((t) => t.classList.remove("active", "border-blue-600", "text-blue-600"));

    targetContent.classList.remove("hidden");
    targetContent.classList.add("active", "block");

    const matching = Array.from(tabsContainer.querySelectorAll(".tab-trigger")).find(
      (t) => t.getAttribute("data-tab-target") === targetId || t.getAttribute("href") === `#${targetId}`
    );
    if (matching) {
      matching.classList.add("active", "border-blue-600", "text-blue-600");
    }
  }

  // 4. Command Palette
  if (component === "command") {
    const action = (options && options.action) || "toggle";
    let backdrop = document.querySelector(".lila-command-backdrop");
    if (!backdrop) {
      backdrop = createCommandPaletteModal();
    }
    const isOpen = backdrop.classList.contains("open");
    if (action === "open" || (action === "toggle" && !isOpen)) {
      backdrop.classList.add("open");
      backdrop.classList.remove("hidden");
      const input = backdrop.querySelector(".command-input");
      if (input) {
        input.value = "";
        setTimeout(() => input.focus(), 50);
      }
    } else if (action === "close" || (action === "toggle" && isOpen)) {
      backdrop.classList.remove("open");
      backdrop.classList.add("hidden");
    }
  }

  // 5. Drawer: lila('drawer', { id, action: 'open'|'close'|'toggle', orientation })
  if (component === "drawer") {
    cleanupOrphanedBackdrops();
    const id = options && String(options.id || "").replace(/^#/, "");
    if (!id) return;
    const drawerEl = document.getElementById(id);
    if (!drawerEl) return;
    return lilaDrawer(drawerEl, (options && options.action) || "toggle", options || {});
  }

  // 6. Carousel
  if (component === "carousel") {
    // lila('carousel', { selector: '.carousel', autoplay: 4000 }) -> array of controllers
    // lila('carousel', { el: element }) -> one controller
    if (options && options.el) return initSingleCarousel(options.el, options);
    const selector = (options && options.selector) || ".carousel, [data-carousel]";
    return Array.from(document.querySelectorAll(selector)).map((c) => initSingleCarousel(c, options || {}));
  }

  // 7. DataTable
  if (component === "datatable" || component === "table") {
    const containerId = (options && (options.container || options.id)) || "datatable";
    return new ResponsiveDataTable(containerId, options);
  }
}

function dismissToast(toastEl) {
  if (!toastEl || toastEl.isDismissing) return;
  toastEl.isDismissing = true;
  toastEl.style.opacity = "0";
  toastEl.style.transform = "translateY(-8px) scale(0.96)";
  setTimeout(() => {
    if (toastEl.parentNode) toastEl.remove();
  }, 200);
}

function createCommandPaletteModal() {
  const backdrop = document.createElement("div");
  backdrop.className = "lila-command-backdrop hidden fixed inset-0 z-[9998] bg-slate-950/50 backdrop-blur-sm flex items-start justify-center pt-20 p-4";
  backdrop.innerHTML = `
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl max-w-xl w-full overflow-hidden transition-all">
      <div class="flex items-center gap-3 px-4 py-3.5 border-b border-slate-100 dark:border-slate-800">
        <span class="text-slate-400">🔍</span>
        <input type="text" class="command-input flex-1 bg-transparent text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none" placeholder="Type a command or search..." />
        <kbd class="px-2 py-0.5 text-[10px] font-bold rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-500">ESC</kbd>
      </div>
      <div class="command-list max-h-80 overflow-y-auto p-2 space-y-1">
        <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 py-1.5">Navigation</div>
        <div class="command-item flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer" data-navigate="/">
          <span>Home</span><kbd class="text-xs text-slate-400">↵</kbd>
        </div>
        <div class="command-item flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer" data-navigate="/docs">
          <span>Documentation</span><kbd class="text-xs text-slate-400">↵</kbd>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);

  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) lila("command", { action: "close" });
  });

  const input = backdrop.querySelector(".command-input");
  input.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase().trim();
    backdrop.querySelectorAll(".command-item").forEach((item) => {
      item.style.display = item.textContent.toLowerCase().includes(q) ? "flex" : "none";
    });
  });

  backdrop.addEventListener("click", (e) => {
    const item = e.target.closest(".command-item");
    if (item && item.getAttribute("data-navigate")) {
      const path = item.getAttribute("data-navigate");
      lila("command", { action: "close" });
      if (window.Lila) window.Lila.navigate(path);
      else window.location.href = path;
    }
  });

  return backdrop;
}

function cleanupOrphanedBackdrops() {
  document.querySelectorAll(".drawer-backdrop[data-for]").forEach((b) => {
    const targetId = b.getAttribute("data-for");
    if (!document.getElementById(targetId)) b.remove();
  });
}

/**
 * Drawer with orientation. Markup:
 *
 *   <button data-drawer="#menu">Menu</button>
 *   <aside id="menu" data-drawer-panel data-orientation="left" data-size="18rem" class="bg-white dark:bg-slate-900 p-6">
 *     <button data-drawer-close>&times;</button> ...
 *   </aside>
 *
 * data-orientation: left | right (default) | top | bottom (aliases: up, down,
 * start, end). Closes with the backdrop, Escape, [data-drawer-close] and on SPA
 * navigation. Focus moves into the drawer and back to the trigger.
 */
const LILA_DRAWER_SIDES = { left: "left", start: "left", right: "right", end: "right", top: "top", up: "top", bottom: "bottom", down: "bottom" };

function lilaDrawerSide(el, options) {
  const raw = String((options && (options.orientation || options.side)) || el.getAttribute("data-orientation") || el.getAttribute("data-side") || "right").toLowerCase();
  return LILA_DRAWER_SIDES[raw] || "right";
}

function lilaPrepareDrawer(el, side) {
  if (el._lilaDrawerSide === side) return;
  el._lilaDrawerSide = side;
  el.classList.add("drawer");
  el.classList.remove("translate-x-full", "-translate-x-full");
  const size = el.getAttribute("data-size");
  const horizontal = side === "left" || side === "right";
  Object.assign(el.style, {
    position: "fixed",
    zIndex: "9999",
    top: side === "bottom" ? "auto" : "0",
    bottom: side === "top" ? "auto" : "0",
    left: side === "right" ? "auto" : "0",
    right: side === "left" ? "auto" : "0",
    width: horizontal ? (size || "20rem") : "100%",
    maxWidth: horizontal ? "85vw" : "100%",
    height: horizontal ? "100%" : (size || "auto"),
    maxHeight: horizontal ? "100%" : "85vh",
    overflowY: "auto",
    transition: "transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
    boxShadow: "0 0 24px rgba(0, 0, 0, 0.15)",
  });
  el.setAttribute("role", el.getAttribute("role") || "dialog");
  el.setAttribute("aria-modal", "true");
  if (!el.classList.contains("open")) {
    el.style.transform = lilaDrawerHidden(side);
    el.setAttribute("aria-hidden", "true");
    el.inert = true;
  }
}

function lilaDrawerHidden(side) {
  return { left: "translateX(-100%)", right: "translateX(100%)", top: "translateY(-100%)", bottom: "translateY(100%)" }[side];
}

function lilaDrawer(el, action = "toggle", options = {}) {
  const id = el.id;
  const side = lilaDrawerSide(el, options);
  lilaPrepareDrawer(el, side);

  let overlay = el._lilaOverlay && el._lilaOverlay.isConnected ? el._lilaOverlay
    : id ? document.querySelector(`.drawer-backdrop[data-for="${CSS.escape(id)}"]`) : null;
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.className = "drawer-backdrop fixed inset-0 z-[9998] bg-slate-950/50 backdrop-blur-sm transition-opacity duration-300 opacity-0 pointer-events-none";
    overlay.style.pointerEvents = "none";
    if (id) overlay.setAttribute("data-for", id);
    document.body.appendChild(overlay);
    overlay.addEventListener("click", () => lilaDrawer(el, "close"));
  }
  el._lilaOverlay = overlay;

  const isOpen = el.classList.contains("open");
  const open = action === "open" || (action === "toggle" && !isOpen);
  if (open && !isOpen) {
    el._lilaReturnFocus = document.activeElement;
    el.classList.add("open");
    el.style.transform = "none";
    el.inert = false;
    el.setAttribute("aria-hidden", "false");
    overlay.classList.add("open", "opacity-100", "pointer-events-auto");
    overlay.classList.remove("opacity-0", "pointer-events-none");
    overlay.style.pointerEvents = "auto";
    document.body.style.overflow = "hidden";
    if (id) document.querySelectorAll(`[data-drawer="#${CSS.escape(id)}"], [data-drawer="${CSS.escape(id)}"], [data-drawer-target="${CSS.escape(id)}"]`)
      .forEach((t) => t.setAttribute("aria-expanded", "true"));
    const focusable = el.querySelector("[autofocus], a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex='-1'])");
    if (focusable) setTimeout(() => focusable.focus(), 50);
    el.dispatchEvent(new CustomEvent("lila:drawer-open", { bubbles: true }));
  } else if (!open && isOpen) {
    el.classList.remove("open");
    el.style.transform = lilaDrawerHidden(side);
    el.setAttribute("aria-hidden", "true");
    el.inert = true;
    overlay.classList.remove("open", "opacity-100", "pointer-events-auto");
    overlay.classList.add("opacity-0", "pointer-events-none");
    overlay.style.pointerEvents = "none";
    if (!document.querySelector(".drawer.open")) document.body.style.overflow = "";
    if (id) document.querySelectorAll(`[data-drawer="#${CSS.escape(id)}"], [data-drawer="${CSS.escape(id)}"], [data-drawer-target="${CSS.escape(id)}"]`)
      .forEach((t) => t.setAttribute("aria-expanded", "false"));
    if (el._lilaReturnFocus && el._lilaReturnFocus.isConnected) el._lilaReturnFocus.focus();
    el.dispatchEvent(new CustomEvent("lila:drawer-close", { bubbles: true }));
  }
  return el;
}

/**
 * Small declarative utilities (all optional, no setup):
 *   data-dropdown="#menu"            toggle a menu; closes on outside click / Escape
 *   data-toggle-class="a b" [data-toggle-target="#el"]   toggle classes (default: itself)
 *   data-remove ["#el"]              remove an element (default: closest [data-removable] or parent)
 *   data-password-toggle="#input"    show / hide a password
 *   data-tab-target="panelId"        tabs (.tabs > .tab-trigger + .tab-content)
 *   data-scroll="#id" | data-scroll  smooth scroll to an element (or the top)
 *   data-autosubmit[="ms"]           submit the form on change / after typing
 *   form[data-navigate]              GET form -> SPA navigation with the query string
 *   data-char-count="#counter"       "n / maxlength" counter
 *   data-filter="#list"              filter list items by text
 *   <time data-local-time datetime="..." data-format="date|time|datetime|relative">
 *   data-copy="text | #selector" [data-copy-message="Copied!"]
 */
function lilaTargets(value, fallback) {
  if (typeof value === "string" && value.trim()) return Array.from(document.querySelectorAll(value));
  return fallback ? [fallback] : [];
}

function lilaCloseDropdowns(except) {
  document.querySelectorAll("[data-dropdown][aria-expanded='true']").forEach((trigger) => {
    if (trigger === except) return;
    trigger.setAttribute("aria-expanded", "false");
    lilaTargets(trigger.getAttribute("data-dropdown")).forEach((menu) => {
      menu.hidden = true;
      menu.classList.add("hidden");
    });
  });
}

async function lilaCopyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Non-secure origins (http://) have no clipboard API: legacy fallback.
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch {}
    area.remove();
    return ok;
  }
}

function lilaUpdateCharCount(field) {
  const counter = document.querySelector(field.getAttribute("data-char-count"));
  if (!counter) return;
  const max = field.getAttribute("maxlength");
  counter.textContent = max ? `${field.value.length} / ${max}` : String(field.value.length);
  counter.classList.toggle("text-red-500", !!max && field.value.length >= Number(max));
}

function lilaApplyFilter(input) {
  const term = input.value.trim().toLowerCase();
  lilaTargets(input.getAttribute("data-filter")).forEach((list) => {
    const items = list.querySelectorAll("[data-filter-item]").length
      ? list.querySelectorAll("[data-filter-item]")
      : list.children;
    let visible = 0;
    Array.from(items).forEach((item) => {
      const match = !term || item.textContent.toLowerCase().includes(term);
      item.hidden = !match;
      if (match) visible++;
    });
    const empty = list.querySelector("[data-filter-empty]") || document.querySelector(`[data-filter-empty="${CSS.escape(input.getAttribute("data-filter"))}"]`);
    if (empty) empty.hidden = visible > 0;
  });
}

function lilaFormatTime(el) {
  const raw = el.getAttribute("datetime") || el.getAttribute("data-local-time") || el.textContent;
  const date = new Date(raw);
  if (!raw || isNaN(date.getTime())) return;
  const lang = document.documentElement.lang || undefined;
  const format = el.getAttribute("data-format") || "datetime";
  if (format === "relative") {
    const diff = (date.getTime() - Date.now()) / 1000;
    const units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60], ["second", 1]];
    const [unit, secs] = units.find(([, s]) => Math.abs(diff) >= s) || ["second", 1];
    try {
      el.textContent = new Intl.RelativeTimeFormat(lang, { numeric: "auto" }).format(Math.round(diff / secs), unit);
    } catch { el.textContent = date.toLocaleString(lang); }
  } else {
    const opts = format === "date" ? { dateStyle: "medium" } : format === "time" ? { timeStyle: "short" } : { dateStyle: "medium", timeStyle: "short" };
    try { el.textContent = new Intl.DateTimeFormat(lang, opts).format(date); } catch { el.textContent = date.toLocaleString(lang); }
  }
  if (!el.title) el.title = date.toISOString();
}

function lilaInitUtilities(root = document) {
  root.querySelectorAll("[data-char-count]").forEach(lilaUpdateCharCount);
  root.querySelectorAll("time[data-local-time], [data-local-time]").forEach(lilaFormatTime);
  root.querySelectorAll("[data-filter]").forEach((input) => { if (input.value) lilaApplyFilter(input); });
  root.querySelectorAll("[data-drawer-panel], [data-orientation].drawer").forEach((panel) => lilaPrepareDrawer(panel, lilaDrawerSide(panel)));
}

if (typeof window !== "undefined" && !window.__LILA_UTILS_BOUND__) {
  window.__LILA_UTILS_BOUND__ = true;

  document.addEventListener("click", (e) => {
    if (e.button !== 0) return;
    const t = e.target;

    const drawerTrigger = t.closest("[data-drawer]:not([data-drawer-panel])");
    if (drawerTrigger) {
      e.preventDefault();
      const panel = document.querySelector(drawerTrigger.getAttribute("data-drawer").startsWith("#")
        ? drawerTrigger.getAttribute("data-drawer")
        : `#${CSS.escape(drawerTrigger.getAttribute("data-drawer"))}`);
      if (panel) lilaDrawer(panel, drawerTrigger.getAttribute("data-drawer-action") || "toggle",
        drawerTrigger.hasAttribute("data-orientation") ? { orientation: drawerTrigger.getAttribute("data-orientation") } : {});
      return;
    }
    const drawerClose = t.closest("[data-drawer-close]");
    if (drawerClose) {
      const panel = drawerClose.closest(".drawer") || document.querySelector(drawerClose.getAttribute("data-drawer-close"));
      if (panel) { e.preventDefault(); lilaDrawer(panel, "close"); }
      return;
    }
    // Links inside an open drawer close it when they navigate.
    const drawerLink = t.closest(".drawer.open a[href]:not([href^='#'])");
    if (drawerLink && !drawerLink.hasAttribute("data-keep-open")) lilaDrawer(drawerLink.closest(".drawer"), "close");

    const dropdownTrigger = t.closest("[data-dropdown]");
    if (dropdownTrigger) {
      e.preventDefault();
      const open = dropdownTrigger.getAttribute("aria-expanded") !== "true";
      lilaCloseDropdowns(dropdownTrigger);
      dropdownTrigger.setAttribute("aria-expanded", String(open));
      lilaTargets(dropdownTrigger.getAttribute("data-dropdown")).forEach((menu) => {
        menu.hidden = !open;
        menu.classList.toggle("hidden", !open);
      });
      return;
    }
    if (!t.closest("[data-dropdown-menu], [data-dropdown-keep]")) lilaCloseDropdowns(null);

    const classToggler = t.closest("[data-toggle-class]");
    if (classToggler) {
      const classes = classToggler.getAttribute("data-toggle-class").split(/\s+/).filter(Boolean);
      lilaTargets(classToggler.getAttribute("data-toggle-target"), classToggler)
        .forEach((el) => classes.forEach((c) => el.classList.toggle(c)));
      if (classToggler.tagName === "A") e.preventDefault();
      return;
    }

    const remover = t.closest("[data-remove]");
    if (remover) {
      e.preventDefault();
      const targets = lilaTargets(remover.getAttribute("data-remove"), remover.closest("[data-removable]") || remover.parentElement);
      targets.forEach((el) => {
        el.style.transition = "opacity 200ms ease";
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 200);
      });
      return;
    }

    const pwd = t.closest("[data-password-toggle]");
    if (pwd) {
      e.preventDefault();
      lilaTargets(pwd.getAttribute("data-password-toggle")).forEach((input) => {
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        pwd.setAttribute("aria-pressed", String(show));
        const label = pwd.getAttribute(show ? "data-hide-text" : "data-show-text");
        if (label) pwd.textContent = label;
      });
      return;
    }

    const tab = t.closest("[data-tab-target]");
    if (tab) {
      e.preventDefault();
      lila("tab", { id: tab.getAttribute("data-tab-target").replace(/^#/, "") });
      return;
    }

    const scroller = t.closest("[data-scroll]");
    if (scroller) {
      e.preventDefault();
      const target = scroller.getAttribute("data-scroll");
      const el = target ? document.querySelector(target) : null;
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      else window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    lilaCloseDropdowns(null);
    document.querySelectorAll(".drawer.open").forEach((d) => lilaDrawer(d, "close"));
  });

  document.addEventListener("input", (e) => {
    const el = e.target;
    if (!el || !el.hasAttribute) return;
    if (el.hasAttribute("data-char-count")) lilaUpdateCharCount(el);
    if (el.hasAttribute("data-filter")) lilaApplyFilter(el);
    const form = el.form;
    const auto = el.hasAttribute("data-autosubmit") ? el : form && form.hasAttribute("data-autosubmit") ? form : null;
    if (auto && form && /^(text|search|email|number|tel|url)$/.test(el.type || "") ) {
      const delay = Number(auto.getAttribute("data-autosubmit")) || 400;
      clearTimeout(form._lilaAutoTimer);
      form._lilaAutoTimer = setTimeout(() => form.requestSubmit(), delay);
    }
  });

  document.addEventListener("change", (e) => {
    const el = e.target;
    const form = el && el.form;
    if (!form) return;
    if (/^(text|search|email|number|tel|url|password)$/.test(el.type || "") || el.tagName === "TEXTAREA") return;
    if (el.hasAttribute("data-autosubmit") || form.hasAttribute("data-autosubmit")) form.requestSubmit();
  });

  // GET forms with data-navigate: filters/search as SPA navigation.
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (!form.hasAttribute || !form.hasAttribute("data-navigate") || form.hasAttribute("data-lila-form")) return;
    e.preventDefault();
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(form).entries()) {
      if (value !== "" && typeof value === "string") params.append(key, value);
    }
    const base = form.getAttribute("action") || window.location.pathname;
    const url = params.toString() ? `${base}?${params}` : base;
    if (window.Lila && Lila.navigate) Lila.navigate(url, { scroll: form.getAttribute("data-scroll-top") !== "false" });
    else window.location.href = url;
  });

  window.addEventListener("lila:before-swap", () => {
    lilaCloseDropdowns(null);
    document.querySelectorAll(".drawer.open").forEach((d) => lilaDrawer(d, "close"));
    document.body.style.overflow = "";
  });
  window.addEventListener("lila:page-load", () => lilaInitUtilities());
  window.addEventListener("lila:partial-load", (e) => lilaInitUtilities((e.detail && e.detail.target) || document));
  if (document.readyState !== "loading") lilaInitUtilities();
  else document.addEventListener("DOMContentLoaded", () => lilaInitUtilities());
}

/**
 * Carousel (scroll-snap + Tailwind). Markup:
 *
 *   <div class="carousel" data-lila-carousel data-autoplay="5000" data-loop="true">
 *     <div class="carousel-track">
 *       <div class="carousel-item basis-full md:basis-1/2">...</div>
 *     </div>
 *     <button class="carousel-prev">‹</button><button class="carousel-next">›</button>
 *     <div class="carousel-indicators"></div>
 *   </div>
 *
 * Or from Jinja: {{ carousel(slides, autoplay=5000) }}. Auto-initialized on
 * every page load / SPA navigation; native touch swipe via scroll-snap.
 */
function lilaCarouselOption(carousel, opts, name, fallback) {
  // JS option > data-carousel-<name> > data-<name> > fallback
  if (opts && opts[name] !== undefined) return opts[name];
  const camel = "carousel" + name.charAt(0).toUpperCase() + name.slice(1);
  const data = carousel.dataset || {};
  if (data[camel] !== undefined) return data[camel];
  if (data[name] !== undefined) return data[name];
  return fallback;
}

/**
 * Plain-HTML carousel: only data attributes are required, the track, arrows
 * and dots are created automatically.
 *
 *   <div data-carousel data-carousel-autoplay="4000" data-carousel-loop="true"
 *        data-carousel-arrows="true" data-carousel-indicators="true" class="h-72">
 *     <div data-carousel-slide><img src="/img/1.webp" class="w-full h-full object-cover"></div>
 *     <div data-carousel-slide class="md:basis-1/2">Card</div>
 *   </div>
 */
function lilaPrepareCarousel(carousel) {
  carousel.classList.add("carousel", "relative", "overflow-hidden");
  let track = carousel.querySelector(".carousel-track, [data-carousel-track]");
  const slides = Array.from(carousel.querySelectorAll("[data-carousel-slide]"));
  if (!track && slides.length) {
    track = document.createElement("div");
    track.className = "carousel-track h-full";
    slides[0].parentNode.insertBefore(track, slides[0]);
    slides.forEach((slide) => track.appendChild(slide));
  }
  if (!track) return null;
  track.classList.add("carousel-track");
  slides.forEach((slide) => {
    slide.classList.add("carousel-item", "shrink-0");
    if (!/(^|\s)(basis-|w-)/.test(slide.className)) slide.classList.add("basis-full");
  });

  const arrowCls = "absolute top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full bg-white/80 dark:bg-slate-900/80 shadow-md backdrop-blur flex items-center justify-center text-xl font-bold cursor-pointer hover:bg-white dark:hover:bg-slate-800 disabled:opacity-40 transition";
  const wantArrows = String(lilaCarouselOption(carousel, {}, "arrows", "true")) !== "false";
  if (wantArrows && !carousel.querySelector(".carousel-prev, [data-carousel-prev]")) {
    carousel.insertAdjacentHTML("beforeend",
      `<button type="button" class="carousel-prev ${arrowCls} left-3" aria-label="Previous">&lsaquo;</button>` +
      `<button type="button" class="carousel-next ${arrowCls} right-3" aria-label="Next">&rsaquo;</button>`);
  }
  const wantDots = String(lilaCarouselOption(carousel, {}, "indicators", "true")) !== "false";
  if (wantDots && !carousel.querySelector(".carousel-indicators, [data-carousel-indicators]")) {
    carousel.insertAdjacentHTML("beforeend",
      '<div class="carousel-indicators absolute bottom-3 inset-x-0 z-10 flex justify-center gap-2"></div>');
  }
  return track;
}

function initSingleCarousel(carousel, opts = {}) {
  if (carousel._lila_initialized) return carousel._lila_carousel;
  const track = carousel.hasAttribute("data-carousel")
    ? lilaPrepareCarousel(carousel)
    : carousel.querySelector(".carousel-track, [data-carousel-track]");
  if (!track) return null;
  const items = Array.from(track.querySelectorAll(".carousel-item, .carousel-card, [data-carousel-slide]"));
  if (items.length === 0) return null;
  carousel._lila_initialized = true;

  const autoplay = Number(lilaCarouselOption(carousel, opts, "autoplay", 0)) || 0;
  const loop = String(lilaCarouselOption(carousel, opts, "loop", "true")) !== "false";
  const pauseOnHover = String(lilaCarouselOption(carousel, opts, "pause", "true")) !== "false";
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const prevBtn = carousel.querySelector(".carousel-prev, [data-carousel-prev]");
  const nextBtn = carousel.querySelector(".carousel-next, [data-carousel-next]");
  let indicators = carousel.querySelector(".carousel-indicators, [data-carousel-indicators]");
  let current = 0;
  let timer = null;
  let paused = false;

  carousel.setAttribute("role", carousel.getAttribute("role") || "region");
  carousel.setAttribute("aria-roledescription", "carousel");
  if (!carousel.hasAttribute("tabindex")) carousel.setAttribute("tabindex", "0");
  items.forEach((item, i) => {
    item.setAttribute("role", "group");
    item.setAttribute("aria-roledescription", "slide");
    item.setAttribute("aria-label", `${i + 1} / ${items.length}`);
  });

  const dots = [];
  if (indicators && opts.indicators !== false) {
    indicators.innerHTML = "";
    items.forEach((_, i) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = "carousel-dot w-2.5 h-2.5 rounded-full bg-slate-300 dark:bg-slate-600 transition-all cursor-pointer";
      dot.setAttribute("aria-label", `Slide ${i + 1}`);
      dot.addEventListener("click", () => go(i));
      indicators.appendChild(dot);
      dots.push(dot);
    });
  }

  function paint() {
    dots.forEach((dot, i) => {
      const active = i === current;
      dot.classList.toggle("bg-blue-600", active);
      dot.classList.toggle("w-6", active);
      dot.classList.toggle("bg-slate-300", !active);
      dot.setAttribute("aria-current", active ? "true" : "false");
    });
    if (!loop) {
      if (prevBtn) prevBtn.disabled = current === 0;
      if (nextBtn) nextBtn.disabled = current >= items.length - 1;
    }
  }

  function go(index) {
    if (loop) index = (index + items.length) % items.length;
    else index = Math.max(0, Math.min(index, items.length - 1));
    current = index;
    track.scrollTo({ left: items[index].offsetLeft - track.offsetLeft, behavior: reduceMotion ? "auto" : "smooth" });
    paint();
  }

  // Keep the active index in sync with manual swipes / trackpad scrolling.
  let scrollRaf = 0;
  track.addEventListener("scroll", () => {
    cancelAnimationFrame(scrollRaf);
    scrollRaf = requestAnimationFrame(() => {
      const left = track.scrollLeft + track.offsetLeft;
      let best = 0;
      let bestDist = Infinity;
      items.forEach((item, i) => {
        const dist = Math.abs(item.offsetLeft - left);
        if (dist < bestDist) { bestDist = dist; best = i; }
      });
      if (best !== current) { current = best; paint(); }
    });
  }, { passive: true });

  if (prevBtn) prevBtn.addEventListener("click", () => { go(current - 1); restart(); });
  if (nextBtn) nextBtn.addEventListener("click", () => { go(current + 1); restart(); });
  carousel.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { e.preventDefault(); go(current - 1); restart(); }
    if (e.key === "ArrowRight") { e.preventDefault(); go(current + 1); restart(); }
  });

  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
  }
  function start() {
    stop();
    if (!autoplay || reduceMotion || items.length < 2) return;
    timer = setInterval(() => {
      // Removed by an SPA navigation: release the timer.
      if (!carousel.isConnected) { stop(); return; }
      if (!paused && !document.hidden) go(current + 1);
    }, Math.max(1500, autoplay));
  }
  function restart() { if (timer) start(); }

  if (pauseOnHover) {
    carousel.addEventListener("mouseenter", () => { paused = true; });
    carousel.addEventListener("mouseleave", () => { paused = false; });
  }
  carousel.addEventListener("focusin", () => { paused = true; });
  carousel.addEventListener("focusout", () => { paused = false; });

  paint();
  start();

  const api = {
    go, next: () => go(current + 1), prev: () => go(current - 1), start, stop,
    get index() { return current; }, get length() { return items.length; },
  };
  carousel._lila_carousel = api;
  track.addEventListener("scrollend", () => {
    carousel.dispatchEvent(new CustomEvent("lila:carousel-change", { detail: { index: current }, bubbles: true }));
  });
  return api;
}

/**
 * Declarative components (Jinja helpers ``datatable()`` / ``carousel()``).
 * Runs on the first load, after each SPA navigation and partial swap.
 */
function lilaResolveFn(value) {
  if (typeof value === "function") return value;
  if (typeof value !== "string" || !value) return false;
  return value.split(".").reduce((obj, key) => (obj ? obj[key] : undefined), window) || false;
}

function lilaInitDataTable(el) {
  if (el._lila_datatable) return el._lila_datatable;
  const cfgEl = document.getElementById(`${el.id}-config`);
  let cfg = {};
  try {
    cfg = cfgEl ? JSON.parse(cfgEl.textContent || "{}") : {};
  } catch (err) {
    console.error("[LILA DATATABLE] Invalid config for", el.id, err);
    return null;
  }
  const options = Object.assign({}, cfg);
  delete options.url;
  delete options.dataKey;
  ["edit", "delete"].forEach((key) => {
    if (options[key]) options[key] = lilaResolveFn(options[key]);
  });

  const build = (rows) => {
    options.data = Array.isArray(rows) ? rows : [];
    el._lila_datatable = new ResponsiveDataTable(el, options);
    el.dispatchEvent(new CustomEvent("lila:datatable-ready", { detail: el._lila_datatable, bubbles: true }));
    return el._lila_datatable;
  };

  if (cfg.url && typeof Http === "function") {
    el._lila_datatable = true; // guard against double init while loading
    Http(cfg.url)
      .then((res) => {
        const rows = cfg.dataKey ? cfg.dataKey.split(".").reduce((o, k) => (o ? o[k] : undefined), res) : res;
        build(Array.isArray(rows) ? rows : (res && Array.isArray(res.data) ? res.data : []));
      })
      .catch((err) => {
        el._lila_datatable = null;
        el.innerHTML = '<p class="p-6 text-center text-sm text-red-500">Could not load data.</p>';
        console.error("[LILA DATATABLE]", err);
      });
    return null;
  }
  return build(cfg.data || []);
}

function lilaInitComponents(root = document) {
  root.querySelectorAll("[data-lila-carousel], [data-carousel]").forEach((el) => initSingleCarousel(el));
  root.querySelectorAll("[data-lila-datatable]").forEach((el) => lilaInitDataTable(el));
}

if (typeof window !== "undefined") {
  window.lilaInitComponents = lilaInitComponents;
  const runInit = (e) => lilaInitComponents((e && e.detail && e.detail.target) || document);
  window.addEventListener("lila:page-load", runInit);
  window.addEventListener("lila:partial-load", runInit);
  if (document.readyState !== "loading") lilaInitComponents();
  else document.addEventListener("DOMContentLoaded", () => lilaInitComponents());
}

if (!window.__LILA_UI_BOUND__) {
  window.__LILA_UI_BOUND__ = true;

  document.addEventListener("click", (e) => {
    // Copy to clipboard
    const copyTrigger = e.target.closest("[data-copy]");
    if (copyTrigger) {
      e.preventDefault();
      const targetAttr = copyTrigger.getAttribute("data-copy");
      let textToCopy = targetAttr;
      if (targetAttr && (targetAttr.startsWith("#") || targetAttr.startsWith("."))) {
        const el = document.querySelector(targetAttr);
        if (el) textToCopy = el.value !== undefined ? el.value : (el.innerText || el.textContent);
      }
      if (textToCopy) {
        lilaCopyText(textToCopy.trim()).then((ok) => {
          const custom = copyTrigger.getAttribute("data-copy-message");
          if (copyTrigger.hasAttribute("data-copy-silent")) return;
          if (custom) {
            lila("snackbar", { message: ok ? custom : "Copy failed", type: ok ? "success" : "error", duration: 2000 });
          } else {
            lila("toast", {
              title: ok ? "Copied" : "Copy failed",
              description: textToCopy.length > 40 ? textToCopy.substring(0, 40) + "..." : textToCopy,
              type: ok ? "success" : "error",
              duration: 2500,
            });
          }
        });
      }
      return;
    }

    // Confirm dialog
    const confirmTrigger = e.target.closest("[data-confirm]");
    if (confirmTrigger) {
      const msg = confirmTrigger.getAttribute("data-confirm") || "Are you sure?";
      if (!window.confirm(msg)) {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }
    }

    // Modal dialogs
    const modalTrigger = e.target.closest('[data-toggle="modal"], [data-modal-target]');
    if (modalTrigger) {
      e.preventDefault();
      const selector = modalTrigger.getAttribute("data-modal-target") || modalTrigger.getAttribute("data-target");
      if (selector) {
        const dialog = document.querySelector(selector);
        if (dialog && typeof dialog.showModal === "function") dialog.showModal();
      }
      return;
    }

    const dismissTrigger = e.target.closest('[data-dismiss="modal"], [data-close-modal]');
    if (dismissTrigger) {
      e.preventDefault();
      const dialog = dismissTrigger.closest("dialog") || document.querySelector(dismissTrigger.getAttribute("data-target") || "");
      if (dialog && typeof dialog.close === "function") dialog.close();
      return;
    }

    // Theme toggle
    const themeTrigger = e.target.closest('[data-toggle="theme"]');
    if (themeTrigger) {
      e.preventDefault();
      const html = document.documentElement;
      const current = html.getAttribute("data-theme") || (html.classList.contains("dark") ? "dark" : "light");
      const next = current === "dark" ? "light" : "dark";
      html.setAttribute("data-theme", next);
      html.classList.toggle("dark", next === "dark");

      try {
        localStorage.setItem("lila-theme", next);
      } catch {}
      return;
    }

    // Drawer triggers
    const drawerTrigger = e.target.closest("[data-drawer-target]");
    if (drawerTrigger) {
      const id = drawerTrigger.getAttribute("data-drawer-target");
      lila("drawer", { id, action: "toggle" });
    }
  });

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      lila("command", { action: "toggle" });
    } else if (e.key === "Escape") {
      lila("command", { action: "close" });
    }
  });
}

/**
 * Declarative forms & actions (htmx-style, zero JS per page).
 *
 *   <form action="/api/login" method="post" data-lila-form data-snackbar data-redirect="/dashboard">
 *     <input name="email" type="email" required>
 *     <div data-message hidden></div>
 *     <button type="submit">Sign in</button>
 *   </form>
 *
 *   <button data-action="/api/items/3" data-method="DELETE" data-confirm="Delete?"
 *           data-toast data-refresh="#items-table">Delete</button>
 *
 * Flow: HTML5 validation (required/min/max/pattern...) -> buttons disabled with a
 * spinner -> Http() with CSRF -> feedback (snackbar/toast/[data-message]),
 * field errors from 422 responses -> redirect/reset/reload/target swap/refresh/
 * callback. Buttons are always re-enabled (also after a timeout).
 */
const LILA_SPINNER =
  '<svg class="lila-spinner animate-spin -ml-0.5 mr-2 h-4 w-4 inline-block align-[-2px]" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg>';

const LILA_MESSAGE_STYLES = {
  success: "rounded-xl border px-4 py-3 text-sm font-medium bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900 text-emerald-800 dark:text-emerald-200",
  error: "rounded-xl border px-4 py-3 text-sm font-medium bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-900 text-red-800 dark:text-red-200",
  info: "rounded-xl border px-4 py-3 text-sm font-medium bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-900 text-blue-800 dark:text-blue-200",
};

function lilaAttr(el, name, fallback = null) {
  if (!el || !el.hasAttribute(name)) return fallback;
  const value = el.getAttribute(name);
  return value === "" ? true : value;
}

function lilaIsOn(el, name) {
  const value = lilaAttr(el, name);
  return value !== null && value !== "false";
}

function lilaSetBusy(buttons, busyButton) {
  const restore = [];
  buttons.forEach((btn) => {
    if (!btn || btn.disabled) return;
    const state = { btn, html: btn.innerHTML, value: btn.value };
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    if (btn === busyButton && btn.getAttribute("data-loading") !== "false") {
      const text = btn.getAttribute("data-loading-text");
      if (btn.tagName === "INPUT") {
        if (text) btn.value = text;
      } else {
        btn.innerHTML = LILA_SPINNER + (text ? lilaEscapeHtml(text) : btn.innerHTML);
      }
    }
    restore.push(state);
  });
  return () => restore.forEach(({ btn, html, value }) => {
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
    if (btn.tagName === "INPUT") btn.value = value;
    else btn.innerHTML = html;
  });
}

function lilaFormBody(form, submitter) {
  const fd = new FormData(form);
  if (submitter && submitter.name) fd.append(submitter.name, submitter.value);
  const hasFile = Array.from(form.querySelectorAll('input[type="file"]')).some((i) => i.files && i.files.length);
  if (hasFile || (form.getAttribute("enctype") || "").includes("multipart")) return { form: fd };
  const data = {};
  for (const [key, value] of fd.entries()) {
    if (key in data) data[key] = [].concat(data[key], value); // checkbox groups / multi-select
    else data[key] = value;
  }
  // Unchecked boxes with data-unchecked send a value too (e.g. "0").
  form.querySelectorAll('input[type="checkbox"][data-unchecked]').forEach((box) => {
    if (box.name && !box.checked && !(box.name in data)) data[box.name] = box.getAttribute("data-unchecked");
  });
  return { json: data };
}

function lilaResult(res, error) {
  // Normalizes any API answer into { ok, message, data, errors, type }.
  const data = error ? (error.data || { message: error.message }) : res;
  let ok = !error;
  if (data && typeof data === "object" && !Array.isArray(data)) {
    if (data.success === false || data.ok === false || data.error === true) ok = false;
  }
  let message = "";
  if (typeof data === "string") message = "";
  else if (data && typeof data === "object") {
    message = data.message || data.msg || data.detail || (typeof data.error === "string" ? data.error : "") || "";
  }
  if (!message && error) message = error.status === 422 ? "Please check the highlighted fields." : (error.message || "Request failed");
  const errors = data && typeof data === "object" && Array.isArray(data.errors) ? data.errors : [];
  const type = (data && typeof data === "object" && data.type) || (ok ? "success" : "error");
  return { ok, message: String(message || ""), data, errors, type, status: error ? error.status : 200 };
}

function lilaClearFieldErrors(form) {
  if (!form) return;
  form.querySelectorAll("[data-lila-field-error]").forEach((el) => el.remove());
  form.querySelectorAll('[aria-invalid="true"]').forEach((el) => el.removeAttribute("aria-invalid"));
}

function lilaShowFieldErrors(form, errors) {
  if (!form || !errors.length) return;
  let first = null;
  errors.forEach((item) => {
    if (!item || typeof item !== "object") return;
    Object.entries(item).forEach(([name, msg]) => {
      const field = form.querySelector(`[name="${CSS.escape(name)}"]`);
      if (!field) return;
      field.setAttribute("aria-invalid", "true");
      const holder = form.querySelector(`[data-error-for="${CSS.escape(name)}"]`);
      if (holder) {
        holder.textContent = String(msg);
        holder.hidden = false;
        holder.classList.remove("hidden");
      } else {
        const p = document.createElement("p");
        p.setAttribute("data-lila-field-error", "");
        p.className = "mt-1 text-xs font-medium text-red-600 dark:text-red-400";
        p.textContent = String(msg);
        field.insertAdjacentElement("afterend", p);
      }
      if (!first) first = field;
    });
  });
  if (first && typeof first.focus === "function") first.focus();
}

function lilaShowMessage(el, result) {
  const box = (() => {
    const sel = lilaAttr(el, "data-message");
    if (typeof sel === "string") return document.querySelector(sel);
    return el.tagName === "FORM" ? el.querySelector("[data-message]") : null;
  })();
  if (!box || !result.message) return;
  if (!box._lilaBaseClass) box._lilaBaseClass = box.className.replace(/\b(hidden|d-none)\b/g, "").trim();
  const style = LILA_MESSAGE_STYLES[result.ok ? (result.type === "info" ? "info" : "success") : "error"];
  box.className = `${box._lilaBaseClass} ${style}`.trim();
  box.setAttribute("role", result.ok ? "status" : "alert");
  box.textContent = result.message;
  box.hidden = false;
}

function lilaFeedback(el, result) {
  if (!result.message) return;
  const type = result.ok ? (result.type === "info" ? "info" : "success") : "error";
  if (lilaIsOn(el, "data-snackbar")) lila("snackbar", { message: result.message, type });
  if (lilaIsOn(el, "data-toast")) {
    const okTitle = lilaAttr(el, "data-toast");
    const errTitle = lilaAttr(el, "data-toast-error");
    const title = result.ok
      ? (typeof okTitle === "string" ? okTitle : "OK")
      : (typeof errTitle === "string" ? errTitle : "Error");
    lila("toast", { title, description: result.message, type });
  }
  lilaShowMessage(el, result);
}

function lilaSwap(el, result) {
  const targetSel = lilaAttr(el, "data-target");
  if (typeof targetSel !== "string") return;
  const target = document.querySelector(targetSel);
  if (!target) return;
  const data = result.data;
  const html = typeof data === "string" ? data : data && typeof data.html === "string" ? data.html : null;
  const mode = lilaAttr(el, "data-swap", "inner");
  if (html === null) {
    if (data && typeof data === "object") target.textContent = result.message || "";
    return;
  }
  if (mode === "text") target.textContent = html;
  else if (mode === "outer") target.outerHTML = html;
  else if (mode === "append") target.insertAdjacentHTML("beforeend", html);
  else if (mode === "prepend") target.insertAdjacentHTML("afterbegin", html);
  else target.innerHTML = html;
  if (mode !== "text") {
    const root = mode === "outer" ? document : target;
    lilaInitComponents(root);
    lilaInitUtilities(root);
  }
}

function lilaRefresh(selector) {
  // Re-renders declarative components: datatable(url=...) re-fetches its data.
  String(selector).split(",").map((x) => x.trim()).filter(Boolean).forEach((sel) => {
    document.querySelectorAll(sel).forEach((el) => {
      if (el.hasAttribute("data-lila-datatable")) {
        const dt = el._lila_datatable;
        if (dt && typeof dt.destroy === "function") dt.destroy();
        el._lila_datatable = null;
        lilaInitDataTable(el);
      } else if (typeof el.refresh === "function") {
        el.refresh();
      }
      el.dispatchEvent(new CustomEvent("lila:refresh", { bubbles: true }));
    });
  });
}

async function lilaRequest(el, { url, method, json, form, submitter }) {
  const confirmMsg = lilaAttr(el, "data-confirm");
  if (el.tagName === "FORM" && typeof confirmMsg === "string" && !window.confirm(confirmMsg)) return null;

  const buttons = el.tagName === "FORM"
    ? Array.from(el.querySelectorAll('button[type="submit"], button:not([type]), input[type="submit"]'))
        .concat(el.id ? Array.from(document.querySelectorAll(`[form="${CSS.escape(el.id)}"]`)) : [])
    : [el];
  const busyButton = submitter || (el.tagName === "FORM" ? buttons[0] : el);
  const release = lilaSetBusy(buttons, busyButton);
  const timeoutMs = Number(lilaAttr(el, "data-timeout", 20000)) || 20000;
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = setTimeout(() => { if (controller) controller.abort(); release(); }, timeoutMs);
  el.setAttribute("aria-busy", "true");
  lilaClearFieldErrors(el.tagName === "FORM" ? el : null);
  el.dispatchEvent(new CustomEvent("lila:request", { detail: { url, method }, bubbles: true }));

  let result;
  try {
    const res = await Http(url, method, json || false, form || false, { "X-Lila-Action": "1" }, { signal: controller && controller.signal });
    result = lilaResult(res, null);
  } catch (error) {
    if (error && error.name === "AbortError") error.message = "The server took too long to answer.";
    result = lilaResult(null, error);
  } finally {
    clearTimeout(timer);
    release();
    el.removeAttribute("aria-busy");
  }

  if (!result.ok && el.tagName === "FORM") lilaShowFieldErrors(el, result.errors);
  lilaFeedback(el, result);
  el.dispatchEvent(new CustomEvent(result.ok ? "lila:success" : "lila:error", { detail: result, bubbles: true }));

  const callbackName = lilaAttr(el, "data-callback");
  if (typeof callbackName === "string") {
    const fn = lilaResolveFn(callbackName);
    if (typeof fn === "function") {
      try { fn(result.data, el, result); } catch (err) { console.error("[LILA ACTION] callback error:", err); }
    } else {
      console.warn(`[LILA ACTION] data-callback "${callbackName}" is not a global function`);
    }
  }
  if (!result.ok) return result;

  lilaSwap(el, result);
  const refresh = lilaAttr(el, "data-refresh");
  if (typeof refresh === "string") lilaRefresh(refresh);
  if (el.tagName === "FORM" && lilaIsOn(el, "data-reset")) {
    // data-reset -> whole form; data-reset="password,password_2" -> only those fields
    const names = lilaAttr(el, "data-reset");
    if (typeof names === "string") {
      names.split(",").map((n) => n.trim()).filter(Boolean).forEach((name) => {
        el.querySelectorAll(`[name="${CSS.escape(name)}"]`).forEach((field) => {
          if (field.type === "checkbox" || field.type === "radio") field.checked = field.defaultChecked;
          else field.value = "";
        });
      });
    } else {
      el.reset();
    }
  }

  const redirect = (typeof lilaAttr(el, "data-redirect") === "string" && lilaAttr(el, "data-redirect")) ||
    (result.data && typeof result.data === "object" && (result.data.redirect || result.data.redirect_url));
  if (redirect) {
    const go = () => (window.Lila && Lila.navigate && !lilaIsOn(el, "data-no-router") ? Lila.navigate(redirect) : (window.location.href = redirect));
    const delay = Number(lilaAttr(el, "data-redirect-delay", result.message ? 600 : 0)) || 0;
    delay ? setTimeout(go, delay) : go();
  } else if (lilaIsOn(el, "data-reload")) {
    if (window.Lila && Lila.navigate) Lila.navigate(window.location.href, { replace: true, scroll: false });
    else window.location.reload();
  }
  return result;
}

function lilaSubmitForm(form, submitter) {
  if (form.getAttribute("aria-busy") === "true") return null;
  // <input name="confirm" data-match="password" data-match-message="Passwords do not match">
  form.querySelectorAll("[data-match]").forEach((input) => {
    const other = form.querySelector(`[name="${CSS.escape(input.getAttribute("data-match"))}"]`);
    const mismatch = other && other.value !== input.value;
    input.setCustomValidity(mismatch ? (input.getAttribute("data-match-message") || "Values do not match") : "");
  });
  if (!lilaIsOn(form, "data-novalidate") && !form.noValidate && !form.checkValidity()) {
    form.reportValidity();
    return null;
  }
  const url = (submitter && submitter.getAttribute("formaction")) || form.getAttribute("action") || window.location.pathname;
  const method = (lilaAttr(form, "data-method") || (submitter && submitter.getAttribute("formmethod")) || form.getAttribute("method") || "POST").toUpperCase();
  const body = lilaFormBody(form, submitter);
  if (method === "GET" && body.json) {
    const qs = new URLSearchParams(body.json).toString();
    return lilaRequest(form, { url: qs ? `${url}${url.includes("?") ? "&" : "?"}${qs}` : url, method, submitter });
  }
  return lilaRequest(form, { url, method, json: body.json, form: body.form, submitter });
}

function lilaRunAction(el) {
  if (el.getAttribute("aria-busy") === "true" || el.disabled) return null;
  const url = lilaAttr(el, "data-action");
  if (typeof url !== "string") return null;
  const method = String(lilaAttr(el, "data-method", "POST")).toUpperCase();
  let json = false;
  const raw = lilaAttr(el, "data-body");
  if (typeof raw === "string") {
    try { json = JSON.parse(raw); } catch { console.error("[LILA ACTION] data-body must be valid JSON:", raw); return null; }
  }
  const include = lilaAttr(el, "data-include");
  if (typeof include === "string") {
    const source = document.querySelector(include);
    if (source) {
      const extra = source.tagName === "FORM" ? lilaFormBody(source).json || {} :
        Object.fromEntries(Array.from(source.querySelectorAll("[name]")).map((i) => [i.name, i.value]));
      json = Object.assign({}, extra, json || {});
    }
  }
  if (method === "GET" && json) {
    const qs = new URLSearchParams(json).toString();
    return lilaRequest(el, { url: `${url}${url.includes("?") ? "&" : "?"}${qs}`, method });
  }
  return lilaRequest(el, { url, method, json: json || (method === "GET" ? false : {}) });
}

const LILA_FORM_SELECTOR = "form[data-lila-form], form[data-snackbar], form[data-toast], form[data-target], form[data-redirect]";

if (typeof window !== "undefined" && !window.__LILA_ACTIONS_BOUND__) {
  window.__LILA_ACTIONS_BOUND__ = true;
  document.addEventListener("submit", (e) => {
    const form = e.target.closest ? e.target.closest(LILA_FORM_SELECTOR) : null;
    if (!form || form.hasAttribute("data-native")) return;
    e.preventDefault();
    lilaSubmitForm(form, e.submitter || null);
  });
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0) return;
    // <button data-toggle-hidden="#panel"> shows/hides an element (hidden attr or class)
    const toggler = e.target.closest("[data-toggle-hidden]");
    if (toggler) {
      e.preventDefault();
      document.querySelectorAll(toggler.getAttribute("data-toggle-hidden")).forEach((target) => {
        const isHidden = target.hidden || target.classList.contains("hidden");
        target.hidden = !isHidden;
        target.classList.toggle("hidden", !isHidden);
        toggler.setAttribute("aria-expanded", String(isHidden));
      });
      return;
    }
    const el = e.target.closest("[data-action]:not(form)");
    if (!el) return;
    e.preventDefault();
    lilaRunAction(el);
  });
  // Clear a field's error as soon as the user edits it.
  document.addEventListener("input", (e) => {
    const field = e.target;
    if (field && field.hasAttribute && field.hasAttribute("data-match")) field.setCustomValidity("");
    if (!field || field.getAttribute("aria-invalid") !== "true") return;
    field.removeAttribute("aria-invalid");
    const next = field.nextElementSibling;
    if (next && next.hasAttribute("data-lila-field-error")) next.remove();
  });
}

/**
 * Modern ResponsiveDataTable with pure Tailwind CSS
 */
class ResponsiveDataTable {
  constructor(containerId, options = {}) {
    this.container = typeof containerId === "string" ? document.getElementById(containerId) : containerId;
    if (!this.container) return;

    this.options = {
      data: [],
      columns: [],
      rowsPerPage: 10,
      search: true,
      pagination: true,
      headerTitles: {},
      summaryFields: ["id"],
      idKey: "id",
      edit: false,
      delete: false,
      breakpoint: 768,
      ...options,
    };

    this.currentPage = 1;
    this.filteredData = [...this.options.data];
    this.isMobile = window.innerWidth < this.options.breakpoint;
    this._onResize = () => {
      const wasMobile = this.isMobile;
      this.isMobile = window.innerWidth < this.options.breakpoint;
      if (wasMobile !== this.isMobile) this.updateTable();
    };
    window.addEventListener("resize", this._onResize);
    // SPA navigation removed the table: drop the global resize listener.
    this._onPageLoad = () => {
      if (this.container && !this.container.isConnected) this.destroy();
    };
    window.addEventListener("lila:page-load", this._onPageLoad);
    this.init();
  }

  destroy() {
    if (this._onResize) {
      window.removeEventListener("resize", this._onResize);
      this._onResize = null;
    }
    if (this._onPageLoad) {
      window.removeEventListener("lila:page-load", this._onPageLoad);
      this._onPageLoad = null;
    }
    if (this.container) this.container.innerHTML = "";
  }

  init() {
    this.renderContainer();
    this.updateTable();
    if (this.options.search) this.setupSearch();
  }

  renderContainer() {
    this.container.innerHTML = `
      <section class="w-full flex flex-col gap-4">
        ${
          this.options.search
            ? `<div class="flex items-center justify-between">
                <input type="search" class="datatable-search-input w-full sm:w-72 px-4 py-2.5 text-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-slate-800 dark:text-slate-100 transition-all" placeholder="Search records..." aria-label="Search" />
              </div>`
            : ""
        }
        <div class="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
          <table class="datatable-table hidden w-full text-sm text-left border-collapse"></table>
          <div class="datatable-mobile p-3"></div>
        </div>
        ${this.options.pagination ? `<nav class="datatable-pagination flex items-center justify-center gap-1.5 py-2"></nav>` : ""}
      </section>
    `;
  }

  updateTable() {
    const table = this.container.querySelector(".datatable-table");
    const mobileView = this.container.querySelector(".datatable-mobile");
    if (!table || !mobileView) return;

    if (this.isMobile) {
      table.classList.add("hidden");
      mobileView.classList.remove("hidden");
      this.renderMobileView(mobileView);
    } else {
      table.classList.remove("hidden");
      mobileView.classList.add("hidden");
      this.renderDesktopTable(table);
    }

    if (this.options.pagination) this.renderPagination();
  }

  renderDesktopTable(table) {
    const theadRows = this.options.columns.map((col) => {
      const title = this.options.headerTitles[col.key] || col.title || col.key;
      return `<th class="px-4 py-3.5 font-bold">${lilaEscapeHtml(title)}</th>`;
    }).join("");

    const actionsHeader = this.options.edit || this.options.delete ? '<th class="px-4 py-3.5 font-bold text-right">Actions</th>' : "";

    const startIndex = (this.currentPage - 1) * this.options.rowsPerPage;
    const pageItems = this.filteredData.slice(startIndex, startIndex + this.options.rowsPerPage);
    const idKey = this.options.idKey || "id";

    const tbodyRows = pageItems.map((item) => {
      const cells = this.options.columns.map((col) => {
        const val = item[col.key];
        return `<td class="px-4 py-3.5 text-slate-700 dark:text-slate-300 align-middle">${val !== undefined && val !== null ? lilaEscapeHtml(val) : "-"}</td>`;
      }).join("");

      let actionBtns = "";
      if (this.options.edit || this.options.delete) {
        actionBtns = `<td class="px-4 py-3.5 text-right align-middle"><div class="flex items-center justify-end gap-2">`;
        if (this.options.edit) {
          actionBtns += `<button class="datatable-btn-edit px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-all cursor-pointer" data-id="${lilaEscapeAttr(item[idKey])}">Edit</button>`;
        }
        if (this.options.delete) {
          actionBtns += `<button class="datatable-btn-delete px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-500/10 text-red-600 dark:text-red-400 hover:bg-red-500 hover:text-white transition-all cursor-pointer" data-id="${lilaEscapeAttr(item[idKey])}">Delete</button>`;
        }
        actionBtns += `</div></td>`;
      }

      return `<tr class="border-b border-slate-100 dark:border-slate-800/60 hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">${cells}${actionBtns}</tr>`;
    }).join("");

    table.innerHTML = `
      <thead><tr class="border-b border-slate-200 dark:border-slate-800 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 bg-slate-50/60 dark:bg-slate-900/50">${theadRows}${actionsHeader}</tr></thead>
      <tbody>${tbodyRows || '<tr><td colspan="100%" class="p-8 text-center text-slate-400">No records found</td></tr>'}</tbody>
    `;

    this.bindActionEvents(table);
  }

  renderMobileView(container) {
    const startIndex = (this.currentPage - 1) * this.options.rowsPerPage;
    const pageItems = this.filteredData.slice(startIndex, startIndex + this.options.rowsPerPage);

    if (pageItems.length === 0) {
      container.innerHTML = '<div class="p-6 text-center text-slate-400">No records found</div>';
      return;
    }

    container.innerHTML = pageItems.map((item) => {
      const summaryText = this.options.summaryFields.map((k) => item[k]).filter((v) => v !== undefined && v !== null && v !== "").map(lilaEscapeHtml).join(" • ");
      const details = this.options.columns
        .filter((c) => !this.options.summaryFields.includes(c.key))
        .map((c) => {
          const title = this.options.headerTitles[c.key] || c.title || c.key;
          const raw = item[c.key];
          const shown = raw !== undefined && raw !== null && raw !== "" ? lilaEscapeHtml(raw) : "-";
          return `<div class="flex items-center justify-between py-1 text-xs"><dt class="font-bold text-slate-400 uppercase">${lilaEscapeHtml(title)}</dt><dd class="text-slate-700 dark:text-slate-200 font-medium">${shown}</dd></div>`;
        }).join("");
      const idKey = this.options.idKey || "id";

      return `
        <article class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 mb-3 shadow-sm">
          <h3 class="font-bold text-sm text-slate-900 dark:text-slate-100 pb-2 border-b border-slate-100 dark:border-slate-800 mb-2">${summaryText || "Item"}</h3>
          <dl class="space-y-1 mb-3">${details}</dl>
          <div class="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            ${this.options.edit ? `<button class="datatable-btn-edit px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200" data-id="${lilaEscapeAttr(item[idKey])}">Edit</button>` : ""}
            ${this.options.delete ? `<button class="datatable-btn-delete px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-500/10 text-red-600 dark:text-red-400" data-id="${lilaEscapeAttr(item[idKey])}">Delete</button>` : ""}
          </div>
        </article>
      `;
    }).join("");

    this.bindActionEvents(container);
  }

  bindActionEvents(root) {
    const idKey = this.options.idKey || "id";
    root.querySelectorAll(".datatable-btn-edit").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const id = btn.getAttribute("data-id");
        const item = this.options.data.find((d) => String(d[idKey]) === String(id));
        if (typeof this.options.edit === "function") this.options.edit(e, item || id);
      });
    });

    root.querySelectorAll(".datatable-btn-delete").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const id = btn.getAttribute("data-id");
        const item = this.options.data.find((d) => String(d[idKey]) === String(id));
        if (typeof this.options.delete === "function") this.options.delete(e, item || id);
      });
    });
  }

  renderPagination() {
    const nav = this.container.querySelector(".datatable-pagination");
    if (!nav) return;
    const pageCount = Math.ceil(this.filteredData.length / this.options.rowsPerPage);
    if (pageCount <= 1) {
      nav.innerHTML = "";
      return;
    }

    const baseClass = "px-3.5 py-2 text-xs font-bold rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-40 disabled:pointer-events-none transition-all cursor-pointer";
    const activeClass = "px-3.5 py-2 text-xs font-bold rounded-xl bg-blue-600 text-white shadow-sm cursor-pointer";

    let html = `<button class="${baseClass}" ${this.currentPage === 1 ? "disabled" : ""} data-page="${this.currentPage - 1}">«</button>`;
    for (let i = 1; i <= pageCount; i++) {
      html += `<button class="${i === this.currentPage ? activeClass : baseClass}" data-page="${i}">${i}</button>`;
    }
    html += `<button class="${baseClass}" ${this.currentPage === pageCount ? "disabled" : ""} data-page="${this.currentPage + 1}">»</button>`;

    nav.innerHTML = html;
    nav.querySelectorAll("button[data-page]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const p = parseInt(btn.getAttribute("data-page"), 10);
        if (p >= 1 && p <= pageCount) {
          this.currentPage = p;
          this.updateTable();
        }
      });
    });
  }

  setupSearch() {
    const input = this.container.querySelector(".datatable-search-input");
    if (!input) return;
    input.addEventListener("input", (e) => {
      const term = e.target.value.toLowerCase().trim();
      this.filteredData = this.options.data.filter((item) =>
        this.options.columns.some((col) => String(item[col.key] || "").toLowerCase().includes(term))
      );
      this.currentPage = 1;
      this.updateTable();
    });
  }

  updateData(newData) {
    this.options.data = newData;
    this.filteredData = [...newData];
    this.currentPage = 1;
    this.updateTable();
  }
}

/**
 * Universal Http request helper with automated CSRF and prefetch cache clearance.
 */
async function Http(url = "/", method = "GET", body = false, bodyForm = false, headers = {}, opts = {}) {
  const csrfEl =
    document.querySelector('meta[name="csrf-token"]') ||
    document.getElementById("csrf") ||
    document.querySelector('input[name="_csrf"]');
  const csrfToken = csrfEl ? csrfEl.getAttribute("content") || csrfEl.value : null;

  const mergedHeaders = { Accept: "application/json", ...headers };
  if (csrfToken) {
    mergedHeaders["X-CSRF-Token"] = csrfToken;
  }

  const upperMethod = String(method || "GET").toUpperCase();
  const options = { method: upperMethod, headers: mergedHeaders, credentials: "include" };
  if (opts && opts.signal) options.signal = opts.signal;

  if (bodyForm) {
    if (csrfToken && bodyForm instanceof FormData && !bodyForm.has("_csrf")) {
      bodyForm.append("_csrf", csrfToken);
    }
    options.body = bodyForm;
  } else if (body) {
    const payload = csrfToken ? { ...body, _csrf: csrfToken, csrf: csrfToken } : body;
    options.body = JSON.stringify(payload);
    if (!mergedHeaders["Content-Type"] && !mergedHeaders["content-type"]) {
      mergedHeaders["Content-Type"] = "application/json";
    }
  }

  if (upperMethod !== "GET" && window.Lila && typeof window.Lila.clearPrefetch === "function") {
    window.Lila.clearPrefetch();
  }

  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";

  if (!response.ok) {
    let errorData = null;
    try {
      if (contentType.includes("application/json")) {
        errorData = await response.json();
      } else {
        const text = await response.text();
        errorData = { message: text ? text.slice(0, 300) : `HTTP Error ${response.status}` };
      }
    } catch {
      errorData = { message: `HTTP Error ${response.status}: ${response.statusText}` };
    }
    const error = new Error(
      errorData.message || errorData.msg || `HTTP Error ${response.status}: ${response.statusText}`
    );
    error.status = response.status;
    error.data = errorData;
    throw error;
  }

  if (response.status === 204) return null;
  if (contentType.includes("application/json")) return await response.json();
  return await response.text();
}

if (typeof window !== "undefined") {
  window.ResponsiveDataTable = ResponsiveDataTable;
  window.Http = Http;
  window.lila = lila;
  window.Lila.ui = lila;
  window.Lila.escape = lilaEscapeHtml;
  window.Lila.submit = (form, submitter) => lilaSubmitForm(typeof form === "string" ? document.querySelector(form) : form, submitter);
  window.Lila.action = (el) => lilaRunAction(typeof el === "string" ? document.querySelector(el) : el);
  window.Lila.refresh = lilaRefresh;
  window.Lila.drawer = (el, action, opts) => lilaDrawer(typeof el === "string" ? document.querySelector(el) : el, action, opts);
  window.Lila.copy = lilaCopyText;
}
