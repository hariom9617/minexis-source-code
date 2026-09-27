import type { ThermalDetection } from '../types';

interface Props {
  detections: ThermalDetection[];
}

const CLS_ICON: Record<string, string> = {
  person: '🚶',
  vehicle: '🚛',
  large_obstacle: '⬛',
  unknown: '?',
};

export function DetectionPanel({ detections }: Props) {
  return (
    <section className="panel">
      <div className="panel-title">
        ⊞ Thermal Detections
        <span className="count-badge" style={{ marginLeft: 8 }}>{detections.length}</span>
      </div>
      <div className="panel-body">
        {detections.length === 0 ? (
          <p className="empty-state">No thermal detections</p>
        ) : (
          <div className="detection-list">
            {detections.map((d, i) => {
              const [x0, y0, x1, y1] = d.box_xyxy;
              const w = (x1 - x0).toFixed(0);
              const h = (y1 - y0).toFixed(0);
              return (
                <div className="detection-item" key={i}>
                  <span className="det-label">Class</span>
                  <span className="det-value">
                    {CLS_ICON[d.cls] ?? '?'} {d.cls}
                  </span>
                  <span className="det-label">Confidence</span>
                  <span className="det-value">{(d.confidence * 100).toFixed(0)} %</span>
                  <span className="det-label">Box (px)</span>
                  <span className="det-value">{w} × {h}</span>
                  <span className="det-label">Img quality</span>
                  <span className="det-value">{(d.image_quality * 100).toFixed(0)} %</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
