# MINEXIS — Intelligent Multisensor Collision Warning for Open-Cast Mines

SIH 2026 · PS 26007 · Team ASTRA CODE

Driver-assistance collision-warning system for mine dumpers operating in
fog/dust/low-visibility, fusing a thermal camera and 4D/mmWave radar.
This repo implements the pipeline described in `SIH26007_Complete_Proposed_Solution_pdf.docx`.

## Frontend dashboard

```bash
cd ui/dashboard
npm install
npm run dev
```

Backend must be running separately first:

```bash
# In a separate terminal, from the minexis/ directory:
python -m backend.app
```

Then open the dashboard at:

```
http://localhost:5173
```

The dashboard connects automatically to `ws://localhost:8000/ws/live` and streams live pipeline frames. Override the backend URL at build time with:

```bash
VITE_API_BASE_URL=http://192.168.1.10:8000 npm run dev
```

### Run frontend tests

```bash
cd ui/dashboard
npm test
```

## Quick start

```bash
pip install -r requirements.txt
python main.py                    # clear-visibility synthetic run, Ctrl+C to stop
python main.py --fog 0.7          # heavy-fog synthetic run
python main.py --duration 30      # run for 30s then exit
python -m pytest tests/ -v        # sanity tests (or: python tests/test_pipeline.py)
```

No hardware needed to run this — `sensors/` generates synthetic thermal
frames and radar scans so every downstream stage can be built, tested and
demoed today.

## Pipeline (matches doc section 1 "Core flow")

```
sensors/  →  sync/  →  perception/  →  evidence/  →  fusion/  →  tracking/  →  risk/  →  alerts/
(thermal+     (time-    (thermal        (reliability   (adaptive    (Kalman +    (TTC +   (driver
 radar)        align)    branch,         scoring per    weighted     Hungarian    4-state   warning
               ✚         radar           modality)      decision-    tracking)    risk      messages)
               reject     branch)                        level                    logic +
               stale                                     fusion)                  hysteresis)
```

`main.py` wires all of it together and is the thing you actually run.
`config/thresholds.yaml` documents every tunable value in one place — it's
not wired to auto-load yet (thresholds are still hardcoded as dataclass
defaults in each module); if you want the yaml to be the actual source of
truth, load it in `main.py` and pass values into each module's config
objects instead of relying on defaults.

## What's real vs. placeholder right now

| Module | Status |
|---|---|
| Sync, radar CFAR/clustering, adaptive fusion, Kalman tracking, TTC/risk/hysteresis, alerts, logging | **Real logic**, working end-to-end, tested |
| Thermal detector | `BlobThermalDetector` — dependency-free brightness-threshold detector so the pipeline runs today. **Not a real object detector.** Swap for `YoloThermalDetector` (`perception/thermal_branch.py`) once you have a fine-tuned model |
| Camera↔radar calibration | `CalibrationConfig` in `fusion/adaptive_fusion.py` uses a placeholder linear pixel→azimuth mapping. **Must be replaced** with real calibrated extrinsics once sensors are physically mounted |
| Monocular range estimate (thermal-only objects) | Rough box-size heuristic (`_rough_range_from_box`) — expected to be poor, exists only so thermal-only detections aren't silently dropped |
| All risk/TTC/fusion thresholds | Placeholder values. The doc explicitly says these **must be validated against real vehicle braking distance, speed, mine safety rules** before they mean anything |

Don't present any of the "real logic" row's numeric outputs as validated
performance — they're architecturally correct and tested for logical
behavior (does TTC decrease as things get closer, does hysteresis prevent
flicker, etc.), not tuned against real mine data yet.

## Training a real thermal detector

`BlobThermalDetector` is a placeholder. To get a real one:

