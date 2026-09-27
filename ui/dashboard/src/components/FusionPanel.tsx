import type { FusedObject } from '../types';

interface Props {
  fusedObjects: FusedObject[];
}

const CLS_LABEL: Record<string, string> = {
  person: 'Person',
  vehicle: 'Vehicle',
  large_obstacle: 'Obstacle',
  unknown: 'Unknown',
};

export function FusionPanel({ fusedObjects }: Props) {
  return (
    <section className="panel fusion-panel">
      <div className="panel-title">⊕ Adaptive Fusion</div>
      <div className="panel-body">
        <p className="fusion-caption">Evidence-aware adaptive fusion</p>
        {fusedObjects.length === 0 ? (
          <p className="empty-state">No fused objects</p>
        ) : (
          <div className="fusion-list">
            {fusedObjects.map((f, i) => {
              const tPct = (f.thermal_weight * 100).toFixed(0);
              const rPct = (f.radar_weight  * 100).toFixed(0);
              const dist = Math.hypot(f.position_xy[0], f.position_xy[1]);
              return (
                <div className="fusion-item" key={i}>
                  <div className="fusion-header">
                    <span className="fusion-cls">{CLS_LABEL[f.cls] ?? f.cls}</span>
                    <span className="fusion-conf">{(f.confidence * 100).toFixed(0)}% conf</span>
                    <span className={`agreement-badge ${f.agreement}`}>{f.agreement.replace('_', ' ')}</span>
                  </div>

                  <div className="weight-bars">
                    <div className="weight-row">
                      <span className="weight-label">Thermal</span>
                      <div className="weight-bar">
                        <div className="weight-fill-thermal" style={{ width: `${tPct}%` }} />
                      </div>
                      <span className="weight-val">{tPct}%</span>
                    </div>
                    <div className="weight-row">
                      <span className="weight-label">Radar</span>
                      <div className="weight-bar">
                        <div className="weight-fill-radar" style={{ width: `${rPct}%` }} />
                      </div>
                      <span className="weight-val">{rPct}%</span>
                    </div>
                  </div>

                  <div className="fusion-pos">
                    {dist.toFixed(1)} m &nbsp;|&nbsp;
                    ({f.position_xy[0].toFixed(1)}, {f.position_xy[1].toFixed(1)}) m &nbsp;|&nbsp;
                    Vx {f.velocity_xy[0].toFixed(1)} Vy {f.velocity_xy[1].toFixed(1)} m/s
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
