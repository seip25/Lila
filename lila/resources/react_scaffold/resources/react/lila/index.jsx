// Lila <-> React client (copied by `lila react init`; it is your code now).
//
//   createLilaApp({ pages })   pages from react_render(request, "Name", props)
//   createLilaSpa(App)         SPA from router.spa("/app", meta={...})
//   <Link href="/x">           client navigation (JSON page + <head> swap)
//   visit(url, opts)           programmatic navigation
//   http(url, opts)            fetch + CSRF + JSON, throws { status, data }
//   useLila()                  { page, props, desktop, isAvailable, visit, http }
//   <DesktopOnly> <WebOnly>    render children only in the desktop app / web
//   useLilaHead(pathname)      SPA: refresh <title>/meta/JSON-LD on navigation
//   desktopApi()               pywebview bridge (window.pywebview.api) or null
import {
  createContext,
  startTransition,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createRoot } from "react-dom/client";

const LilaContext = createContext(null);
let currentPage = null;
let lilaNavigate = null;

// ── page payload ────────────────────────────────────────────────────────────
export function readPage() {
  const el = document.getElementById("lila-page");
  if (!el) return {};
  try {
    return JSON.parse(el.textContent || "{}");
  } catch {
    return {};
  }
}

function csrfToken() {
  return (
    (currentPage && currentPage.csrf) ||
    document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ||
    ""
  );
}

