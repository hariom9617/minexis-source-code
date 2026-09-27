import type { AlertEvent } from '../types';

interface Props {
  alerts: AlertEvent[];
}

const RISK_ORDER: Record<string, number> = { safe: 0, caution: 1, warning: 2, critical: 3 };

export function AlertPanel({ alerts }: Props) {
  const sorted = [...alerts].sort(
    (a, b) => RISK_ORDER[b.risk_state] - RISK_ORDER[a.risk_state],
  );

  return (
    <section className="panel alerts-panel">
      <div className="panel-title">
        ⚠ Active Alerts
        {alerts.length > 0 && (
          <span className="count-badge" style={{ marginLeft: 8 }}>{alerts.length}</span>
        )}
      </div>
      <div className="panel-body">
        {sorted.length === 0 ? (
          <p className="empty-state">System clear — no active alerts</p>
        ) : (
          <div className="alert-list">
            {sorted.map((a, i) => (
              <div className={`alert-item ${a.risk_state}`} key={i}>
                <div className="alert-top">
                  <span className={`alert-state ${a.risk_state}`}>
                    {a.risk_state.toUpperCase()}
                  </span>
                  <span className="alert-msg">{a.message}</span>
                </div>
                <div className="alert-meta">
                  <span>Track #{a.track_id}</span>
                  {a.direction_hint && <span>📍 {a.direction_hint}</span>}
                  <span>{a.timestamp.toFixed(2)} s</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
