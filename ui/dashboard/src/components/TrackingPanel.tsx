import type { Track } from '../types';

interface Props {
  tracks: Track[];
}

const CLS_LABEL: Record<string, string> = {
  person: 'Person',
  vehicle: 'Vehicle',
  large_obstacle: 'Obstacle',
  unknown: 'Unknown',
};

export function TrackingPanel({ tracks }: Props) {
  return (
    <section className="panel tracking-panel">
      <div className="panel-title">
        ⊛ Active Tracks
        <span className="count-badge" style={{ marginLeft: 8 }}>{tracks.length}</span>
      </div>
      <div className="panel-body">
        {tracks.length === 0 ? (
          <p className="empty-state">No active tracks</p>
        ) : (
          <div className="track-list">
            {tracks.map((t) => {
              const speed = Math.hypot(t.velocity_xy[0], t.velocity_xy[1]);
              return (
                <div className="track-item" key={t.track_id}>
                  <div className="track-header">
                    <span className="track-id">TRK #{t.track_id}</span>
                    <span className="track-cls">{CLS_LABEL[t.cls] ?? t.cls}</span>
                  </div>
                  <div className="track-grid">
                    <div className="track-kv">
                      <div className="k">X</div>
                      <div className="v">{t.position_xy[0].toFixed(1)} m</div>
                    </div>
                    <div className="track-kv">
                      <div className="k">Y</div>
                      <div className="v">{t.position_xy[1].toFixed(1)} m</div>
                    </div>
                    <div className="track-kv">
                      <div className="k">Speed</div>
                      <div className="v">{speed.toFixed(1)} m/s</div>
                    </div>
                    <div className="track-kv">
                      <div className="k">Conf</div>
                      <div className="v">{(t.confidence * 100).toFixed(0)} %</div>
                    </div>
                    <div className="track-kv">
                      <div className="k">Age</div>
                      <div className="v">{t.age_frames} fr</div>
                    </div>
                    <div className="track-kv">
                      <div className="k">Miss</div>
                      <div className="v" style={{ color: t.missed_frames > 2 ? 'var(--warning)' : undefined }}>
                        {t.missed_frames}
                      </div>
                    </div>
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
