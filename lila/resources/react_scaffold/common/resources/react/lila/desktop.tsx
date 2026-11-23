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
  description?: string;
  author?: string;
  lila_version?: string;
  platform: "windows" | "macos" | "linux";
  os: string;
  frozen: boolean;
  data_dir: string;
}

export interface HelpManual {
  ok?: boolean;
  markdown: string;
  html: string;
  is_empty: boolean;
  editable: boolean;
  path?: string;
  has_override?: boolean;
  has_bundled?: boolean;
  reason?: string;
}

export interface ReportSettings {
  configured: boolean;
  report_url?: string;
  anonymous_telemetry: boolean;
  install_id?: string;
  last_telemetry_at?: string | null;
  interval_seconds?: number;
}

export interface ReportSubmitResult {
  ok: boolean;
  status: string;
  stored?: boolean;
  duplicate?: boolean;
  id?: number;
  reason?: string;
}

export interface BackupResult {
  ok: boolean;
  path?: string;
  size_bytes?: number;
  size_mb?: number;
  duration_ms?: number;
  rotated?: number;
  reason?: string;
}

export interface LanStatus {
  running: boolean;
  host_ip?: string;
  port?: number;
  url?: string;
  pair_url?: string;
  otp?: string;
  otp_expires_in?: number;
  active_sessions?: number;
  allow?: string[];
  deny?: string[];
  revoked?: number;
  reason?: string;
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
  get_help_manual(): Promise<HelpManual>;
  save_help_manual(content: string): Promise<HelpManual>;
  reset_help_manual(): Promise<HelpManual>;
  open_data_dir(): Promise<boolean>;
  open_help(): Promise<boolean>;
  open_about(): Promise<boolean>;
  open_preferences(): Promise<boolean>;
  get_report_settings(): Promise<ReportSettings>;
  set_telemetry_opt_in(enabled: boolean): Promise<ReportSettings>;
  send_bug_report(note?: string, includeLogs?: boolean): Promise<ReportSubmitResult>;
  send_telemetry_now(): Promise<ReportSubmitResult>;
  open_bug_report(): Promise<boolean>;
  create_backup(compress?: boolean): Promise<BackupResult>;
  lan_status(): Promise<LanStatus>;
  start_lan(port?: number | null, otpTtl?: number | null): Promise<LanStatus>;
  stop_lan(): Promise<LanStatus>;
  rotate_lan_otp(ttl?: number | null): Promise<LanStatus>;
  revoke_lan_sessions(): Promise<LanStatus>;
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
  getHelpManual: () =>
    call((b) => b.get_help_manual(), { markdown: "", html: "", is_empty: true, editable: false } as HelpManual),
  saveHelpManual: (content: string) =>
    call((b) => b.save_help_manual(content), { ok: false, markdown: "", html: "", is_empty: true, editable: false, reason: "web" } as HelpManual),
  resetHelpManual: () =>
    call((b) => b.reset_help_manual(), { ok: false, markdown: "", html: "", is_empty: true, editable: false, reason: "web" } as HelpManual),
  openDataDir: () => call((b) => b.open_data_dir(), false),
  openHelp: () => call((b) => b.open_help(), false),
  openAbout: () => call((b) => b.open_about(), false),
  openPreferences: () => call((b) => b.open_preferences(), false),
  getReportSettings: () => call((b) => b.get_report_settings(), { configured: false, anonymous_telemetry: false } as ReportSettings),
  setTelemetryOptIn: (enabled: boolean) =>
    call((b) => b.set_telemetry_opt_in(enabled), { configured: false, anonymous_telemetry: false } as ReportSettings),
  sendBugReport: (note = "", includeLogs = true) =>
    call((b) => b.send_bug_report(note, includeLogs), { ok: false, status: "web", reason: "web" } as ReportSubmitResult),
  sendTelemetryNow: () => call((b) => b.send_telemetry_now(), { ok: false, status: "web", reason: "web" } as ReportSubmitResult),
  openBugReport: () => call((b) => b.open_bug_report(), false),
  createBackup: (compress = false) =>
    call((b) => b.create_backup(compress), { ok: false, reason: "web" } as BackupResult),
  lanStatus: () => call((b) => b.lan_status(), { running: false, reason: "web" } as LanStatus),
  startLan: (port?: number | null, otpTtl?: number | null) =>
    call((b) => b.start_lan(port ?? null, otpTtl ?? null), { running: false, reason: "web" } as LanStatus),
  stopLan: () => call((b) => b.stop_lan(), { running: false, reason: "web" } as LanStatus),
  rotateLanOtp: (ttl?: number | null) =>
    call((b) => b.rotate_lan_otp(ttl ?? null), { running: false, reason: "web" } as LanStatus),
  revokeLanSessions: () => call((b) => b.revoke_lan_sessions(), { running: false, revoked: 0, reason: "web" } as LanStatus),
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
