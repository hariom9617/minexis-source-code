import type { LatencyMap } from '../types';

interface Props {
  latency: LatencyMap | null;
  frameNumber: number | null;
  syncSkewS: number | null;
  thermalQuality: number | null;
  radarQuality: number | null;
}

interface MetricItemProps {
  label: string;
  value: string;
  unit?: string;
  warn?: boolean;
}

function MetricItem({ label, value, unit, warn }: MetricItemProps) {
  return (
    <div className="metric-item">
      <span className="metric-label">{label}</span>
      <span
        className="metric-value"
        style={warn ? { color: 'var(--warning)' } : undefined}
      >
        {value}
      </span>
      {unit && <span className="metric-unit">{unit}</span>}
    </div>
  );
}

export function MetricsPanel({
  latency,
  frameNumber,
  syncSkewS,
  thermalQuality,
  radarQuality,
}: Props) {
  const lat = latency;
  const totalWarn = lat != null && lat.total > 100;

  return (
    <div className="metrics-panel">
      {/* Latency block */}
      <MetricItem label="Perception"  value={lat ? lat.perception.toFixed(1) : '—'}  unit="ms" />
      <MetricItem label="Fusion"      value={lat ? lat.fusion.toFixed(1) : '—'}      unit="ms" />
      <MetricItem label="Tracking"    value={lat ? lat.tracking.toFixed(1) : '—'}    unit="ms" />
      <MetricItem label="Risk"        value={lat ? lat.risk.toFixed(1) : '—'}        unit="ms" />
      <MetricItem label="Alerts"      value={lat ? lat.alerts.toFixed(1) : '—'}      unit="ms" />
      <MetricItem label="Total"       value={lat ? lat.total.toFixed(1) : '—'}       unit="ms" warn={totalWarn} />

      {/* Visual divider */}
      <div className="divider" />

      {/* Pipeline state block */}
      <MetricItem label="Frame #"     value={frameNumber != null ? String(frameNumber) : '—'} />
      <MetricItem
        label="Sync skew"
        value={syncSkewS != null ? (syncSkewS * 1000).toFixed(1) : '—'}
        unit="ms"
        warn={syncSkewS != null && syncSkewS > 0.06}
      />
      <MetricItem
        label="Thermal Q"
        value={thermalQuality != null ? (thermalQuality * 100).toFixed(0) : '—'}
        unit="%"
        warn={thermalQuality != null && thermalQuality < 0.3}
      />
      <MetricItem
        label="Radar Q"
        value={radarQuality != null ? (radarQuality * 100).toFixed(0) : '—'}
        unit="%"
        warn={radarQuality != null && radarQuality < 0.3}
      />
    </div>
  );
}
