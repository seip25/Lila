/**
 * Lila Framework WebSocket Client (Socket.io-style lightweight client)
 * Zero dependencies: auto-reconnection with backoff, events, rooms, heartbeat.
 *
 *   const socket = lilaWS("/ws/chat");          // relative URLs are fine
 *   socket.on("chat:message", (data) => ...);
 *   socket.join("room-1").emit("chat:message", { text: "hi" });
 *
 * SPA-aware: sockets created by a page are closed when the Lila router leaves
 * that page (pass { persist: true } to keep one alive across navigations).
 */

(function (global) {
  'use strict';

  const MAX_QUEUE = 500;
  // Server refused us on purpose: do not hammer it with reconnects.
  const NO_RECONNECT_CODES = [1003, 1008, 1009, 1011];

  function resolveUrl(url) {
    const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
    if (!url) return proto + location.host + '/ws';
    if (/^wss?:\/\//i.test(url)) return url;
    if (/^https?:\/\//i.test(url)) return url.replace(/^http/i, 'ws');
    if (url.startsWith('//')) return proto.slice(0, -2) + url;
    return proto + location.host + (url.startsWith('/') ? url : '/' + url);
  }

  class LilaWS {
    constructor(url, options = {}) {
      this.url = resolveUrl(url);
      this.options = Object.assign({
        autoConnect: true,
        reconnect: true,
        reconnectDelay: 1000,
        maxReconnectDelay: 10000,
        reconnectAttempts: Infinity,
        heartbeatInterval: 25000,
        persist: false,
        noReconnectCodes: NO_RECONNECT_CODES
      }, options);

      this.ws = null;
      this.listeners = new Map();
      this.queue = [];
      this.reconnectCount = 0;
      this.isConnecting = false;
      this.heartbeatTimer = null;
      this.reconnectTimer = null;
      this.manualClose = false;
      this.rooms = new Set();

      this._onOnline = () => {
        if (!this.manualClose && !this.connected) {
          this.reconnectCount = 0;
          this.connect();
        }
      };
      if (typeof window !== 'undefined') {
        window.addEventListener('online', this._onOnline);
        if (!this.options.persist) {
          this._onLeavePage = () => this.disconnect();
          window.addEventListener('lila:before-swap', this._onLeavePage, { once: true });
        }
      }

      if (this.options.autoConnect) {
        this.connect();
      }
    }

    get connected() {
      return !!(this.ws && this.ws.readyState === WebSocket.OPEN);
    }

    connect() {
      this.manualClose = false;
      this._clearReconnect();
      if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
        return this;
      }

      this.isConnecting = true;
      try {
        this.ws = new WebSocket(this.url);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = (e) => this._onOpen(e);
        this.ws.onmessage = (e) => this._onMessage(e);
        this.ws.onerror = (e) => this._onError(e);
        this.ws.onclose = (e) => this._onClose(e);
      } catch (err) {
        this.isConnecting = false;
        this._scheduleReconnect();
      }
      return this;
    }

    on(event, callback) {
      if (!this.listeners.has(event)) {
        this.listeners.set(event, new Set());
      }
      this.listeners.get(event).add(callback);
      return this;
    }

    once(event, callback) {
      const wrapper = (data) => {
        this.off(event, wrapper);
        callback(data);
      };
      return this.on(event, wrapper);
    }

    off(event, callback) {
      if (this.listeners.has(event)) {
        if (callback) {
          this.listeners.get(event).delete(callback);
        } else {
          this.listeners.delete(event);
        }
      }
      return this;
    }

    emit(event, data = null) {
      const payload = JSON.stringify({ event, data });
      if (this.connected) {
        this.ws.send(payload);
      } else if (!this.manualClose) {
        // Bounded offline buffer: oldest messages are dropped first.
        if (this.queue.length >= MAX_QUEUE) this.queue.shift();
        this.queue.push(payload);
      }
      return this;
    }

    join(room) {
      room = String(room);
      this.rooms.add(room);
      // While offline the room is (re)joined once in _onOpen; no duplicate.
      if (this.connected) this.ws.send(JSON.stringify({ event: 'join', data: room }));
      return this;
    }

    leave(room) {
      room = String(room);
      this.rooms.delete(room);
      if (this.connected) this.ws.send(JSON.stringify({ event: 'leave', data: room }));
      return this;
    }

    disconnect(code = 1000, reason = '') {
      this.manualClose = true;
      this.queue = [];
      this._clearReconnect();
      this._stopHeartbeat();
      if (typeof window !== 'undefined') {
        window.removeEventListener('online', this._onOnline);
        if (this._onLeavePage) window.removeEventListener('lila:before-swap', this._onLeavePage);
      }
      if (this.ws && this.ws.readyState <= WebSocket.OPEN) {
        try { this.ws.close(code, reason); } catch (err) { }
      }
      return this;
    }

    close(code, reason) {
      return this.disconnect(code, reason);
    }

    _onOpen(e) {
      this.isConnecting = false;
      this.reconnectCount = 0;
      this._startHeartbeat();

      this.rooms.forEach(room => this.ws.send(JSON.stringify({ event: 'join', data: room })));

      const pending = this.queue;
      this.queue = [];
      for (const payload of pending) {
        this.ws.send(payload);
      }

      this._trigger('connect', e);
      this._trigger('open', e);
    }

    _onMessage(e) {
      let msg;
      try {
        let raw = e.data;
        if (raw instanceof ArrayBuffer) {
          raw = new TextDecoder('utf-8').decode(raw);
        }
        if (raw === 'pong') return;
        msg = JSON.parse(raw);
      } catch (err) {
        this._trigger('message', e.data);
        return;
      }
      if (msg && typeof msg === 'object' && msg.event) {
        if (msg.event === 'pong') return;
        this._trigger(msg.event, msg.data);
      } else {
        this._trigger('message', msg);
      }
    }

    _onError(e) {
      this._trigger('error', e);
    }

    _onClose(e) {
      this.isConnecting = false;
      this._stopHeartbeat();
      this._trigger('disconnect', e);
      this._trigger('close', e);

      const refused = e && this.options.noReconnectCodes.indexOf(e.code) !== -1;
      if (this.options.reconnect && !this.manualClose && !refused) {
        this._scheduleReconnect();
      }
    }

    _scheduleReconnect() {
      if (this.manualClose || this.reconnectTimer) return;
      if (this.reconnectCount >= this.options.reconnectAttempts) {
        this._trigger('reconnect_failed');
        return;
      }

      this.reconnectCount++;
      const base = Math.min(
        this.options.reconnectDelay * Math.pow(1.5, this.reconnectCount - 1),
        this.options.maxReconnectDelay
      );
      // Jitter avoids every tab reconnecting at the same instant after a deploy.
      const delay = Math.round(base * (0.8 + Math.random() * 0.4));

      this._trigger('reconnecting', { attempt: this.reconnectCount, delay });
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        if (!this.manualClose) this.connect();
      }, delay);
    }

    _clearReconnect() {
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    }

    _startHeartbeat() {
      this._stopHeartbeat();
      if (this.options.heartbeatInterval > 0) {
        this.heartbeatTimer = setInterval(() => {
          // Pings are never queued while offline.
          if (this.connected) {
            this.ws.send(JSON.stringify({ event: 'ping', data: Date.now() }));
          }
        }, this.options.heartbeatInterval);
      }
    }

    _stopHeartbeat() {
      if (this.heartbeatTimer) {
        clearInterval(this.heartbeatTimer);
        this.heartbeatTimer = null;
      }
    }

    _trigger(event, data) {
      const callbacks = this.listeners.get(event);
      if (callbacks) {
        Array.from(callbacks).forEach(cb => {
          try {
            cb(data);
          } catch (err) {
            console.error(`[LilaWS] Error in listener for event "${event}":`, err);
          }
        });
      }
    }
  }

  function lilaWS(url, options) {
    return new LilaWS(url, options);
  }

  global.LilaWS = LilaWS;
  global.lilaWS = lilaWS;

})(typeof window !== 'undefined' ? window : this);
