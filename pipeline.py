"""
MINEXIS reusable pipeline wrapper.

Complete processing flow:

    Thermal Sensor
        +
    Radar Sensor
        ↓
    Synchronization
        ↓
    Thermal YOLO Detection
        +
    Radar Processing
        ↓
    Adaptive Fusion
        ↓
    Object Tracking
        ↓
    TTC / Risk Assessment
        ↓
    Alert Generation
        ↓
    Logging
"""

from __future__ import annotations

import time

from dataclasses import dataclass

from typing import Optional


# ---------------------------------------------------------------------------
# Sensors
# ---------------------------------------------------------------------------

from sensors.thermal_source import (

    SyntheticThermalSource,

    ThermalSource,

)

from sensors.radar_source import (

    SyntheticRadarSource,

    RadarSource,

)


# ---------------------------------------------------------------------------
# Synchronization
# ---------------------------------------------------------------------------

from sync.synchronizer import (

    Synchronizer,

)


# ---------------------------------------------------------------------------
# Perception
# ---------------------------------------------------------------------------

from perception.thermal_branch import (

    ThermalBranch,

    YoloThermalDetector,

    BlobThermalDetector,

)

from perception.radar_branch import (

    RadarBranch,

)


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------

from fusion.adaptive_fusion import (

    AdaptiveFusion,

)


# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------

from tracking.tracker import (

    Tracker,

)


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

from risk.ttc_risk import (

    RiskEngine,

)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

from alerts.alert_manager import (

    AlertManager,

)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

from logging_.logger import (

    PipelineLogger,

)


# ---------------------------------------------------------------------------
# Common types
# ---------------------------------------------------------------------------

from common.types import (

    ThermalDetection,

    RadarCluster,

    FusedObject,

    Track,

    RiskAssessment,

    AlertEvent,

    RiskState,

)


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

THERMAL_MODEL_PATH = (

    "runs/detect/runs/thermal_training/weights/best.pt"

)


THERMAL_CONFIDENCE_THRESHOLD = 0.20


# ---------------------------------------------------------------------------
# FrameResult
# ---------------------------------------------------------------------------

@dataclass

