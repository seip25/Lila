// Lila <-> React client (copied by `lila react init`; it is your code now).
// Written in TypeScript; JavaScript projects import it too (Vite strips types).
//
//   createLilaApp({ pages })   pages from react_render(request, "Name", props)
//   createLilaSpa(App)         SPA from router.spa("/app", meta={...})
//   <Link href="/x">           client navigation (JSON page + <head> swap)
//   visit(url, opts)           programmatic navigation
//   http(url, opts)            fetch + CSRF + JSON, throws HttpError { status, data }
//   useForm(initial)           form state + Lila 422 field errors + CSRF
//   useLila()                  { page, props, desktop, isAvailable, visit, http }
//   useT()                     t(key, fallback) for react_render(translations=[...])
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
  type AnchorHTMLAttributes,
  type ComponentType,
  type FormEvent,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
} from "react";
import { createRoot, type Root } from "react-dom/client";

// ── types ───────────────────────────────────────────────────────────────────
export type Props = Record<string, unknown>;

export interface Head {
  title: string;
  description: string;
  keywords: string;
  robots: string;
  canonical: string;
  image: string;
  og_type: string;
  url: string;
  meta: Array<Record<string, string>>;
  jsonld: unknown[];
  lang: string;
}

export interface Page<P = Props> {
  component: string | null;
  /** Locale strings sent with react_render(translations=...). */
  t?: Record<string, string>;
  props: P;
  url: string;
  version: string;
  csrf: string;
  desktop: boolean;
  unavailable: string[];
  head?: Head;
  spa?: { mount: string };
}

export type PageComponent<P = any> = ComponentType<P> & {
  layout?: (page: ReactElement) => ReactNode;
};

// import.meta.glob("./pages/**/*.tsx") result: lazy loaders, or modules with { eager: true }.
export type PagesGlob = Record<string, unknown>;

export interface VisitOptions {
  method?: string;
  data?: unknown;
  replace?: boolean;
  preserveScroll?: boolean;
  headers?: Record<string, string>;
}

