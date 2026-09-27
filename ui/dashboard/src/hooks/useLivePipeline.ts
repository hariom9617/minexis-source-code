/**
 * useLivePipeline — WebSocket hook for the MINEXIS live stream.
 *
 * Connects to WS_LIVE_URL, parses each incoming JSON message and exposes
 * the latest LiveFrame.  Reconnects automatically with exponential back-off
 * after any disconnect or error.
 *
 * Only the most recent frame is kept in state — the dashboard is a live
 * console, not a replay system.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { WS_LIVE_URL } from '../config';
import type { ConnectionState, LiveFrame, WsMessage } from '../types';

const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS  = 16_000;

export interface LivePipelineState {
  data: LiveFrame | null;
  connectionState: ConnectionState;
  lastUpdate: number | null;   // Date.now() of last received frame
  reconnect: () => void;       // force an immediate reconnect
}

export function useLivePipeline(): LivePipelineState {
  const [data, setData]                   = useState<LiveFrame | null>(null);
  const [connState, setConnState]         = useState<ConnectionState>('connecting');
  const [lastUpdate, setLastUpdate]       = useState<number | null>(null);

  const wsRef        = useRef<WebSocket | null>(null);
  const retryDelay   = useRef<number>(RECONNECT_BASE_MS);
  const retryTimer   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMounted    = useRef(true);
  const forceRetry   = useRef(false);

  const connect = useCallback(() => {
    // Clean up any existing socket before opening a new one.
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    if (!isMounted.current) return;

    setConnState('connecting');

    let ws: WebSocket;
    try {
      ws = new WebSocket(WS_LIVE_URL);
    } catch {
      if (!isMounted.current) return;
      setConnState('error');
      scheduleReconnect();
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMounted.current) return;
      setConnState('connected');
      retryDelay.current = RECONNECT_BASE_MS; // reset back-off on successful connect
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      if (!isMounted.current) return;
      try {
        const msg = JSON.parse(event.data) as WsMessage;
        // Ignore keepalive pings
        if ('type' in msg && msg.type === 'ping') return;
        setData(msg as LiveFrame);
        setLastUpdate(Date.now());
      } catch {
        // Malformed JSON — ignore silently
      }
    };

    ws.onerror = () => {
      if (!isMounted.current) return;
      setConnState('error');
    };

    ws.onclose = () => {
      if (!isMounted.current) return;
      wsRef.current = null;
      setConnState('reconnecting');
      scheduleReconnect();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function scheduleReconnect() {
    if (!isMounted.current) return;
    if (retryTimer.current) clearTimeout(retryTimer.current);
    const delay = forceRetry.current ? 0 : retryDelay.current;
    forceRetry.current = false;
    retryDelay.current = Math.min(retryDelay.current * 2, RECONNECT_MAX_MS);
    retryTimer.current = setTimeout(() => {
      if (isMounted.current) connect();
    }, delay);
  }

  // Public reconnect() — resets back-off and reconnects immediately.
  const reconnect = useCallback(() => {
    retryDelay.current = RECONNECT_BASE_MS;
    forceRetry.current = true;
    if (retryTimer.current) {
      clearTimeout(retryTimer.current);
      retryTimer.current = null;
    }
    connect();
  }, [connect]);

  useEffect(() => {
    isMounted.current = true;
    connect();
    return () => {
      isMounted.current = false;
      if (retryTimer.current) clearTimeout(retryTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return {
    data,
    connectionState: connState,
    lastUpdate,
    reconnect,
  };
}