function compileUnavailable(list) {
  return (list || [])
    .map((source) => {
      try {
        return new RegExp(source);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

function pathOf(href) {
  try {
    const url = new URL(href, window.location.href);
    if (url.origin !== window.location.origin) return null;
    return url.pathname;
  } catch {
    return null;
  }
}

// ── http ────────────────────────────────────────────────────────────────────
export async function http(url, { method = "GET", body, headers = {}, ...rest } = {}) {
  const verb = method.toUpperCase();
  const options = {
    method: verb,
    credentials: "same-origin",
    headers: { Accept: "application/json", ...headers },
    ...rest,
  };
  if (verb !== "GET" && verb !== "HEAD") options.headers["X-CSRF-Token"] = csrfToken();
  if (body !== undefined) {
    if (body instanceof FormData || body instanceof URLSearchParams || body instanceof Blob) {
      options.body = body;
    } else {
      options.body = JSON.stringify(body);
      options.headers["Content-Type"] = "application/json";
    }
  }
  const res = await fetch(url, options);
  const type = res.headers.get("content-type") || "";
  const data = type.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const message = (data && (data.message || data.msg || data.detail)) || res.statusText;
    const error = new Error(typeof message === "string" ? message : res.statusText);
    error.status = res.status;
    error.data = data;
    throw error;
  }
  return data;
}

// ── <head> ──────────────────────────────────────────────────────────────────
const KEEP_META = new Set(["viewport", "color-scheme", "csrf-token", "lila-debug"]);

function setLink(rel, href) {
  let el = document.head.querySelector(`link[rel="${rel}"]`);
  if (!href) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement("link");
    el.rel = rel;
    document.head.appendChild(el);
  }
  el.href = href;
}

function addMeta(attrs) {
  const el = document.createElement("meta");
  Object.entries(attrs).forEach(([k, v]) => v != null && el.setAttribute(k, String(v)));
  el.setAttribute("data-lila-head", "");
  document.head.appendChild(el);
}

/** Applies the head payload sent by react_render / router.spa. */
export function applyHead(head) {
  if (!head) return;
  if (head.title) document.title = head.title;
  if (head.lang) document.documentElement.lang = head.lang;
  document.head.querySelectorAll("meta[name], meta[property]").forEach((el) => {
    if (!KEEP_META.has(el.getAttribute("name"))) el.remove();
  });
  const pairs = [
    ["name", "description", head.description],
    ["name", "keywords", head.keywords],
    ["name", "robots", head.robots],
    ["property", "og:title", head.title],
    ["property", "og:type", head.og_type],
    ["property", "og:url", head.canonical || head.url],
    ["property", "og:description", head.description],
    ["property", "og:image", head.image],
    ["name", "twitter:card", head.image ? "summary_large_image" : ""],
    ["name", "twitter:image", head.image],
  ];
  pairs.forEach(([attr, key, content]) => content && addMeta({ [attr]: key, content }));
  (head.meta || []).forEach((item) => addMeta(item));
  setLink("canonical", head.canonical);
  document.head.querySelectorAll('script[type="application/ld+json"]').forEach((el) => el.remove());
  (head.jsonld || []).forEach((data) => {
    const script = document.createElement("script");
    script.type = "application/ld+json";
    script.setAttribute("data-lila-head", "");
    script.textContent = typeof data === "string" ? data : JSON.stringify(data);
    document.head.appendChild(script);
  });
}

// ── navigation (pages mode) ─────────────────────────────────────────────────
/** Navigates to a react_render page without a full reload. */
export async function visit(url, options = {}) {
  if (lilaNavigate) return lilaNavigate(url, options);
  window.location.href = url;
  return undefined;
}

async function resolveComponent(pages, name) {
  const wanted = String(name || "").replace(/^\/+/, "");
  const key = Object.keys(pages).find(
    (k) => k.replace(/^.*?pages\//, "").replace(/\.(jsx|tsx|js|ts)$/, "") === wanted,
  );
  if (!key) throw new Error(`Lila: page "${wanted}" not found in resources/react/pages`);
  let mod = pages[key];
  if (typeof mod === "function") mod = await mod();
  return mod.default || mod;
}

function useLilaValue(page) {
  const unavailable = useMemo(() => compileUnavailable(page.unavailable), [page.unavailable]);
  const isAvailable = useCallback(
    (href) => {
      const path = pathOf(href);
      if (path === null) return true;
      return !unavailable.some((regex) => regex.test(path));
    },
    [unavailable],
  );
  return useMemo(
    () => ({
      page,
      props: page.props || {},
      desktop: Boolean(page.desktop),
      isAvailable,
      visit,
      http,
    }),
    [page, isAvailable],
  );
}

export function LilaProvider({ page, children }) {
  const value = useLilaValue(page);
  return <LilaContext.Provider value={value}>{children}</LilaContext.Provider>;
}

export function useLila() {
  const value = useContext(LilaContext);
  if (!value) throw new Error("useLila() must be used inside createLilaApp/createLilaSpa");
  return value;
}

export function usePage() {
  return useLila().page;
}

function PagesApp({ initial, pages, layout: Layout }) {
  const [state, setState] = useState(initial);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const go = async (url, { method = "GET", data, replace = false, preserveScroll = false, headers = {} } = {}) => {
      const verb = method.toUpperCase();
      const res = await fetch(url, {
        method: verb,
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "X-Lila-React": "1",
          "X-Lila-Version": stateRef.current.page.version || "",
          ...(verb !== "GET" ? { "X-CSRF-Token": csrfToken(), "Content-Type": "application/json" } : {}),
          ...headers,
        },
        body: verb !== "GET" && data !== undefined ? JSON.stringify(data) : undefined,
      });
      if (res.status === 409) {
        window.location.href = res.headers.get("X-Lila-Location") || url;
        return undefined;
      }
      const type = res.headers.get("content-type") || "";
      if (!type.includes("application/json")) {
        // Not a React page (Jinja page, file...): let the browser load it.
        window.location.href = res.url || url;
        return undefined;
      }
      const next = await res.json();
      if (!next || !next.component) {
        if (verb === "GET") window.location.href = res.url || url;
        return next;
      }
      const Component = await resolveComponent(pages, next.component);
      currentPage = next;
      startTransition(() => setState({ page: next, Component }));
      window.history[replace ? "replaceState" : "pushState"]({ lila: next }, "", next.url);
      applyHead(next.head);
      if (!preserveScroll) window.scrollTo(0, 0);
      return next;
    };
    lilaNavigate = go;

    const onPop = async (event) => {
      const saved = event.state && event.state.lila;
      if (saved && saved.component) {
        const Component = await resolveComponent(pages, saved.component);
        currentPage = saved;
        startTransition(() => setState({ page: saved, Component }));
        applyHead(saved.head);
      } else {
        go(window.location.pathname + window.location.search, { replace: true });
      }
    };
    window.addEventListener("popstate", onPop);
    window.history.replaceState({ lila: stateRef.current.page }, "", window.location.href);
    return () => {
      window.removeEventListener("popstate", onPop);
      lilaNavigate = null;
    };
  }, [pages]);

  const { page, Component } = state;
  const content = <Component {...(page.props || {})} />;
  const wrapped = Component.layout ? Component.layout(content) : Layout ? <Layout>{content}</Layout> : content;
  return <LilaProvider page={page}>{wrapped}</LilaProvider>;
}