1. Get a thermal dataset in YOLO format. Fastest path: search
   [Roboflow Universe](https://universe.roboflow.com) for "thermal person
   vehicle" and export in YOLOv8 format — it downloads/unzips into a
   folder with `data.yaml`, `train/`, `valid/`, `test/`. (FLIR ADAS and
   KAIST are better long-term datasets but need a format-conversion
   script first — worth doing on Day 6-7 if time allows, not before.)
2. `pip install ultralytics`
3. `python perception/train_thermal.py --data /path/to/dataset/data.yaml`
   — fine-tunes YOLOv8n starting from COCO pretrained weights, 30 epochs
   by default. Produces `runs/detect/train/weights/best.pt`.
4. After training, run `python -c "from ultralytics import YOLO; print(YOLO('runs/detect/train/weights/best.pt').names)"`
   to see your dataset's actual class names, and extend `CLASS_MAP` in
   `perception/thermal_branch.py::YoloThermalDetector` if they don't
   already match (Roboflow/FLIR/KAIST each name classes slightly
   differently — unmapped classes fall back to `UNKNOWN` rather than
   being dropped).
5. In `main.py`, replace:
   ```python
   thermal_branch = ThermalBranch(detector=BlobThermalDetector())
   ```
   with:
   ```python
   from perception.thermal_branch import YoloThermalDetector
   thermal_branch = ThermalBranch(detector=YoloThermalDetector(weights_path="runs/detect/train/weights/best.pt"))
   ```

## Swapping in real hardware

Every sensor interface is deliberately thin so this is a small change:

1. In `sensors/thermal_source.py`, add a `LiveThermalSource` class implementing
   `read() -> Optional[ThermalFrame]` using your camera's SDK.
2. In `sensors/radar_source.py`, add a `LiveRadarSource` class implementing
   `read() -> Optional[RadarScan]` using your radar's SDK (vendor SDKs
   typically hand you detections/point clouds directly, matching
   `RadarReturn` — see doc section 5 "Input acquisition").
3. In `main.py`, swap `SyntheticThermalSource()` / `SyntheticRadarSource()`
   for your new classes. Nothing else changes.
4. Calibrate `CalibrationConfig` in `fusion/adaptive_fusion.py` against
   your actual mounted camera/radar geometry.

## Team split (matches doc section 16)

- **AI/ML** → `perception/thermal_branch.py` (fine-tune YOLO on FLIR ADAS /
  KAIST + your own captured mine-like fog/dust data — see doc section 13)
- **Radar** → `perception/radar_branch.py` (real CFAR, calibration,
  diagnostics once radar SDK data is available)
- **Fusion/Evidence** → `evidence/evidence_module.py`, `fusion/adaptive_fusion.py`
- **Tracking/Risk** → `tracking/tracker.py`, `risk/ttc_risk.py`
- **Integration** → `sync/synchronizer.py`, `main.py`, hardware swap-in
- **UI/Alerts** → `alerts/alert_manager.py` + `ui/dashboard/` (not yet built —
  see below)
- **Testing** → `tests/`, plus running the doc's section 11 experimental
  plan (thermal-only / radar-only / fixed-fusion / adaptive-fusion
  comparison) once real data exists

## Logs → experiments

Every run appends structured JSON lines to `logs/pipeline_log.jsonl`
(one record per synced frame: quality scores, fusion weights/agreement,
tracks, TTC, risk state, alerts, per-stage latency in ms). This is your
raw material for the doc's section 11-12 ablation study and results
table — write a small script to parse this log for each baseline
configuration (e.g. run with radar branch disabled = "thermal-only"
baseline) and compute the metrics table.

## Backend API server

The FastAPI backend streams real-time pipeline output to any WebSocket
client (e.g. the React dashboard).

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
python -m backend.app
```

or with auto-reload during development:

```bash
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe — `{"status":"ok","service":"MINEXIS backend"}` |
| GET | `/api/status` | Runtime summary — running flag, frame count, highest risk, connected clients |
| WS | `/ws/live` | Real-time FrameResult JSON stream, one message per processed frame |

### WebSocket frame shape

Each message is a JSON object with the following top-level keys:

```
frame_number, timestamp, sync_skew_s,
thermal_quality, radar_quality,
thermal_detections, radar_clusters,
fused_objects, tracks, risks, alerts,
highest_risk, latency
```

Raw thermal images are **not** transmitted.  All enum values are strings.

---

## Still to build

- **UI/dashboard** (`ui/dashboard/`) — a live view of detections, fused
  tracks, TTC and alert state. Fastest path: a small FastAPI backend
  streaming the same data `main.py` already computes over a WebSocket, to
  a simple HTML/JS frontend. Ask if you want this scaffolded next.
- **Real thermal model** — fine-tune YOLOv8n/v9 on FLIR ADAS first (works
  without mine data), then on your own captured footage once the camera
  and vehicle access exist.
- **Real radar calibration** — once radar hardware arrives, replace the
  synthetic azimuth mapping with actual extrinsic calibration.
- **Ablation harness** — a script that runs `main.py`-equivalent logic
  with modules toggled off (per doc section 12's ablation table A1-A7)
  and produces the results table automatically from the logs.
