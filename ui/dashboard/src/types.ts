/**
 * TypeScript interfaces that mirror the Python FrameResult JSON payload
 * produced by common/serialization.py → frame_result_to_dict().
 *
 * Field names, types and optionality must stay in sync with the Python
 * dataclasses in common/types.py.
 *
 * Enum string values match the Python Enum .value strings exactly.
 */

// ---------------------------------------------------------------------------
// Enums (Python str-Enum → TypeScript string literal union)
// ---------------------------------------------------------------------------

export type RiskState = 'safe' | 'caution' | 'warning' | 'critical';

export type ObjectClass = 'person' | 'vehicle' | 'large_obstacle' | 'unknown';

export type AgreementState =
  | 'agreement'
  | 'partial'
  | 'conflict'
  | 'thermal_only'
  | 'radar_only';

// ---------------------------------------------------------------------------
// Perception
// ---------------------------------------------------------------------------

/**
 * ThermalDetection — one bounding-box detection from thermal_branch.
 * box_xyxy is serialized as a 4-element array (Python tuple → JSON array).
 */
export interface ThermalDetection {
  box_xyxy: [number, number, number, number]; // [x0, y0, x1, y1] pixel coords
  cls: ObjectClass;
  confidence: number;    // 0-1
  image_quality: number; // 0-1
}

/**
 * RadarCluster — one clustered detection from radar_branch.
 */
export interface RadarCluster {
  range_m: number;
  azimuth_deg: number;
  elevation_deg: number;
  doppler_mps: number;   // +ve = closing
  rcs_dbsm: number;
  snr_db: number;
  point_count: number;
  persistence: number;   // 0-1
}

// ---------------------------------------------------------------------------
// Fusion
// ---------------------------------------------------------------------------

/**
 * FusedObject — one object after adaptive fusion.
 * position_xy and velocity_xy are serialized as 2-element arrays.
 * source_thermal and source_radar are excluded by the serializer.
 */
export interface FusedObject {
  timestamp: number;
  position_xy: [number, number]; // [x_m, y_m] vehicle frame
  velocity_xy: [number, number]; // [vx_mps, vy_mps]
  cls: ObjectClass;
  confidence: number;     // 0-1, fused
  thermal_weight: number; // 0-1
  radar_weight: number;   // 0-1
  agreement: AgreementState;
}

// ---------------------------------------------------------------------------
// Tracking
// ---------------------------------------------------------------------------

/**
 * Track — a tracked object with a persistent ID.
 * history is serialized as an array of 2-element arrays.
 */
export interface Track {
  track_id: number;
  position_xy: [number, number];
  velocity_xy: [number, number];
  cls: ObjectClass;
  confidence: number;
  age_frames: number;
  missed_frames: number;
  history: [number, number][]; // recent positions, up to 20
}

// ---------------------------------------------------------------------------
// Risk / Alerts
// ---------------------------------------------------------------------------

export interface RiskAssessment {
  track_id: number;
  ttc_s: number | null;  // null when not closing / not on-path
  distance_m: number;
  risk_state: RiskState;
  path_overlap: number;  // 0-1
}

export interface AlertEvent {
  timestamp: number;
  risk_state: RiskState;
  track_id: number;
  message: string;
  direction_hint: string | null;
}

// ---------------------------------------------------------------------------
// Latency map
// ---------------------------------------------------------------------------

export interface LatencyMap {
  perception: number;
  fusion: number;
  tracking: number;
  risk: number;
  alerts: number;
  total: number;
  [key: string]: number; // allow future keys
}

// ---------------------------------------------------------------------------
// Full frame payload (top-level WebSocket message)
// ---------------------------------------------------------------------------

/**
 * LiveFrame — the exact JSON structure broadcast over WS /ws/live.
 * Produced by frame_result_to_dict() in common/serialization.py.
 */
export interface LiveFrame {
  timestamp: number;
  frame_number: number;
  sync_skew_s: number;
  thermal_quality: number; // 0-1
  radar_quality: number;   // 0-1
  highest_risk: RiskState;
  scenario: string;        // active demo scenario, e.g. "CRITICAL" or "DEFAULT"
  latency: LatencyMap;
  thermal_detections: ThermalDetection[];
  radar_clusters: RadarCluster[];
  fused_objects: FusedObject[];
  tracks: Track[];
  risks: RiskAssessment[];
  alerts: AlertEvent[];
}

// Keepalive ping sent by backend when no frame is available
export interface PingMessage {
  type: 'ping';
}

export type WsMessage = LiveFrame | PingMessage;

// ---------------------------------------------------------------------------
// Connection state
// ---------------------------------------------------------------------------

export type ConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'reconnecting'
  | 'error';

// ---------------------------------------------------------------------------
// Demo / simulation mode
// ---------------------------------------------------------------------------

export interface ScenarioInfo {
  name: string;
  description: string;
}

export interface ScenariosResponse {
  scenarios: ScenarioInfo[];
  current: string;
}

// ---------------------------------------------------------------------------
// Sensor mode (from GET /api/config/mode)
// ---------------------------------------------------------------------------

export interface SensorModeResponse {
  thermal: 'synthetic' | 'real';
  radar:   'synthetic' | 'real';
  label:   string;   // "SYNTHETIC" | "REAL" | "MIXED (...)"
}
