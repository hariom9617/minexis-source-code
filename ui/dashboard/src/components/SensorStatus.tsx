interface Props {
  thermalQuality: number;
  radarQuality: number;
}

function qualityColor(q: number): string {
  if (q >= 0.6) return 'var(--safe)';
  if (q >= 0.3) return 'var(--caution)';
  return 'var(--critical)';
}

function dotClass(q: number): string {
  if (q >= 0.4) return '';
  if (q >= 0.2) return 'low';
  return 'critical';
}

function qualityLabel(q: number): string {
  if (q >= 0.7) return 'GOOD';
  if (q >= 0.4) return 'DEGRADED';
  if (q >= 0.15) return 'POOR';
  return 'CRITICAL';
}

interface SensorCardProps {
  name: string;
  quality: number;
  icon: string;
}

function SensorCard({ name, quality, icon }: SensorCardProps) {
  const pct = Math.round(quality * 100);
  return (
    <div className="sensor-card">
      <div className="sensor-card-header">
        <span className="sensor-name">{icon} {name}</span>
        <span className={`sensor-status-dot ${dotClass(quality)}`} />
      </div>
      <div className="quality-bar-wrap">
        <div className="quality-bar">
          <div
            className="quality-fill"
            style={{ width: `${pct}%`, background: qualityColor(quality) }}
          />
        </div>
        <span className="quality-val">{pct}%</span>
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 3, fontFamily: 'var(--font-mono)', letterSpacing: '0.5px' }}>
        {qualityLabel(quality)}
      </div>
    </div>
  );
}

export function SensorStatus({ thermalQuality, radarQuality }: Props) {
  return (
    <section className="panel">
      <div className="panel-title">▣ Sensor Status</div>
      <div className="panel-body">
        <div className="sensor-grid">
          <SensorCard name="THERMAL CAMERA" quality={thermalQuality} icon="⬤" />
          <SensorCard name="RADAR" quality={radarQuality} icon="◎" />
        </div>
      </div>
    </section>
  );
}
