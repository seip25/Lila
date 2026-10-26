/**
 * Lila Framework Client Runtime v2.0.0
 * Provides client-side SPA routing with View Transitions API,
 * persistent element state, selective React/JS Islands hydration,
 * lightweight global event bus, and modern Tailwind CSS UI components.
 */
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
        const applyPartial = () => {
          Lila.unmountNonPersistent(targetEl);
          targetEl.innerHTML = html;
          executeScripts(targetEl);
          Lila.hydrate(targetEl);
          if (options.pushUrl) {
            window.history.pushState({}, "", url);
          }
          window.dispatchEvent(
            new CustomEvent("lila:partial-load", { detail: { url, target: targetEl } })
          );
        };

        if (options.transition && document.startViewTransition) {
          await document.startViewTransition(applyPartial).finished;
        } else {
          applyPartial();
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
          await document.startViewTransition(() => {
            swapDocument(nextDoc, targetUrl, options);
          }).finished;
        } else {
          swapDocument(nextDoc, targetUrl, options);
        }
      } catch {
        window.location.href = url;
      }
    },
  };

  function swapDocument(nextDoc, url, options) {
    const currentPersistNodes = new Map();
    const currentPersistElements = document.querySelectorAll('[data-persist="true"]');

    currentPersistElements.forEach((el, index) => {
      const key = el.getAttribute("data-island") || el.getAttribute("data-lila-client") || el.id || `persist-${index}`;
      currentPersistNodes.set(key, el);
    });

    Lila.unmountNonPersistent();

    document.title = nextDoc.title || document.title;
    updateHeadTags(nextDoc);

    const nextPersistElements = nextDoc.querySelectorAll('[data-persist="true"]');
    nextPersistElements.forEach((nextEl, index) => {
      const key = nextEl.getAttribute("data-island") || nextEl.getAttribute("data-lila-client") || nextEl.id || `persist-${index}`;
      const activeEl = currentPersistNodes.get(key);
      if (activeEl && nextEl.parentNode) {
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
      executeScripts(currentOutlet);
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

      executeScripts(document.body);
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
  }

  function executeScripts(container) {
    const scripts = Array.from(container.querySelectorAll("script"));
    for (const oldScript of scripts) {
      if (oldScript.getAttribute("data-persist") === "true") continue;
      const src = oldScript.getAttribute("src") || "";
      if (src.includes("lila-client.js")) continue;

      const newScript = document.createElement("script");
      for (const attr of Array.from(oldScript.attributes)) {
        newScript.setAttribute(attr.name, attr.value);
      }
      newScript.textContent = oldScript.textContent;
      if (oldScript.parentNode) {
        oldScript.parentNode.replaceChild(newScript, oldScript);
      }
    }
  }

  function updateHeadTags(nextDoc) {
    const currentMeta = document.head.querySelectorAll("meta[name], meta[property]");
    currentMeta.forEach((el) => el.remove());

    const nextMeta = nextDoc.head.querySelectorAll("meta[name], meta[property]");
    nextMeta.forEach((el) => {
      document.head.appendChild(document.importNode(el, true));
    });

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
  }

  function isInternalLink(anchor) {
    if (!anchor || anchor.tagName !== "A") return false;
    if (anchor.target && anchor.target !== "_self") return false;
    if (anchor.hasAttribute("download")) return false;
    if (anchor.getAttribute("rel") === "external") return false;
    if (anchor.getAttribute("data-no-router") !== null) return false;

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
        path.startsWith("/_lila")
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

      e.preventDefault();
      Lila.navigate(url);
    });

    document.addEventListener(
      "mouseover",
      (e) => {
        const anchor = e.target.closest("a");
        if (!anchor || !canPrefetch(anchor)) return;
        const url = anchor.href;
        if (!getPrefetchedHtml(url)) {
          fetch(url, { headers: { "X-Lila-Prefetch": "1" }, credentials: "include" })
            .then((r) => (r.ok ? r.text() : null))
            .then((html) => {
              if (html) setPrefetchedHtml(url, html);
            })
            .catch(() => {});
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
    }

    function connect() {
      cleanup();
      try {
        es = new EventSource("/_lila/dev-reload");

        es.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
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
    initLinkInterception();
    Lila.hydrate();
    initDevReload();
    const detail = { url: window.location.href, initial: true };
    window.dispatchEvent(new CustomEvent("lila:page-load", { detail }));
    document.dispatchEvent(new CustomEvent("lila:page-load", { detail }));
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

    const title = options && options.title ? `<div class="font-bold text-sm leading-tight">${options.title}</div>` : "";
    const desc = options && options.description ? `<div class="text-xs opacity-90 mt-0.5">${options.description}</div>` : "";

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

  // 5. Drawer
  if (component === "drawer") {
    cleanupOrphanedBackdrops();
    const id = options && options.id;
    const action = (options && options.action) || "toggle";
    if (!id) return;
    const drawerEl = document.getElementById(id);
    if (!drawerEl) return;

    let overlay = document.querySelector(`.drawer-backdrop[data-for="${id}"]`);
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "drawer-backdrop fixed inset-0 z-[9998] bg-slate-950/50 backdrop-blur-sm transition-opacity duration-300 opacity-0 pointer-events-none";
      overlay.setAttribute("data-for", id);
      document.body.appendChild(overlay);
      overlay.addEventListener("click", () => lila("drawer", { id, action: "close" }));
    }

    const isOpen = drawerEl.classList.contains("open");
    if (action === "open" || (action === "toggle" && !isOpen)) {
      drawerEl.classList.add("open");
      drawerEl.classList.remove("translate-x-full", "-translate-x-full");
      overlay.classList.add("open", "opacity-100", "pointer-events-auto");
      overlay.classList.remove("opacity-0", "pointer-events-none");
      document.body.style.overflow = "hidden";
    } else if (action === "close" || (action === "toggle" && isOpen)) {
      drawerEl.classList.remove("open");
      drawerEl.classList.add(drawerEl.getAttribute("data-side") === "left" ? "-translate-x-full" : "translate-x-full");
      overlay.classList.remove("open", "opacity-100", "pointer-events-auto");
      overlay.classList.add("opacity-0", "pointer-events-none");
      document.body.style.overflow = "";
    }
  }

  // 6. Carousel
  if (component === "carousel") {
    const selector = (options && options.selector) || ".carousel";
    document.querySelectorAll(selector).forEach((c) => initSingleCarousel(c, options));
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

function initSingleCarousel(carousel, opts = {}) {
  if (carousel._lila_initialized) return;
  carousel._lila_initialized = true;

  const track = carousel.querySelector(".carousel-track");
  if (!track) return;
  const items = Array.from(track.querySelectorAll(".carousel-item, .carousel-card"));
  if (items.length === 0) return;

  const prevBtn = carousel.querySelector(".carousel-prev");
  const nextBtn = carousel.querySelector(".carousel-next");
  let indicatorsContainer = carousel.querySelector(".carousel-indicators");
  let currentSlideIndex = 0;

  function scrollToSlide(index) {
    if (index < 0) index = 0;
    if (index >= items.length) index = items.length - 1;
    currentSlideIndex = index;
    const targetItem = items[index];
    if (targetItem) {
      track.scrollTo({ left: targetItem.offsetLeft - track.offsetLeft, behavior: "smooth" });
    }
  }

  if (prevBtn) prevBtn.addEventListener("click", () => scrollToSlide(currentSlideIndex - 1));
  if (nextBtn) nextBtn.addEventListener("click", () => scrollToSlide(currentSlideIndex + 1));
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
        navigator.clipboard.writeText(textToCopy.trim()).then(() => {
          lila("toast", {
            title: "Copied",
            description: textToCopy.length > 40 ? textToCopy.substring(0, 40) + "..." : textToCopy,
            type: "success",
            duration: 2500,
          });
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
      if (next === "dark") html.classList.add("dark");
      else html.classList.remove("dark");
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
      edit: false,
      delete: false,
      breakpoint: 768,
      ...options,
    };

    this.currentPage = 1;
    this.filteredData = [...this.options.data];
    this.isMobile = window.innerWidth < this.options.breakpoint;
    this.init();
    window.addEventListener("resize", () => {
      const wasMobile = this.isMobile;
      this.isMobile = window.innerWidth < this.options.breakpoint;
      if (wasMobile !== this.isMobile) this.updateTable();
    });
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
      return `<th class="px-4 py-3.5 font-bold">${title}</th>`;
    }).join("");

    const actionsHeader = this.options.edit || this.options.delete ? '<th class="px-4 py-3.5 font-bold text-right">Actions</th>' : "";

    const startIndex = (this.currentPage - 1) * this.options.rowsPerPage;
    const pageItems = this.filteredData.slice(startIndex, startIndex + this.options.rowsPerPage);

    const tbodyRows = pageItems.map((item) => {
      const cells = this.options.columns.map((col) => {
        const val = item[col.key];
        return `<td class="px-4 py-3.5 text-slate-700 dark:text-slate-300 align-middle">${val !== undefined && val !== null ? val : "-"}</td>`;
      }).join("");

      let actionBtns = "";
      if (this.options.edit || this.options.delete) {
        actionBtns = `<td class="px-4 py-3.5 text-right align-middle"><div class="flex items-center justify-end gap-2">`;
        if (this.options.edit) {
          actionBtns += `<button class="datatable-btn-edit px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-all cursor-pointer" data-id="${item.id}">Edit</button>`;
        }
        if (this.options.delete) {
          actionBtns += `<button class="datatable-btn-delete px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-500/10 text-red-600 dark:text-red-400 hover:bg-red-500 hover:text-white transition-all cursor-pointer" data-id="${item.id}">Delete</button>`;
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
      const summaryText = this.options.summaryFields.map((k) => item[k]).filter(Boolean).join(" • ");
      const details = this.options.columns
        .filter((c) => !this.options.summaryFields.includes(c.key))
        .map((c) => {
          const title = this.options.headerTitles[c.key] || c.title || c.key;
          return `<div class="flex items-center justify-between py-1 text-xs"><dt class="font-bold text-slate-400 uppercase">${title}</dt><dd class="text-slate-700 dark:text-slate-200 font-medium">${item[c.key] || "-"}</dd></div>`;
        }).join("");

      return `
        <article class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 mb-3 shadow-sm">
          <h3 class="font-bold text-sm text-slate-900 dark:text-slate-100 pb-2 border-b border-slate-100 dark:border-slate-800 mb-2">${summaryText || "Item"}</h3>
          <dl class="space-y-1 mb-3">${details}</dl>
          <div class="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            ${this.options.edit ? `<button class="datatable-btn-edit px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200" data-id="${item.id}">Edit</button>` : ""}
            ${this.options.delete ? `<button class="datatable-btn-delete px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-500/10 text-red-600 dark:text-red-400" data-id="${item.id}">Delete</button>` : ""}
          </div>
        </article>
      `;
    }).join("");

    this.bindActionEvents(container);
  }

  bindActionEvents(root) {
    root.querySelectorAll(".datatable-btn-edit").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const id = btn.getAttribute("data-id");
        const item = this.options.data.find((d) => String(d.id) === String(id));
        if (typeof this.options.edit === "function") this.options.edit(e, item || id);
      });
    });

    root.querySelectorAll(".datatable-btn-delete").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const id = btn.getAttribute("data-id");
        const item = this.options.data.find((d) => String(d.id) === String(id));
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
async function Http(url = "/", method = "GET", body = false, bodyForm = false, headers = {}) {
  const csrfEl =
    document.getElementById("csrf") ||
    document.querySelector('input[name="_csrf"]') ||
    document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfEl ? csrfEl.value || csrfEl.getAttribute("content") : null;

  const mergedHeaders = { ...headers };
  if (csrfToken) {
    mergedHeaders["X-CSRF-Token"] = csrfToken;
  }

  const upperMethod = String(method || "GET").toUpperCase();
  const options = { method: upperMethod, headers: mergedHeaders, credentials: "include" };

  if (body) {
    const payload = csrfToken ? { ...body, _csrf: csrfToken, csrf: csrfToken } : body;
    options.body = JSON.stringify(payload);
    if (!mergedHeaders["Content-Type"]) {
      mergedHeaders["Content-Type"] = "application/json";
    }
  }

  if (bodyForm) {
    if (csrfToken && bodyForm instanceof FormData) {
      if (!bodyForm.has("_csrf")) bodyForm.append("_csrf", csrfToken);
    }
    options.body = bodyForm;
  }

  if (upperMethod !== "GET" && window.Lila && typeof window.Lila.clearPrefetch === "function") {
    window.Lila.clearPrefetch();
  }

  const response = await fetch(url, options);
  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch {
      errorData = { message: `HTTP Error ${response.status}: ${response.statusText}` };
    }
    throw new Error(errorData.message || errorData.msg || "Fetch request failed");
  }
  return await response.json();
}

if (typeof window !== "undefined") {
  window.ResponsiveDataTable = ResponsiveDataTable;
  window.Http = Http;
  window.lila = lila;
  window.Lila.ui = lila;
}
