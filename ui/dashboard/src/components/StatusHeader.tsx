import { useEffect, useState } from 'react';
import type { ConnectionState, LiveFrame, SensorModeResponse } from '../types';
import { HTTP_BASE } from '../config';

interface Props {
  frame: LiveFrame | null;
  connectionState: ConnectionState;
  lastUpdate: number | null;
  onReconnect: () => void;
}

const CONN_LABELS: Record<ConnectionState, string> = {
  connected:    'CONNECTED',
  connecting:   'CONNECTING',
  reconnecting: 'RECONNECTING',
  disconnected: 'DISCONNECTED',
  error:        'ERROR',
};

export function StatusHeader({ frame, connectionState, lastUpdate, onReconnect }: Props) {
  const isLive = connectionState === 'connected' && frame !== null;
  const needsReconnect = connectionState === 'disconnected' || connectionState === 'error';

  // Fetch sensor mode once on mount — it never changes at runtime
  const [sensorMode, setSensorMode] = useState<SensorModeResponse | null>(null);
  useEffect(() => {
    fetch(`${HTTP_BASE}/api/config/mode`)
      .then(r => r.json())
      .then((data: SensorModeResponse) => setSensorMode(data))
      .catch(() => { /* ignore — backend may not be up yet */ });
  }, []);

  const modeLabel = sensorMode?.label ?? '…';
  const isReal    = sensorMode?.label === 'REAL';

  return (
    <header className="panel header">
      <div className="header-brand">
        <span className="header-logo">MINEXIS</span>
        <span className="header-sub">Multi-Sensor Intelligent Navigation &amp; Emergency Safety System</span>
      </div>

      {isLive && (
        <div className="header-live">
          <div className="pulse" />
          LIVE
        </div>
      )}

      <div className={`header-conn ${connectionState}`}>
        {CONN_LABELS[connectionState]}
      </div>

      {/* Sensor mode badge */}
      <div
        className="header-sensor-mode"
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          letterSpacing: '1px',
          padding: '2px 8px',
          borderRadius: 3,
          border: `1px solid ${isReal ? 'rgba(167,139,250,0.4)' : 'var(--border)'}`,
          background: isReal ? 'rgba(167,139,250,0.08)' : 'transparent',
          color: isReal ? '#a78bfa' : 'var(--text-dim)',
          whiteSpace: 'nowrap' as const,
        }}
        title="Sensor data source — set in config/hardware.yaml"
      >
        SENSOR: {modeLabel}
      </div>

      {needsReconnect && (
        <button className="reconnect-btn" onClick={onReconnect}>
          RECONNECT
        </button>
      )}

      <div className="header-meta">
        <span>FRAME&nbsp;<span>{frame?.frame_number ?? '—'}</span></span>
        <span>T&nbsp;<span>{frame ? frame.timestamp.toFixed(2) + 's' : '—'}</span></span>
        {lastUpdate && (
          <span>UPD&nbsp;<span>{new Date(lastUpdate).toLocaleTimeString()}</span></span>
        )}
      </div>
    </header>
  );
}
