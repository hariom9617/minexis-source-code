import type { LiveFrame, RiskAssessment } from '../types';

interface Props {
  frame: LiveFrame | null;
}

const RISK_ICON: Record<string, string> = {
  safe:     '✓',
  caution:  '◆',
  warning:  '▲',
  critical: '⬟',
};

const RISK_LABEL: Record<string, string> = {
  safe:     'ALL CLEAR',
  caution:  'CAUTION',
  warning:  'WARNING',
  critical: 'CRITICAL',
};

function worstRisk(risks: RiskAssessment[]): RiskAssessment | null {
  const order: Record<string, number> = { safe: 0, caution: 1, warning: 2, critical: 3 };
  if (!risks.length) return null;
  return risks.reduce((a, b) => (order[b.risk_state] > order[a.risk_state] ? b : a));
}

export function RiskIndicator({ frame }: Props) {
  const level = frame?.highest_risk ?? 'safe';
  const threat = frame ? worstRisk(frame.risks) : null;

  return (
    <section className="panel risk-panel">
      <div className="panel-title">◈ Risk Status</div>
      <div className="risk-state-block">
        <div className={`risk-badge ${level}`}>
          {RISK_ICON[level]} {RISK_LABEL[level]}
        </div>

        <div className="risk-details">
          {threat ? (
            <>
              <div className="risk-row">
                <span className="label">Track</span>
                <span className="value highlight">#{threat.track_id}</span>
              </div>
              <div className="risk-row">
                <span className="label">Distance</span>
                <span className="value">{threat.distance_m.toFixed(1)} m</span>
              </div>
              <div className="risk-row">
                <span className="label">TTC</span>
                <span className="value">
                  {threat.ttc_s != null ? threat.ttc_s.toFixed(1) + ' s' : 'N/A'}
                </span>
              </div>
              <div className="risk-row">
                <span className="label">Path overlap</span>
                <span className="value">{(threat.path_overlap * 100).toFixed(0)} %</span>
              </div>
              {frame?.alerts.find(a => a.track_id === threat.track_id)?.direction_hint && (
                <div className="risk-row">
                  <span className="label">Direction</span>
                  <span className="value highlight">
                    {frame.alerts.find(a => a.track_id === threat.track_id)?.direction_hint}
                  </span>
                </div>
              )}
            </>
          ) : (
            <p className="empty-state" style={{ textAlign: 'center' }}>
              No active threats detected
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