export interface HttpOptions extends Omit<RequestInit, "body"> {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

export class HttpError<T = any> extends Error {
  status: number;
  data: T;
  constructor(message: string, status: number, data: T) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export interface LilaContextValue {
  page: Page;
  props: Props;
  desktop: boolean;
  isAvailable: (href: string) => boolean;
  visit: typeof visit;
  http: typeof http;
}

declare global {
  interface Window {
    pywebview?: { api?: Record<string, (...args: any[]) => Promise<any>> };
  }
}

const LilaContext = createContext<LilaContextValue | null>(null);
let currentPage: Page | null = null;
let lilaNavigate: ((url: string, options?: VisitOptions) => Promise<Page | unknown>) | null = null;

// ── page payload ────────────────────────────────────────────────────────────
export function readPage(): Page {
  const el = document.getElementById("lila-page");
  const empty = { component: null, props: {}, url: "", version: "", csrf: "", desktop: false, unavailable: [] };
  if (!el) return empty;
  try {
    return { ...empty, ...JSON.parse(el.textContent || "{}") };
  } catch {
    return empty;
  }
}

export function csrfToken(): string {
  return (
    currentPage?.csrf ||
    document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ||
    ""
  );
}

function compileUnavailable(list: string[] | undefined): RegExp[] {
  return (list || [])
    .map((source) => {
      try {
        return new RegExp(source);
      } catch {
        return null;
      }
    })
    .filter((regex): regex is RegExp => regex !== null);
}

function pathOf(href: string): string | null {
  try {
    const url = new URL(href, window.location.href);
    return url.origin === window.location.origin ? url.pathname : null;
  } catch {
    return null;
  }
}

// ── http ────────────────────────────────────────────────────────────────────
export async function http<T = any>(url: string, { method = "GET", body, headers = {}, ...rest }: HttpOptions = {}): Promise<T> {
  const verb = method.toUpperCase();
  const finalHeaders: Record<string, string> = { Accept: "application/json", ...headers };
  const options: RequestInit = { method: verb, credentials: "same-origin", ...rest, headers: finalHeaders };
  if (verb !== "GET" && verb !== "HEAD") finalHeaders["X-CSRF-Token"] = csrfToken();
  if (body !== undefined) {
    if (body instanceof FormData || body instanceof URLSearchParams || body instanceof Blob) {
      options.body = body;
    } else {
      options.body = JSON.stringify(body);
      finalHeaders["Content-Type"] = "application/json";
    }
  }
  const res = await fetch(url, options);
  const type = res.headers.get("content-type") || "";
  const data = type.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const message = (data && (data.message || data.msg || data.detail)) || res.statusText;
    throw new HttpError(typeof message === "string" ? message : res.statusText, res.status, data);
  }
  return data as T;
}

// ── forms ───────────────────────────────────────────────────────────────────
export type FormErrors<T> = Partial<Record<keyof T | "_form", string>>;

export interface SubmitOptions<R> {
  /** Navigate here on success (or the `redirect` the server returns). */
  redirect?: string;
  onSuccess?: (response: R) => void;
  onError?: (error: HttpError) => void;
  /** Reset the fields to their initial values after a success. */
  reset?: boolean;
  /** Change the payload before sending (e.g. "" -> null for optional fields). */
  transform?: (data: any) => unknown;
}

/** Turns Lila errors (`[{field: msg}]`, `{field: msg}` or `msg`) into a map. */
export function parseErrors<T>(data: any): FormErrors<T> {
  const errors: Record<string, string> = {};
  const list = data && data.errors;
  if (Array.isArray(list)) {
    list.forEach((item) => {
      if (item && typeof item === "object") {
        Object.entries(item).forEach(([field, msg]) => (errors[field] = String(msg)));
      }
    });
  } else if (list && typeof list === "object") {
    Object.entries(list).forEach(([field, msg]) => (errors[field] = String(msg)));
  }
  const message = data && (data.message || data.msg);
  if (!Object.keys(errors).length && message) errors._form = String(message);
  return errors as FormErrors<T>;
}

/**
 * Form state for Lila JSON endpoints (`@router.post(..., model=Model)`):
 *
 *   const form = useForm({ email: "", password: "" });
 *   <form onSubmit={form.handleSubmit("/login", { redirect: "/dashboard" })}>
 *     <input {...form.field("email")} />  {form.errors.email}
 */
export function useForm<T extends Record<string, any>>(initial: T) {
  const initialRef = useRef(initial);
  const [data, setDataState] = useState<T>(initial);
  const [errors, setErrors] = useState<FormErrors<T>>({});
  const [processing, setProcessing] = useState(false);
  const [message, setMessage] = useState("");

  const setData = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
    setDataState((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  }, []);

  const field = useCallback(
    <K extends keyof T & string>(name: K) => {
      const value = data[name];
      const common = { id: name, name, "aria-invalid": errors[name] ? true : undefined };
      if (typeof value === "boolean") {
        return { ...common, type: "checkbox", checked: value, onChange: (e: any) => setData(name, e.target.checked) };
      }
      return { ...common, value: (value ?? "") as any, onChange: (e: any) => setData(name, e.target.value) };
    },
    [data, errors, setData],
  );

  const reset = useCallback(() => {
    setDataState(initialRef.current);
    setErrors({});
  }, []);

  const submit = useCallback(
    async <R = any>(method: string, url: string, options: SubmitOptions<R> = {}): Promise<R | undefined> => {
      setProcessing(true);
      setErrors({});
      setMessage("");
      try {
        const body = options.transform ? options.transform(data) : data;
        const response = await http<R>(url, { method, body });
        const payload: any = response;
        if (payload && typeof payload === "object" && payload.success === false) {
          setErrors(parseErrors<T>(payload));
          return undefined;
        }
        if (payload && typeof payload === "object") setMessage(String(payload.message || payload.msg || ""));
        if (options.reset) reset();
        options.onSuccess?.(response);
        const target = (payload && payload.redirect) || options.redirect;
        if (target) await visit(target);
        return response;
      } catch (error) {
        const err = error instanceof HttpError ? error : new HttpError(String(error), 0, null);
        const parsed = parseErrors<T>(err.data);
        setErrors(Object.keys(parsed).length ? parsed : ({ _form: err.message } as FormErrors<T>));
        options.onError?.(err);
        return undefined;
      } finally {
        setProcessing(false);
      }
    },
    [data, reset],
  );

  const handleSubmit = useCallback(
    <R = any>(url: string, options: SubmitOptions<R> & { method?: string } = {}) =>
      (event?: FormEvent) => {
        event?.preventDefault();
        return submit<R>(options.method || "POST", url, options);
      },
    [submit],
  );

  return { data, setData, field, errors, setErrors, processing, message, submit, handleSubmit, reset };
}

// ── <head> ──────────────────────────────────────────────────────────────────
const KEEP_META = new Set(["viewport", "color-scheme", "csrf-token", "lila-debug"]);

function setLink(rel: string, href: string) {
  let el = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
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

function addMeta(attrs: Record<string, string>) {
  const el = document.createElement("meta");
  Object.entries(attrs).forEach(([key, value]) => value != null && el.setAttribute(key, String(value)));
  el.setAttribute("data-lila-head", "");
  document.head.appendChild(el);
}

/** Applies the head payload sent by react_render / router.spa. */
export function applyHead(head?: Head | null) {
  if (!head) return;
  if (head.title) document.title = head.title;
  if (head.lang) document.documentElement.lang = head.lang;
  document.head.querySelectorAll("meta[name], meta[property]").forEach((el) => {
    if (!KEEP_META.has(el.getAttribute("name") || "")) el.remove();
  });
  const pairs: Array<[string, string, string]> = [
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
export async function visit(url: string, options: VisitOptions = {}): Promise<Page | unknown> {
  if (lilaNavigate) return lilaNavigate(url, options);
  window.location.href = url;
  return undefined;
}

async function resolveComponent(pages: PagesGlob, name: string | null): Promise<PageComponent> {
  const wanted = String(name || "").replace(/^\/+/, "");
  const key = Object.keys(pages).find(
    (k) => k.replace(/^.*?pages\//, "").replace(/\.(jsx|tsx|js|ts)$/, "") === wanted,
  );
  if (!key) throw new Error(`Lila: page "${wanted}" not found in resources/react/pages`);
  let mod: any = pages[key];
  // Lazy import.meta.glob values are loaders; eager ones are modules.
  if (typeof mod === "function") mod = await mod();
  return (mod && mod.default) || mod;
}

function useLilaValue(page: Page): LilaContextValue {
  const unavailable = useMemo(() => compileUnavailable(page.unavailable), [page.unavailable]);
  const isAvailable = useCallback(
    (href: string) => {
      const path = pathOf(href);
      return path === null || !unavailable.some((regex) => regex.test(path));
    },
    [unavailable],
  );
  return useMemo(
    () => ({ page, props: page.props || {}, desktop: Boolean(page.desktop), isAvailable, visit, http }),
    [page, isAvailable],
  );
}

export function LilaProvider({ page, children }: { page: Page; children: ReactNode }) {
  const value = useLilaValue(page);
  return <LilaContext.Provider value={value}>{children}</LilaContext.Provider>;
}

export function useLila(): LilaContextValue {
  const value = useContext(LilaContext);
  if (!value) throw new Error("useLila() must be used inside createLilaApp/createLilaSpa");
  return value;
}

export function usePage<P = Props>(): Page<P> {
  return useLila().page as Page<P>;
}

/** Translator for strings sent with react_render(translations=[...]). */
export function useT() {
  const page = useContext(LilaContext)?.page;
  return useCallback(
    (key: string, fallback?: string) => (page?.t && page.t[key] && page.t[key] !== key ? page.t[key] : fallback ?? key),
    [page],
  );
}

interface PagesState {
  page: Page;
  Component: PageComponent;
}

function PagesApp({ initial, pages, layout: Layout }: { initial: PagesState; pages: PagesGlob; layout?: ComponentType<{ children: ReactNode }> }) {
  const [state, setState] = useState<PagesState>(initial);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const go = async (url: string, { method = "GET", data, replace = false, preserveScroll = false, headers = {} }: VisitOptions = {}) => {
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

    const onPop = async (event: PopStateEvent) => {
      const saved: Page | undefined = event.state && event.state.lila;
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

export interface CreateLilaAppOptions {
  pages: PagesGlob;
  root?: string;
  layout?: ComponentType<{ children: ReactNode }>;
  onError?: (error: unknown) => void;
}

/** Mounts the pages rendered with react_render(). */
export async function createLilaApp({ pages, root, layout, onError }: CreateLilaAppOptions): Promise<Root | null> {
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
export function createLilaSpa(App: ComponentType<{ mount: string; page: Page }>, { root }: { root?: string } = {}): Root | null {
  const page = readPage();
  currentPage = page;
  const el = document.getElementById(root || "root") || document.querySelector("[data-lila-react]");
  if (!el) return null;
  const mount = page.spa?.mount || "/";
  const reactRoot = createRoot(el);
  reactRoot.render(
    <LilaProvider page={page}>
      <App mount={mount} page={page} />
    </LilaProvider>,
  );
  return reactRoot;
}

/** SPA: asks the server for the meta of the current URL whenever `pathname` changes. */
export function useLilaHead(pathname: string) {
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
function isModified(event: MouseEvent) {
  return event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0;
}

export interface LinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  href: string;
  method?: string;
  data?: unknown;
  replace?: boolean;
  preserveScroll?: boolean;
  /** Routes removed in this mode (desktop=False / desktop="only") render nothing. */
  hideIfUnavailable?: boolean;
}

/** Client navigation link for react_render pages. */
export function Link({ href, method, data, replace, preserveScroll, hideIfUnavailable = true, onClick, children, ...props }: LinkProps) {
  const ctx = useContext(LilaContext);
  if (hideIfUnavailable && ctx && !ctx.isAvailable(href)) return null;
  const handle = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
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

export function DesktopOnly({ children, fallback = null }: { children: ReactNode; fallback?: ReactNode }) {
  const ctx = useContext(LilaContext);
  return <>{ctx && ctx.desktop ? children : fallback}</>;
}

export function WebOnly({ children, fallback = null }: { children: ReactNode; fallback?: ReactNode }) {
  const ctx = useContext(LilaContext);
  return <>{ctx && ctx.desktop ? fallback : children}</>;
}

/** Native bridge exposed by `lila desktop` (pywebview), or null on the web. */
export function desktopApi() {
  return (typeof window !== "undefined" && window.pywebview && window.pywebview.api) || null;
}
