/**
 * Lila Framework WebSocket Client (Socket.io-style lightweight client)
 * High performance, zero dependencies, auto-reconnection, event-driven, and room support.
 */

(function (global) {
  'use strict';

  class LilaWS {
    constructor(url, options = {}) {
      this.url = url || (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
      this.options = Object.assign({
        autoConnect: true,
        reconnect: true,
        reconnectDelay: 1000,
        maxReconnectDelay: 10000,
        reconnectAttempts: Infinity,
        heartbeatInterval: 25000
      }, options);

      this.ws = null;
      this.listeners = new Map();
      this.queue = [];
      this.reconnectCount = 0;
      this.isConnecting = false;
      this.heartbeatTimer = null;
      this.rooms = new Set();

      if (this.options.autoConnect) {
        this.connect();
      }
    }

    connect() {
      if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
        return;
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
        this._scheduleReconnect();
      }
    }

    on(event, callback) {
      if (!this.listeners.has(event)) {
        this.listeners.set(event, new Set());
      }
      this.listeners.get(event).add(callback);
      return this;
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
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(payload);
      } else {
        this.queue.push(payload);
      }
      return this;
    }

    join(room) {
      this.rooms.add(room);
      return this.emit('join', room);
    }

    leave(room) {
      this.rooms.delete(room);
      return this.emit('leave', room);
    }

    disconnect() {
      this.options.reconnect = false;
      this._stopHeartbeat();
      if (this.ws) {
        this.ws.close();
      }
    }

    _onOpen(e) {
      this.isConnecting = false;
      this.reconnectCount = 0;
      this._startHeartbeat();

      this.rooms.forEach(room => this.emit('join', room));

      while (this.queue.length > 0) {
        const payload = this.queue.shift();
        this.ws.send(payload);
      }

      this._trigger('connect', e);
      this._trigger('open', e);
    }

    _onMessage(e) {
      try {
        let raw = e.data;
        if (raw instanceof ArrayBuffer) {
          raw = new TextDecoder('utf-8').decode(raw);
        }
        const msg = JSON.parse(raw);
        if (msg && msg.event) {
          if (msg.event === 'pong') {
            return;
          }
          this._trigger(msg.event, msg.data);
        } else {
          this._trigger('message', msg);
        }
      } catch (err) {
        this._trigger('message', e.data);
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

      if (this.options.reconnect) {
        this._scheduleReconnect();
      }
    }

    _scheduleReconnect() {
      if (this.reconnectCount >= this.options.reconnectAttempts) {
        this._trigger('reconnect_failed');
        return;
      }

      this.reconnectCount++;
      const delay = Math.min(
        this.options.reconnectDelay * Math.pow(1.5, this.reconnectCount - 1),
        this.options.maxReconnectDelay
      );

      this._trigger('reconnecting', { attempt: this.reconnectCount, delay });
      setTimeout(() => this.connect(), delay);
    }

    _startHeartbeat() {
      this._stopHeartbeat();
      if (this.options.heartbeatInterval > 0) {
        this.heartbeatTimer = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.emit('ping', Date.now());
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
        callbacks.forEach(cb => {
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