/** Mounts the pages rendered with react_render(). */
export async function createLilaApp({ pages, root, layout, onError } = {}) {
  const page = readPage();
  currentPage = page;
  const el = document.getElementById(root || "app") || document.querySelector("[data-lila-react]");
  if (!el || !page.component) return null;
  try {
    const Component = await resolveComponent(pages || {}, page.component);
    const reactRoot = createRoot(el);
    reactRoot.render(<PagesApp initial={{ page, Component }} pages={pages || {}} layout={layout} />);
    return reactRoot;
  } catch (error) {
    if (onError) onError(error);
    else console.error(error);
    return null;
  }
}

/** Mounts a SPA served by router.spa(); `App` receives { mount, page }. */
export function createLilaSpa(App, { root } = {}) {
  const page = readPage();
  currentPage = page;
  const el = document.getElementById(root || "root") || document.querySelector("[data-lila-react]");
  if (!el) return null;
  const mount = (page.spa && page.spa.mount) || "/";
  const reactRoot = createRoot(el);
  reactRoot.render(
    <LilaProvider page={page}>
      <App mount={mount} page={page} />
    </LilaProvider>,
  );
  return reactRoot;
}

/** SPA: asks the server for the meta of the current URL whenever `pathname` changes. */
export function useLilaHead(pathname) {
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false; // the first page already has server-rendered meta
      return undefined;
    }
    const controller = new AbortController();
    // `pathname` only triggers the effect: React Router strips the basename,
    // the browser URL has the full path the server knows.
    fetch(window.location.pathname + window.location.search, {
      credentials: "same-origin",
      headers: { Accept: "application/json", "X-Lila-Head": "1" },
      signal: controller.signal,
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && applyHead(data.head))
      .catch(() => {});
    return () => controller.abort();
  }, [pathname]);
}

// ── components ──────────────────────────────────────────────────────────────
function isModified(event) {
  return event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0;
}

/**
 * Client navigation link for react_render pages. Routes removed in the current
 * mode (desktop=False in the desktop app, desktop="only" on the web) render
 * nothing unless `hideIfUnavailable={false}`.
 */
export function Link({
  href,
  method,
  data,
  replace,
  preserveScroll,
  hideIfUnavailable = true,
  onClick,
  children,
  ...props
}) {
  const ctx = useContext(LilaContext);
  if (hideIfUnavailable && ctx && !ctx.isAvailable(href)) return null;
  const handle = (event) => {
    if (onClick) onClick(event);
    if (event.defaultPrevented || isModified(event) || props.target || props.download) return;
    if (pathOf(href) === null) return;
    event.preventDefault();
    visit(href, { method, data, replace, preserveScroll });
  };
  return (
    <a href={href} onClick={handle} {...props}>
      {children}
    </a>
  );
}

export function DesktopOnly({ children, fallback = null }) {
  const ctx = useContext(LilaContext);
  return ctx && ctx.desktop ? children : fallback;
}

export function WebOnly({ children, fallback = null }) {
  const ctx = useContext(LilaContext);
  return ctx && ctx.desktop ? fallback : children;
}

/** Native bridge exposed by `lila desktop` (pywebview), or null on the web. */
export function desktopApi() {
  return (typeof window !== "undefined" && window.pywebview && window.pywebview.api) || null;
}
