// Real-time hooks for Lila's SSE Channels and WebSocketHub (copied by
// `lila react init`; edit freely).
//
//   const { last, connected } = useSSE("/events/orders", {
//     events: { "order:new": (order) => toast.success(`Order #${order.id}`) },
//   });
//
//   const chat = useWebSocket("/ws/chat", {
//     rooms: ["general"],
//     events: { "chat:message": (msg) => setMessages((m) => [...m, msg]) },
//   });
//   chat.emit("chat:message", { text: "hi" });
//
// Server side: Channel("orders").stream(request) / .publish(data, event) and
// router.ws_hub("/ws/chat", hub) with @hub.can_join for private rooms.
import { useCallback, useEffect, useRef, useState } from "react";

type Handler = (data: any, event: string) => void;

function parse(raw: string): any {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

export interface SSEOptions {
  /** Named events (`event: order:new`) to listen to. */
  events?: Record<string, Handler>;
  /** Unnamed messages (`data:` only). */
  onMessage?: Handler;
  enabled?: boolean;
  withCredentials?: boolean;
}

/** Server-Sent Events with automatic reconnection (native EventSource). */
export function useSSE<T = any>(url: string | null, options: SSEOptions = {}) {
  const { enabled = true, withCredentials = true } = options;
  const [connected, setConnected] = useState(false);
  const [last, setLast] = useState<{ event: string; data: T } | null>(null);
  const handlers = useRef(options);
  handlers.current = options;
  const source = useRef<EventSource | null>(null);
  const eventNames = Object.keys(options.events || {}).sort().join("|");

  useEffect(() => {
    if (!url || !enabled || typeof EventSource === "undefined") return undefined;
    const es = new EventSource(url, { withCredentials });
    source.current = es;
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(es.readyState === EventSource.OPEN);
    es.onmessage = (e) => {
      const data = parse(e.data);
      setLast({ event: "message", data });
      handlers.current.onMessage?.(data, "message");
    };
    const names = eventNames ? eventNames.split("|") : [];
    const listeners = names.map((name) => {
      const listener = (e: MessageEvent) => {
        const data = parse(e.data);
        setLast({ event: name, data });
        handlers.current.events?.[name]?.(data, name);
      };
      es.addEventListener(name, listener as EventListener);
      return [name, listener] as const;
    });
    return () => {
      listeners.forEach(([name, listener]) => es.removeEventListener(name, listener as EventListener));
      es.close();
      source.current = null;
      setConnected(false);
    };
  }, [url, enabled, withCredentials, eventNames]);

  const close = useCallback(() => source.current?.close(), []);
  return { connected, last, close };
}

export interface WebSocketOptions {
  rooms?: string[];
  events?: Record<string, Handler>;
  /** Every message, including events without a handler. */
  onMessage?: Handler;
  enabled?: boolean;
  /** Max reconnect delay in ms (exponential backoff with jitter). */
  maxDelay?: number;
  heartbeat?: number;
  /** Messages kept while offline (sent on reconnect). */
  queueSize?: number;
}

function socketUrl(url: string): string {
  if (/^wss?:\/\//.test(url)) return url;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${url.startsWith("/") ? url : `/${url}`}`;
}

/** WebSocketHub client: {event, data} messages, rooms, reconnect, heartbeat. */
export function useWebSocket(url: string | null, options: WebSocketOptions = {}) {
  const { enabled = true, maxDelay = 15000, heartbeat = 25000, queueSize = 100 } = options;
  const [connected, setConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const rooms = useRef(new Set<string>(options.rooms || []));
  const queue = useRef<string[]>([]);
  const handlers = useRef(options);
  handlers.current = options;
  const extra = useRef(new Map<string, Set<Handler>>());

  const sendRaw = useCallback((payload: string) => {
    const socket = ws.current;
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(payload);
    else {
      queue.current.push(payload);
      if (queue.current.length > queueSize) queue.current.shift();
    }
  }, [queueSize]);

  useEffect(() => {
    if (!url || !enabled) return undefined;
    let stopped = false;
    let attempt = 0;
    let retry: number | undefined;
    let ping: number | undefined;

    const connect = () => {
      const socket = new WebSocket(socketUrl(url));
      ws.current = socket;
      socket.onopen = () => {
        attempt = 0;
        setConnected(true);
        rooms.current.forEach((room) => socket.send(JSON.stringify({ event: "join", data: room })));
        const pending = queue.current.splice(0);
        pending.forEach((payload) => socket.send(payload));
        ping = window.setInterval(() => socket.send(JSON.stringify({ event: "ping", data: Date.now() })), heartbeat);
      };
      socket.onmessage = (e) => {
        const msg = parse(e.data);
        const event = msg && typeof msg === "object" && msg.event ? String(msg.event) : "message";
        const data = msg && typeof msg === "object" && "data" in msg ? msg.data : msg;
        if (event === "pong") return;
        handlers.current.onMessage?.(data, event);
        handlers.current.events?.[event]?.(data, event);
        extra.current.get(event)?.forEach((fn) => fn(data, event));
      };
      socket.onclose = () => {
        window.clearInterval(ping);
        setConnected(false);
        if (stopped) return;
        const delay = Math.min(maxDelay, 500 * 2 ** attempt) * (0.7 + Math.random() * 0.6);
        attempt += 1;
        retry = window.setTimeout(connect, delay);
      };
      socket.onerror = () => socket.close();
    };
    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retry);
      window.clearInterval(ping);
      ws.current?.close();
      ws.current = null;
    };
  }, [url, enabled, maxDelay, heartbeat]);

  const emit = useCallback((event: string, data?: unknown) => sendRaw(JSON.stringify({ event, data })), [sendRaw]);
  const join = useCallback((room: string) => {
    rooms.current.add(room);
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ event: "join", data: room }));
  }, []);
  const leave = useCallback((room: string) => {
    rooms.current.delete(room);
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ event: "leave", data: room }));
  }, []);
  /** Subscribe outside `events`; returns an unsubscribe function. */
  const on = useCallback((event: string, fn: Handler) => {
    const set = extra.current.get(event) || new Set<Handler>();
    set.add(fn);
    extra.current.set(event, set);
    return () => set.delete(fn);
  }, []);

  return { connected, emit, join, leave, on };
}