class FrameResult:
    """
    Output produced by one complete pipeline cycle.
    """


    # -----------------------------------------------------------------------
    # Identity
    # -----------------------------------------------------------------------

    timestamp: float

    frame_number: int


    # -----------------------------------------------------------------------
    # Synchronization
    # -----------------------------------------------------------------------

    sync_skew_s: float


    # -----------------------------------------------------------------------
    # Sensor quality
    # -----------------------------------------------------------------------

    thermal_quality: float

    radar_quality: float


    # -----------------------------------------------------------------------
    # Perception
    # -----------------------------------------------------------------------

    thermal_detections: list[ThermalDetection]

    radar_clusters: list[RadarCluster]


    # -----------------------------------------------------------------------
    # Fusion
    # -----------------------------------------------------------------------

    fused_objects: list[FusedObject]


    # -----------------------------------------------------------------------
    # Tracking
    # -----------------------------------------------------------------------

    tracks: list[Track]


    # -----------------------------------------------------------------------
    # Risk
    # -----------------------------------------------------------------------

    risks: list[RiskAssessment]


    # -----------------------------------------------------------------------
    # Alerts
    # -----------------------------------------------------------------------

    alerts: list[AlertEvent]


    # -----------------------------------------------------------------------
    # Overall state
    # -----------------------------------------------------------------------

    highest_risk: RiskState


    # -----------------------------------------------------------------------
    # Performance
    # -----------------------------------------------------------------------

    latency: dict[str, float]


    # -----------------------------------------------------------------------
    # Simulation
    # -----------------------------------------------------------------------

    scenario: str = "DEFAULT"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    """
    Stateful MINEXIS processing pipeline.

    Complete flow:

        Sensors
            ↓
        Synchronization
            ↓
        Thermal YOLO
            +
        Radar
            ↓
        Adaptive Fusion
            ↓
        Tracking
            ↓
        TTC Risk Engine
            ↓
        Alert Manager
    """


    def __init__(

        self,

        thermal_source: Optional[ThermalSource] = None,

        radar_source: Optional[RadarSource] = None,

        fog_severity: float = 0.0,

        log_path: Optional[str] = "logs/pipeline_log.jsonl",

        controller: Optional[object] = None,

    ):


        # -------------------------------------------------------------------
        # Simulation controller
        # -------------------------------------------------------------------

        self._controller = controller


        # -------------------------------------------------------------------
        # Thermal source
        # -------------------------------------------------------------------

        self._thermal_source: ThermalSource = (

            thermal_source

            if thermal_source is not None

            else SyntheticThermalSource(

                fog_severity=fog_severity,

                controller=controller,

            )

        )


        # -------------------------------------------------------------------
        # Radar source
        # -------------------------------------------------------------------

        self._radar_source: RadarSource = (

            radar_source

            if radar_source is not None

            else SyntheticRadarSource(

                controller=controller,

            )

        )


        # -------------------------------------------------------------------
        # Synchronizer
        # -------------------------------------------------------------------

        self._synchronizer = (

            Synchronizer()

        )


        # -------------------------------------------------------------------
        # THERMAL DETECTOR
        # -------------------------------------------------------------------

        print()

        print(

            "Initializing MINEXIS perception pipeline..."

        )


        # Use BlobThermalDetector (simple brightness-based) for deployment
        # since trained YOLO model is not included in repository.
        # For production with real hardware, train a model and use YoloThermalDetector.

        import os

        use_yolo = os.path.exists(THERMAL_MODEL_PATH)


        if use_yolo:

            print(

                f"Thermal model: {THERMAL_MODEL_PATH} (YOLO)"

            )

            self._thermal_detector = (

                YoloThermalDetector(

                    weights_path=THERMAL_MODEL_PATH,

                    conf_threshold=THERMAL_CONFIDENCE_THRESHOLD,

                )

            )

        else:

            print(

                "Thermal model: BlobThermalDetector (brightness-based fallback)"

            )

            self._thermal_detector = (

                BlobThermalDetector(

                    confidence_threshold=THERMAL_CONFIDENCE_THRESHOLD,

                )

            )


        self._thermal_branch = (

            ThermalBranch(

                detector=self._thermal_detector,

                confidence_threshold=THERMAL_CONFIDENCE_THRESHOLD,

            )

        )


        # -------------------------------------------------------------------
        # Radar branch
        # -------------------------------------------------------------------

        self._radar_branch = (

            RadarBranch()

        )


        # -------------------------------------------------------------------
        # Fusion
        # -------------------------------------------------------------------

        self._fusion = (

            AdaptiveFusion()

        )


        # -------------------------------------------------------------------
        # Tracker
        # -------------------------------------------------------------------

        self._tracker = (

            Tracker()

        )


        # -------------------------------------------------------------------
        # Risk engine
        # -------------------------------------------------------------------

        self._risk_engine = (

            RiskEngine()

        )


        # -------------------------------------------------------------------
        # Alert manager
        # -------------------------------------------------------------------

        self._alert_manager = (

            AlertManager()

        )


        # -------------------------------------------------------------------
        # Logging
        # -------------------------------------------------------------------

        self._logger: Optional[PipelineLogger] = (

            PipelineLogger(

                log_path=log_path

            )

            if log_path is not None

            else None

        )


        # -------------------------------------------------------------------
        # Bookkeeping
        # -------------------------------------------------------------------

        self._frame_count = 0


        self._start_time = (

            time.monotonic()

        )


        print(

            "MINEXIS pipeline initialized successfully."

        )

        print()


    # -----------------------------------------------------------------------
    # Main processing step
    # -----------------------------------------------------------------------

    def step(

        self,

    ) -> Optional[FrameResult]:
        """
        Execute one complete sensor-to-alert cycle.
        """


        # -------------------------------------------------------------------
        # Current time
        # -------------------------------------------------------------------

        now = (

            time.monotonic()

            -

            self._start_time

        )


        # -------------------------------------------------------------------
        # STEP 1
        #
        # Read thermal sensor
        # -------------------------------------------------------------------

        thermal_frame = (

            self._thermal_source.read()

        )


        # -------------------------------------------------------------------
        # STEP 2
        #
        # Read radar sensor
        # -------------------------------------------------------------------

        radar_scan = (

            self._radar_source.read()

        )


        # -------------------------------------------------------------------
        # STEP 3
        #
        # Push sensor readings
        # -------------------------------------------------------------------

        if thermal_frame is not None:

            self._synchronizer.push_thermal(

                thermal_frame

            )


        if radar_scan is not None:

            self._synchronizer.push_radar(

                radar_scan

            )


        # -------------------------------------------------------------------
        # STEP 4
        #
        # Synchronize sensors
        # -------------------------------------------------------------------

        pair = (

            self._synchronizer.try_pair(

                now

            )

        )


        # -------------------------------------------------------------------
        # STEP 5
        #
        # No synchronized pair available
        # -------------------------------------------------------------------

        if pair is None:

            return None


        # -------------------------------------------------------------------
        # Pipeline timing begins
        # -------------------------------------------------------------------

        stage_t0 = (

            time.perf_counter()

        )


        # ===================================================================
        #
        # STEP 6
        #
        # THERMAL PERCEPTION
        #
        # ===================================================================

        thermal_output = (

            self._thermal_branch.process(

                pair.thermal

            )

        )


        # ===================================================================
        #
        # STEP 7
        #
        # RADAR PERCEPTION
        #
        # ===================================================================

        radar_output = (

            self._radar_branch.process(

                pair.radar

            )

        )


        t_perception = (

            time.perf_counter()

        )


        # ===================================================================
        #
        # STEP 8
        #
        # ADAPTIVE FUSION
        #
        # ===================================================================

        fused_objects = (

            self._fusion.fuse(

                thermal_output,

                radar_output,

                pair.timestamp,

            )

        )


        t_fusion = (

            time.perf_counter()

        )


        # ===================================================================
        #
        # STEP 9
        #
        # OBJECT TRACKING
        #
        # ===================================================================

        tracks = (

            self._tracker.update(

                fused_objects,

                pair.timestamp,

            )

        )


        t_tracking = (

            time.perf_counter()

        )


        # ===================================================================
        #
        # STEP 10
        #
        # TRACK LOOKUP
        #
        # ===================================================================

        tracks_by_id = {

            track.track_id: track

            for track

            in tracks

        }


        # ===================================================================
        #
        # STEP 11
        #
        # RISK ASSESSMENT
        #
        # ===================================================================

        risks = (

            self._risk_engine.assess(

                tracks

            )

        )


        t_risk = (

            time.perf_counter()

        )


        # ===================================================================
        #
        # STEP 12
        #
        # ALERT GENERATION
        #
        # ===================================================================

        alerts = (

            self._alert_manager.generate(

                risks,

                tracks_by_id,

                pair.timestamp,

            )

        )


        t_alerts = (

            time.perf_counter()

        )


        # ===================================================================
        #
        # STEP 13
        #
        # HIGHEST RISK STATE
        #
        # ===================================================================

        highest_risk = (

            self._alert_manager.highest_state(

                risks

            )

        )


        # ===================================================================
        #
        # STEP 14
        #
        # LATENCY CALCULATION
        #
        # ===================================================================

        latency: dict[str, float] = {


            "perception":

                (

                    t_perception

                    -

                    stage_t0

                )

                *

                1000,


            "fusion":

                (

                    t_fusion

                    -

                    t_perception

                )

                *

                1000,


            "tracking":

                (

                    t_tracking

                    -

                    t_fusion

                )

                *

                1000,


            "risk":

                (

                    t_risk

                    -

                    t_tracking

                )

                *

                1000,


            "alerts":

                (

                    t_alerts

                    -

                    t_risk

                )

                *

                1000,


            "total":

                (

                    t_alerts

                    -

                    stage_t0

                )

                *

                1000,

        }


        # ===================================================================
        #
        # STEP 15
        #
        # LOGGING
        #
        # ===================================================================

        self._frame_count += 1


        if self._logger is not None:


            self._logger.log_frame(

                timestamp=pair.timestamp,

                sync_skew_s=pair.time_skew_s,

                thermal_quality=thermal_output.frame_quality,

                radar_quality=radar_output.scan_quality,

                fused_objects=fused_objects,

                tracks=tracks,

                risks=risks,

                alerts=alerts,


                stage_latencies_ms={


                    "sensor_read": 0.0,


                    "perception":

                        latency["perception"],


                    "fusion":

                        latency["fusion"],


                    "tracking":

                        latency["tracking"],


                    "risk":

                        latency["risk"],


                    "alerts":

                        latency["alerts"],


                    "total":

                        latency["total"],

                },

            )


        # ===================================================================
        #
        # STEP 16
        #
        # RETURN RESULT
        #
        # ===================================================================

        scenario = (

            self._controller.get_current_scenario()

            if self._controller is not None

            else "DEFAULT"

        )


        return FrameResult(


            timestamp=pair.timestamp,


            frame_number=self._frame_count,


            sync_skew_s=pair.time_skew_s,


            thermal_quality=thermal_output.frame_quality,


            radar_quality=radar_output.scan_quality,


            thermal_detections=thermal_output.detections,


            radar_clusters=radar_output.clusters,


            fused_objects=fused_objects,


            tracks=tracks,


            risks=risks,


            alerts=alerts,


            highest_risk=highest_risk,


            latency=latency,


            scenario=scenario,

        )


    # -----------------------------------------------------------------------
    # Close
    # -----------------------------------------------------------------------

    def close(

        self,

    ) -> None:
        """
        Release pipeline resources.
        """


        if self._logger is not None:

            self._logger.close()


        self._thermal_source.close()


        self._radar_source.close()


    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property

    def frame_count(

        self,

    ) -> int:

        return self._frame_count


    @property

    def fog_severity(

        self,

    ) -> float:

        return getattr(

            self._thermal_source,

            "fog_severity",

            0.0,

        )


    @property

    def scenario(

        self,

    ) -> str:


        if self._controller is not None:

            return (

                self._controller.get_current_scenario()

            )


        return "DEFAULT"