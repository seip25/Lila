// Typed access to the desktop bridge (lila desktop dev/build -> window.pywebview.api).
// Every helper is a no-op returning null/false on the web, so pages can call
// them unconditionally:
//
//   import { desktop, useDesktopUpdate } from "@lila/desktop";
//   await desktop.notify("Backup finished", "3 files");
//   const update = useDesktopUpdate();   // { available, version, notes, install() }
import { useCallback, useEffect, useState } from "react";

export interface UpdateInfo {
  available: boolean;
  current?: string;
  version?: string;
  notes?: string;
  url?: string;
  reason?: string;
}

export interface AppInfo {
  name: string;
  version: string;
  platform: "windows" | "macos" | "linux";
  os: string;
  frozen: boolean;
  data_dir: string;
}

interface BridgeApi {
  open_file_dialog(title?: string, fileTypes?: string[]): Promise<string | null>;
  save_file_dialog(title?: string, defaultFilename?: string): Promise<string | null>;
  select_folder_dialog(title?: string): Promise<string | null>;
  notify(title: string, message?: string): Promise<boolean>;
  open_external(url: string): Promise<boolean>;
  app_info(): Promise<AppInfo>;
  check_update(): Promise<UpdateInfo>;
  install_update(): Promise<{ ok: boolean; reason?: string; version?: string }>;
  set_title(title: string): Promise<boolean>;
  get_system_metrics(): Promise<Record<string, unknown>>;
}

function api(): BridgeApi | null {
  return ((typeof window !== "undefined" && (window as any).pywebview?.api) as BridgeApi) || null;
}

/** pywebview injects the bridge after load: wait for it (max ~3 s). */
export function whenDesktopReady(timeout = 3000): Promise<BridgeApi | null> {
  if (api()) return Promise.resolve(api());
  if (typeof window === "undefined") return Promise.resolve(null);
  return new Promise((resolve) => {
    const done = () => resolve(api());
    window.addEventListener("pywebviewready", done, { once: true });
    window.setTimeout(done, timeout);
  });
}

async function call<T>(fn: (bridge: BridgeApi) => Promise<T>, fallback: T): Promise<T> {
  const bridge = await whenDesktopReady();
  if (!bridge) return fallback;
  try {
    return await fn(bridge);
  } catch {
    return fallback;
  }
}

export const desktop = {
  available: () => api() !== null,
  openFile: (title?: string, fileTypes?: string[]) => call((b) => b.open_file_dialog(title, fileTypes), null),
  saveFile: (title?: string, name?: string) => call((b) => b.save_file_dialog(title, name), null),
  selectFolder: (title?: string) => call((b) => b.select_folder_dialog(title), null),
  notify: (title: string, message?: string) => call((b) => b.notify(title, message), false),
  /** http(s)/mailto in the system browser; on the web a new tab. */
  openExternal: async (url: string) => {
    if (!api()) {
      window.open(url, "_blank", "noopener");
      return true;
    }
    return call((b) => b.open_external(url), false);
  },
  appInfo: () => call((b) => b.app_info(), null as AppInfo | null),
  checkUpdate: () => call((b) => b.check_update(), { available: false, reason: "web" } as UpdateInfo),
  installUpdate: () => call((b) => b.install_update(), { ok: false, reason: "web" }),
  setTitle: (title: string) => call((b) => b.set_title(title), false),
};

/** Checks for an update once (desktop only); `install()` downloads, verifies and opens it. */
export function useDesktopUpdate() {
  const [info, setInfo] = useState<UpdateInfo>({ available: false });
  const [installing, setInstalling] = useState(false);
  useEffect(() => {
    let alive = true;
    desktop.checkUpdate().then((result) => alive && setInfo(result));
    return () => {
      alive = false;
    };
  }, []);
  const install = useCallback(async () => {
    setInstalling(true);
    try {
      return await desktop.installUpdate();
    } finally {
      setInstalling(false);
    }
  }, []);
  return { ...info, installing, install };
}
