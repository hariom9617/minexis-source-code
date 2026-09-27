/**
 * Dashboard frontend tests.
 *
 * Uses Vitest + @testing-library/react + jsdom.
 * The WebSocket is not actually opened — useLivePipeline is either
 * mocked or tested via a fake WS server depending on the test.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
// ---------------------------------------------------------------------------
// Mock WebSocket globally so useLivePipeline doesn't try to open a real socket
// ---------------------------------------------------------------------------

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  onopen:    ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror:   ((e: Event) => void) | null = null;
  onclose:   ((e: CloseEvent) => void) | null = null;

  constructor(public url: string) {
    // Simulate async open
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));
    }, 10);
  }

  send(_data: string) { /* no-op */ }
  close() {
    this.readyState = MockWebSocket.CLOSED;
  }

  // Test helper: push a message as if received from server
  receiveMessage(data: unknown) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) }));
  }
}

let wsInstance: MockWebSocket | null = null;

// Default sensor mode response for any fetch call that isn't specifically overridden
const DEFAULT_SENSOR_MODE = { thermal: 'synthetic', radar: 'synthetic', label: 'SYNTHETIC' };

beforeEach(() => {
  wsInstance = null;
  vi.stubGlobal('WebSocket', class extends MockWebSocket {
    constructor(url: string) {
      super(url);
      wsInstance = this;
    }
  });
  // Stub fetch globally so StatusHeader's useEffect (GET /api/config/mode)
  // and DemoControls' useEffect (GET /api/scenarios) don't hit a real network.
  // Individual tests that need specific fetch behaviour override this.
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => DEFAULT_SENSOR_MODE,
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Helpers: minimal LiveFrame payload
// ---------------------------------------------------------------------------

import type { LiveFrame } from '../types';

function makeLiveFrame(overrides: Partial<LiveFrame> = {}): LiveFrame {
  return {
    timestamp: 1.5,
    frame_number: 42,
    sync_skew_s: 0.005,
    thermal_quality: 0.75,
    radar_quality: 0.60,
    highest_risk: 'caution',
    scenario: 'SAFE',
    latency: { perception: 1.2, fusion: 0.3, tracking: 0.1, risk: 0.05, alerts: 0.02, total: 1.67 },
    thermal_detections: [
      { box_xyxy: [100, 80, 140, 130], cls: 'person', confidence: 0.85, image_quality: 0.75 },
    ],
    radar_clusters: [
      { range_m: 30, azimuth_deg: 1.5, elevation_deg: 0, doppler_mps: 3.2,
        rcs_dbsm: 8, snr_db: 18, point_count: 2, persistence: 0.6 },
    ],
    fused_objects: [
      { timestamp: 1.5, position_xy: [0.8, 29.9], velocity_xy: [-0.09, -3.2],
        cls: 'person', confidence: 0.72, thermal_weight: 0.55, radar_weight: 0.45,
        agreement: 'agreement' },
    ],
    tracks: [
      { track_id: 1, position_xy: [0.8, 29.9], velocity_xy: [-0.09, -3.2],
        cls: 'person', confidence: 0.72, age_frames: 5, missed_frames: 0,
        history: [[0.8, 30.0]] },
    ],
    risks: [
      { track_id: 1, ttc_s: 9.3, distance_m: 29.9, risk_state: 'caution', path_overlap: 0.73 },
    ],
    alerts: [
      { timestamp: 1.5, risk_state: 'caution', track_id: 1,
        message: 'Object detected ahead', direction_hint: 'ahead' },
    ],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Component imports
// ---------------------------------------------------------------------------

import App from '../App';
import { RiskIndicator }  from '../components/RiskIndicator';
import { SensorStatus }   from '../components/SensorStatus';
import { DetectionPanel } from '../components/DetectionPanel';
import { TrackingPanel }  from '../components/TrackingPanel';
import { FusionPanel }    from '../components/FusionPanel';
import { AlertPanel }     from '../components/AlertPanel';
import { MetricsPanel }   from '../components/MetricsPanel';
import { RadarView }      from '../components/RadarView';
import { StatusHeader }   from '../components/StatusHeader';

// ---------------------------------------------------------------------------
// App renders
// ---------------------------------------------------------------------------

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    // Header brand should be present
    expect(screen.getByText('MINEXIS')).toBeInTheDocument();
  });

  it('shows CONNECTED when WebSocket opens', async () => {
    render(<App />);
    // Wait for the mock WS to "open"
    await new Promise(r => setTimeout(r, 50));
    expect(screen.getByText('CONNECTED')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// RiskIndicator — all four risk states
// ---------------------------------------------------------------------------

describe('RiskIndicator', () => {
  it('renders SAFE state', () => {
    const frame = makeLiveFrame({ highest_risk: 'safe', risks: [] });
    render(<RiskIndicator frame={frame} />);
    expect(screen.getByText(/ALL CLEAR/i)).toBeInTheDocument();
  });

  it('renders CAUTION state', () => {
    const frame = makeLiveFrame({ highest_risk: 'caution' });
    render(<RiskIndicator frame={frame} />);
    expect(screen.getByText(/CAUTION/i)).toBeInTheDocument();
  });

  it('renders WARNING state', () => {
    const frame = makeLiveFrame({
      highest_risk: 'warning',
      risks: [{ track_id: 1, ttc_s: 5.0, distance_m: 20, risk_state: 'warning', path_overlap: 0.8 }],
    });
    render(<RiskIndicator frame={frame} />);
    expect(screen.getByText(/WARNING/i)).toBeInTheDocument();
  });

  it('renders CRITICAL state', () => {
    const frame = makeLiveFrame({
      highest_risk: 'critical',
      risks: [{ track_id: 1, ttc_s: 1.5, distance_m: 8, risk_state: 'critical', path_overlap: 0.95 }],
    });
    render(<RiskIndicator frame={frame} />);
    expect(screen.getByText(/CRITICAL/i)).toBeInTheDocument();
  });

  it('renders with null frame gracefully', () => {
    render(<RiskIndicator frame={null} />);
    expect(screen.getByText(/ALL CLEAR/i)).toBeInTheDocument();
  });

  it('shows TTC when available', () => {
    const frame = makeLiveFrame({
      highest_risk: 'warning',
      risks: [{ track_id: 1, ttc_s: 5.5, distance_m: 20, risk_state: 'warning', path_overlap: 0.8 }],
    });
    render(<RiskIndicator frame={frame} />);
    expect(screen.getByText(/5\.5 s/)).toBeInTheDocument();
  });

  it('shows N/A when ttc_s is null', () => {
    const frame = makeLiveFrame({
      risks: [{ track_id: 1, ttc_s: null, distance_m: 20, risk_state: 'caution', path_overlap: 0.5 }],
    });
    render(<RiskIndicator frame={frame} />);
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// SensorStatus
// ---------------------------------------------------------------------------

describe('SensorStatus', () => {
  it('renders thermal and radar quality bars', () => {
    render(<SensorStatus thermalQuality={0.75} radarQuality={0.60} />);
    // Sensor name spans include an icon prefix + whitespace, use partial match
    expect(screen.getByText(/THERMAL CAMERA/)).toBeInTheDocument();
    expect(screen.getByText(/RADAR/)).toBeInTheDocument();
    // quality-val span renders as two adjacent text nodes: number + "%"
    // getByText regex matches on the full textContent of the element
    expect(screen.getByText((content) => content.replace(/\s/g, '') === '75%')).toBeInTheDocument();
    expect(screen.getByText((content) => content.replace(/\s/g, '') === '60%')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// DetectionPanel
// ---------------------------------------------------------------------------

describe('DetectionPanel', () => {
  it('shows empty state with no detections', () => {
    render(<DetectionPanel detections={[]} />);
    expect(screen.getByText('No thermal detections')).toBeInTheDocument();
  });

  it('renders a detection with class and confidence', () => {
    const frame = makeLiveFrame();
    render(<DetectionPanel detections={frame.thermal_detections} />);
    expect(screen.getByText(/person/i)).toBeInTheDocument();
    expect(screen.getByText('85 %')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// TrackingPanel
// ---------------------------------------------------------------------------

describe('TrackingPanel', () => {
  it('shows empty state with no tracks', () => {
    render(<TrackingPanel tracks={[]} />);
    expect(screen.getByText('No active tracks')).toBeInTheDocument();
  });

  it('renders track ID and position', () => {
    const frame = makeLiveFrame();
    render(<TrackingPanel tracks={frame.tracks} />);
    expect(screen.getByText('TRK #1')).toBeInTheDocument();
    expect(screen.getByText('29.9 m')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// FusionPanel
// ---------------------------------------------------------------------------

describe('FusionPanel', () => {
  it('shows empty state with no fused objects', () => {
    render(<FusionPanel fusedObjects={[]} />);
    expect(screen.getByText('No fused objects')).toBeInTheDocument();
  });

  it('renders agreement badge and weights', () => {
    const frame = makeLiveFrame();
    render(<FusionPanel fusedObjects={frame.fused_objects} />);
    expect(screen.getByText('agreement')).toBeInTheDocument();
    expect(screen.getByText('55%')).toBeInTheDocument();
    expect(screen.getByText('45%')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// AlertPanel
// ---------------------------------------------------------------------------

describe('AlertPanel', () => {
  it('shows clear message with no alerts', () => {
    render(<AlertPanel alerts={[]} />);
    expect(screen.getByText(/System clear/i)).toBeInTheDocument();
  });

  it('renders an alert message and direction hint', () => {
    const frame = makeLiveFrame();
    render(<AlertPanel alerts={frame.alerts} />);
    expect(screen.getByText('Object detected ahead')).toBeInTheDocument();
    // direction_hint is rendered with a 📍 prefix — use getAllByText for the hint
    const hints = screen.getAllByText(/ahead/);
    expect(hints.length).toBeGreaterThanOrEqual(1);
  });

  it('sorts highest risk first', () => {
    const alerts: LiveFrame['alerts'] = [
      { timestamp: 1, risk_state: 'caution',  track_id: 1, message: 'Caution msg',  direction_hint: null },
      { timestamp: 1, risk_state: 'critical', track_id: 2, message: 'Critical msg', direction_hint: null },
      { timestamp: 1, risk_state: 'warning',  track_id: 3, message: 'Warning msg',  direction_hint: null },
    ];
    render(<AlertPanel alerts={alerts} />);
    const items = screen.getAllByText(/msg/);
    expect(items[0].textContent).toBe('Critical msg');
    expect(items[1].textContent).toBe('Warning msg');
    expect(items[2].textContent).toBe('Caution msg');
  });
});

// ---------------------------------------------------------------------------
// MetricsPanel
// ---------------------------------------------------------------------------

describe('MetricsPanel', () => {
  it('renders — with data', () => {
    const frame = makeLiveFrame();
    render(
      <MetricsPanel
        latency={frame.latency}
        frameNumber={frame.frame_number}
        syncSkewS={frame.sync_skew_s}
        thermalQuality={frame.thermal_quality}
        radarQuality={frame.radar_quality}
      />,
    );
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('1.7')).toBeInTheDocument(); // total latency 1.67 → 1.7
  });

  it('renders — with null data (no crash)', () => {
    render(
      <MetricsPanel
        latency={null}
        frameNumber={null}
        syncSkewS={null}
        thermalQuality={null}
        radarQuality={null}
      />,
    );
    // Multiple '—' placeholders expected
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// RadarView
// ---------------------------------------------------------------------------

describe('RadarView', () => {
  it('shows empty state with no clusters', () => {
    render(<RadarView clusters={[]} />);
    expect(screen.getByText('No radar targets')).toBeInTheDocument();
  });

  it('renders SVG with clusters present', () => {
    const frame = makeLiveFrame();
    const { container } = render(<RadarView clusters={frame.radar_clusters} />);
    const circles = container.querySelectorAll('circle');
    expect(circles.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// StatusHeader
// ---------------------------------------------------------------------------

describe('StatusHeader', () => {
  it('renders MINEXIS brand', () => {
    render(
      <StatusHeader
        frame={null}
        connectionState="connecting"
        lastUpdate={null}
        onReconnect={() => {}}
      />,
    );
    expect(screen.getByText('MINEXIS')).toBeInTheDocument();
  });

  it('shows frame number when frame is available', () => {
    const frame = makeLiveFrame({ frame_number: 99 });
    render(
      <StatusHeader
        frame={frame}
        connectionState="connected"
        lastUpdate={Date.now()}
        onReconnect={() => {}}
      />,
    );
    expect(screen.getByText('99')).toBeInTheDocument();
  });

  it('shows reconnect button when disconnected', () => {
    render(
      <StatusHeader
        frame={null}
        connectionState="disconnected"
        lastUpdate={null}
        onReconnect={() => {}}
      />,
    );
    expect(screen.getByRole('button', { name: /reconnect/i })).toBeInTheDocument();
  });

  it('shows sensor mode badge after fetch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ thermal: 'synthetic', radar: 'synthetic', label: 'SYNTHETIC' }),
    }));
    render(
      <StatusHeader
        frame={null}
        connectionState="connected"
        lastUpdate={null}
        onReconnect={() => {}}
      />,
    );
    // Wait for the fetch to resolve and the badge to appear
    expect(await screen.findByText(/SENSOR:.*SYNTHETIC/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// LiveFrame payload parse test
// ---------------------------------------------------------------------------

describe('LiveFrame payload parsing', () => {
  it('parses a full payload JSON into TypeScript structure', () => {
    const payload = makeLiveFrame();
    const json = JSON.stringify(payload);
    const parsed = JSON.parse(json) as LiveFrame;

    expect(parsed.frame_number).toBe(42);
    expect(parsed.highest_risk).toBe('caution');
    expect(parsed.thermal_detections).toHaveLength(1);
    expect(parsed.radar_clusters).toHaveLength(1);
    expect(parsed.fused_objects).toHaveLength(1);
    expect(parsed.tracks).toHaveLength(1);
    expect(parsed.risks).toHaveLength(1);
    expect(parsed.alerts).toHaveLength(1);
    expect(typeof parsed.latency.total).toBe('number');
  });

  it('handles empty arrays gracefully', () => {
    const payload = makeLiveFrame({
      thermal_detections: [],
      radar_clusters: [],
      fused_objects: [],
      tracks: [],
      risks: [],
      alerts: [],
      highest_risk: 'safe',
    });
    const parsed = JSON.parse(JSON.stringify(payload)) as LiveFrame;
    expect(parsed.thermal_detections).toHaveLength(0);
    expect(parsed.highest_risk).toBe('safe');
  });
});

// ---------------------------------------------------------------------------
// WebSocket hook: connection state
// ---------------------------------------------------------------------------

describe('useLivePipeline hook (via App)', () => {
  it('starts in connecting state', () => {
    render(<App />);
    // Before the mock WS fires onopen, state is connecting
    expect(screen.getByText('CONNECTING')).toBeInTheDocument();
  });

  it('transitions to connected after WS opens', async () => {
    render(<App />);
    await new Promise(r => setTimeout(r, 50));
    expect(screen.getByText('CONNECTED')).toBeInTheDocument();
  });

  it('updates frame data when WS message arrives', async () => {
    render(<App />);
    // Wait for WS to open
    await new Promise(r => setTimeout(r, 50));
    expect(wsInstance).not.toBeNull();

    // Push a live frame message
    const frame = makeLiveFrame({ frame_number: 777, highest_risk: 'warning' });
    wsInstance!.receiveMessage(frame);

    // Wait for React re-render
    await new Promise(r => setTimeout(r, 20));

    // frame_number appears in both StatusHeader and MetricsPanel — use getAllByText
    const matches = screen.getAllByText('777');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// DemoControls
// ---------------------------------------------------------------------------

import { DemoControls } from '../components/DemoControls';
import { act } from '@testing-library/react';

// Scenario list returned by GET /api/scenarios
const SCENARIO_NAMES = [
  'SAFE', 'CAUTION', 'WARNING', 'CRITICAL', 'PEDESTRIAN_APPROACH', 'MULTI_TARGET',
];

const mockScenariosResponse = {
  scenarios: SCENARIO_NAMES.map(name => ({
    name,
    description: `${name} description`,
  })),
  current: 'SAFE',
};

/** Helper: render DemoControls with a fetch mock that returns the scenario list */
function renderDemoWithFetch(currentScenario: string | null = 'SAFE') {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => mockScenariosResponse,
  });
  vi.stubGlobal('fetch', fetchMock);
  const result = render(<DemoControls currentScenario={currentScenario} />);
  return { ...result, fetchMock };
}

describe('DemoControls', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders SIMULATION MODE label', async () => {
    renderDemoWithFetch();
    expect(await screen.findByText(/SIMULATION MODE/i)).toBeInTheDocument();
  });

  it('renders all six scenario buttons after fetch', async () => {
    renderDemoWithFetch();
    for (const label of ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL', 'PEDESTRIAN', 'MULTI TARGET']) {
      expect(await screen.findByText(label)).toBeInTheDocument();
    }
  });

  it('shows current active scenario in the active-name span', async () => {
    renderDemoWithFetch('CRITICAL');
    // The demo-active-name span displays the raw scenario string
    const activeSpans = await screen.findAllByText('CRITICAL');
    expect(activeSpans.length).toBeGreaterThanOrEqual(1);
  });

  it('calls POST /api/scenario when a button is clicked', async () => {
    const calls: Array<{ url: string; method: string; body: string }> = [];
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      calls.push({ url, method: opts?.method ?? 'GET', body: (opts?.body as string) ?? '' });
      if (opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({ scenario: 'WARNING', status: 'ok' }) });
      }
      return Promise.resolve({ ok: true, json: async () => mockScenariosResponse });
    }));

    render(<DemoControls currentScenario="SAFE" />);

    // Use data-testid to unambiguously target the WARNING button —
    // avoids any accessible-name / title-attribute fallback ambiguity.
    const warnBtn = await screen.findByTestId('scenario-btn-WARNING');

    // Confirm the button is enabled before clicking
    expect(warnBtn).not.toBeDisabled();

    await act(async () => {
      fireEvent.click(warnBtn);
      // Allow the async POST fetch to resolve
      await new Promise(r => setTimeout(r, 150));
    });

    const postCalls = calls.filter(c => c.method === 'POST');
    expect(postCalls.length).toBeGreaterThanOrEqual(1);
    expect(postCalls[0].url).toContain('/api/scenario');
    const body = JSON.parse(postCalls[0].body);
    expect(body.scenario).toBe('WARNING');
  });

  it('handles empty scenarios gracefully (no crash)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ scenarios: [], current: 'SAFE' }),
    }));
    const { container } = render(<DemoControls currentScenario={null} />);
    // Just wait for fetch to settle
    await new Promise(r => setTimeout(r, 30));
    expect(container).toBeTruthy();
  });

  it('shows error message when fetch fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    render(<DemoControls currentScenario={null} />);
    expect(await screen.findByText(/Could not load scenarios/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ThermalView
// ---------------------------------------------------------------------------

import { ThermalView } from '../components/ThermalView';

// ── Mock navigator.mediaDevices ──────────────────────────────────────────
type FakeTrack = { stop: ReturnType<typeof vi.fn>; kind: string };

function makeFakeStream(tracks: FakeTrack[] = []): MediaStream {
  return {
    getTracks: () => tracks,
    getVideoTracks: () => tracks.filter(t => t.kind === 'video'),
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

function stubMediaDevices(resolveWith?: MediaStream, rejectWith?: Error) {
  const getUserMedia = resolveWith
    ? vi.fn().mockResolvedValue(resolveWith)
    : vi.fn().mockRejectedValue(rejectWith ?? new Error('camera error'));

  vi.stubGlobal('navigator', {
    ...navigator,
    mediaDevices: { getUserMedia },
  });
  return getUserMedia;
}

// jsdom doesn't implement HTMLVideoElement.play — stub it
beforeEach(() => {
  HTMLVideoElement.prototype.play = vi.fn().mockResolvedValue(undefined);
});

describe('ThermalView', () => {
  // Stub rAF/cAF so the render loop doesn't hang tests in jsdom
  beforeEach(() => {
    vi.stubGlobal('requestAnimationFrame', vi.fn(() => 0));
    vi.stubGlobal('cancelAnimationFrame',  vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    // Re-stub WebSocket and fetch for the outer afterEach to clean up
    // (outer afterEach calls vi.unstubAllGlobals which is fine here)
  });
  it('renders without crashing', () => {
    stubMediaDevices(undefined, Object.assign(new Error('NotAllowedError'), { name: 'NotAllowedError' }));
    render(<ThermalView />);
    // Panel title must be present
    expect(screen.getByText(/Thermal Situational View/i)).toBeInTheDocument();
  });

  it('shows SIMULATED badge', () => {
    stubMediaDevices(undefined, Object.assign(new Error('NotAllowedError'), { name: 'NotAllowedError' }));
    render(<ThermalView />);
    expect(screen.getByText('SIMULATED')).toBeInTheDocument();
  });

  it('shows SIMULATED THERMAL label in footer', async () => {
    stubMediaDevices(undefined, Object.assign(new Error('NotAllowedError'), { name: 'NotAllowedError' }));
    render(<ThermalView />);
    expect(await screen.findByText(/SIMULATED THERMAL/i)).toBeInTheDocument();
  });

  it('shows WEBCAM SOURCE label in footer', async () => {
    stubMediaDevices(undefined, Object.assign(new Error('NotAllowedError'), { name: 'NotAllowedError' }));
    render(<ThermalView />);
    expect(await screen.findByText(/WEBCAM SOURCE/i)).toBeInTheDocument();
  });

  it('shows CAMERA ACTIVE when permission is granted', async () => {
    const fakeTrack: FakeTrack = { stop: vi.fn(), kind: 'video' };
    const stream = makeFakeStream([fakeTrack]);
    stubMediaDevices(stream);

    render(<ThermalView />);

    // Wait for getUserMedia to resolve and state to update
    expect(await screen.findByText(/CAMERA ACTIVE/i)).toBeInTheDocument();
  });

  it('shows PERMISSION DENIED when camera is blocked', async () => {
    const err = Object.assign(new Error('Permission denied'), { name: 'NotAllowedError' });
    stubMediaDevices(undefined, err);

    render(<ThermalView />);
    // Text appears in both the footer status and the fallback body — use getAllByText
    const matches = await screen.findAllByText(/PERMISSION DENIED/i);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('shows fallback message on permission denied', async () => {
    const err = Object.assign(new Error('Permission denied'), { name: 'NotAllowedError' });
    stubMediaDevices(undefined, err);

    render(<ThermalView />);
    expect(await screen.findByText(/THERMAL CAMERA UNAVAILABLE/i)).toBeInTheDocument();
  });

  it('shows synthetic fallback note on permission denied', async () => {
    const err = Object.assign(new Error('Permission denied'), { name: 'NotAllowedError' });
    stubMediaDevices(undefined, err);

    render(<ThermalView />);
    expect(await screen.findByText(/Using synthetic thermal pipeline data/i)).toBeInTheDocument();
  });

  it('shows STOP button when camera is active', async () => {
    const fakeTrack: FakeTrack = { stop: vi.fn(), kind: 'video' };
    const stream = makeFakeStream([fakeTrack]);
    stubMediaDevices(stream);

    render(<ThermalView />);
    expect(await screen.findByRole('button', { name: /STOP/i })).toBeInTheDocument();
  });

  it('stops media tracks when STOP is clicked', async () => {
    const fakeTrack: FakeTrack = { stop: vi.fn(), kind: 'video' };
    const stream = makeFakeStream([fakeTrack]);
    stubMediaDevices(stream);

    render(<ThermalView />);
    const stopBtn = await screen.findByRole('button', { name: /STOP/i });

    await act(async () => {
      fireEvent.click(stopBtn);
      await new Promise(r => setTimeout(r, 30));
    });

    expect(fakeTrack.stop).toHaveBeenCalled();
  });

  it('shows CAMERA STOPPED after stopping', async () => {
    const fakeTrack: FakeTrack = { stop: vi.fn(), kind: 'video' };
    const stream = makeFakeStream([fakeTrack]);
    stubMediaDevices(stream);

    render(<ThermalView />);
    const stopBtn = await screen.findByRole('button', { name: /STOP/i });

    await act(async () => {
      fireEvent.click(stopBtn);
      await new Promise(r => setTimeout(r, 30));
    });

    // Text appears in both footer and fallback area — use getAllByText
    const matches = screen.getAllByText(/CAMERA STOPPED/i);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('stops media tracks on component unmount', async () => {
    const fakeTrack: FakeTrack = { stop: vi.fn(), kind: 'video' };
    const stream = makeFakeStream([fakeTrack]);
    stubMediaDevices(stream);

    const { unmount } = render(<ThermalView />);
    await screen.findByText(/CAMERA ACTIVE/i);  // ensure camera is active first

    unmount();
    expect(fakeTrack.stop).toHaveBeenCalled();
  });

  it('dashboard renders when ThermalView camera unavailable', async () => {
    // Simulate camera error inside full App context
    const err = Object.assign(new Error('no cam'), { name: 'NotFoundError' });
    stubMediaDevices(undefined, err);

    render(<App />);
    expect(screen.getByText('MINEXIS')).toBeInTheDocument();
    // Should not crash; the new perception panels should appear
    expect(await screen.findByText(/THERMAL PERCEPTION/i)).toBeInTheDocument();
    expect(await screen.findByText(/RADAR PERCEPTION/i)).toBeInTheDocument();
  });

  it('does NOT display temperature values', () => {
    const err = Object.assign(new Error('NotAllowedError'), { name: 'NotAllowedError' });
    stubMediaDevices(undefined, err);

    const { container } = render(<ThermalView />);
    // Should contain no degree symbols or "°C" text
    expect(container.textContent).not.toMatch(/°C/);
    expect(container.textContent).not.toMatch(/temperature/i);
  });

  it('does NOT display MLX90640 label', () => {
    const err = Object.assign(new Error('NotAllowedError'), { name: 'NotAllowedError' });
    stubMediaDevices(undefined, err);

    const { container } = render(<ThermalView />);
    expect(container.textContent).not.toMatch(/MLX90640/);
  });

  it('does NOT display "REAL THERMAL" text', () => {
    const err = Object.assign(new Error('NotAllowedError'), { name: 'NotAllowedError' });
    stubMediaDevices(undefined, err);

    const { container } = render(<ThermalView />);
    expect(container.textContent).not.toMatch(/REAL THERMAL/i);
  });
});
