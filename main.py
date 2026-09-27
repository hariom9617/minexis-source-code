"""
MINEXIS pipeline entry point.

Complete system flow:

    Thermal Sensor
        +
    Radar Sensor
        ↓
    Synchronization
        ↓
    YOLOv8 Thermal Detection
        +
    Radar Processing
        ↓
    Adaptive Sensor Fusion
        ↓
    Object Tracking
        ↓
    TTC Risk Analysis
        ↓
    Alert Generation
        ↓
    Logging


Usage:

    python main.py

    python main.py --fog 0.7

    python main.py --duration 30

    python main.py --quiet
"""

from __future__ import annotations


import argparse

import time


from pipeline import (

    Pipeline,

)


from common.types import (

    RiskState,

)


# ---------------------------------------------------------------------------
# Run pipeline
# ---------------------------------------------------------------------------

def run(

    duration_s: float | None,

    fog_severity: float,

    log_path: str,

    quiet: bool,

) -> None:


    # -----------------------------------------------------------------------
    # Initialize pipeline
    # -----------------------------------------------------------------------

    pipe = Pipeline(

        fog_severity=fog_severity,

        log_path=log_path,

    )


    # -----------------------------------------------------------------------
    # Start timer
    # -----------------------------------------------------------------------

    start = (

        time.monotonic()

    )


    print(

        "============================================================"

    )

    print(

        "MINEXIS COLLISION WARNING SYSTEM"

    )

    print(

        "============================================================"

    )

    print(

        "Pipeline status: RUNNING"

    )

    print(

        "Thermal detector: YOLOv8 Fine-Tuned Model"

    )

    print(

        f"Fog severity: {fog_severity}"

    )

    print(

        f"Log file: {log_path}"

    )

    print()

    print(

        "Press Ctrl+C to stop."

    )

    print()


    try:


        while True:


            # ---------------------------------------------------------------
            # Current runtime
            # ---------------------------------------------------------------

            now = (

                time.monotonic()

                -

                start

            )


            # ---------------------------------------------------------------
            # Stop after requested duration
            # ---------------------------------------------------------------

            if (

                duration_s is not None

                and

                now >= duration_s

            ):

                break


            # ---------------------------------------------------------------
            # Execute pipeline
            # ---------------------------------------------------------------

            result = (

                pipe.step()

            )


            # ---------------------------------------------------------------
            # No synchronized sensor pair
            # ---------------------------------------------------------------

            if result is None:


                time.sleep(

                    0.02

                )


                continue


            # ---------------------------------------------------------------
            # Console output
            # ---------------------------------------------------------------

            if (

                not quiet

                and

                result.frame_number % 10 == 0

            ):


                # -----------------------------------------------------------
                # Risk marker
                # -----------------------------------------------------------

                marker = (

                    "  <<< WARNING"

                    if (

                        result.highest_risk

                        !=

                        RiskState.SAFE

                    )

                    else ""

                )


                # -----------------------------------------------------------
                # Frame summary
                # -----------------------------------------------------------

                print(

                    f"[{now:6.1f}s] "

                    f"frame={result.frame_number:04d}  "

                    f"thermal={len(result.thermal_detections):2d}  "

                    f"radar={len(result.radar_clusters):2d}  "

                    f"tracks={len(result.tracks):2d}  "

                    f"tQ={result.thermal_quality:.2f}  "

                    f"rQ={result.radar_quality:.2f}  "

                    f"risk={result.highest_risk.value:8s}  "

                    f"latency={result.latency['total']:.1f}ms"

                    f"{marker}"

                )


                # -----------------------------------------------------------
                # Print thermal detections
                # -----------------------------------------------------------

                if result.thermal_detections:


                    print(

                        "          THERMAL DETECTIONS:"

                    )


                    for detection in (

                        result.thermal_detections

                    ):


                        print(

                            f"          "

                            f"class={detection.cls.value}  "

                            f"confidence={detection.confidence:.2f}  "

                            f"box={detection.box_xyxy}"

                        )


                # -----------------------------------------------------------
                # Print alerts
                # -----------------------------------------------------------

                for alert in (

                    result.alerts

                ):


                    if (

                        alert.risk_state

                        in (

                            RiskState.WARNING,

                            RiskState.CRITICAL,

                        )

                    ):


                        print(

                            f"          ALERT "

                            f"track#{alert.track_id}  "

                            f"{alert.message}  "

                            f"[{alert.direction_hint}]"

                        )


    # -----------------------------------------------------------------------
    # Ctrl+C
    # -----------------------------------------------------------------------

    except KeyboardInterrupt:


        print()

        print(

            "MINEXIS stopped by user."

        )


    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    finally:


        pipe.close()


        print()

        print(

            "============================================================"

        )

        print(

            "MINEXIS PIPELINE STOPPED"

        )

        print(

            "============================================================"

        )


        print(

            f"Processed frames: {pipe.frame_count}"

        )


        print(

            f"Log written to: {log_path}"

        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":


    parser = argparse.ArgumentParser(

        description=(
            "MINEXIS AI-based collision warning system"
        )

    )


    # -----------------------------------------------------------------------
    # Duration
    # -----------------------------------------------------------------------

    parser.add_argument(

        "--duration",

        type=float,

        default=None,

        help=(
            "Run duration in seconds. "
            "Default: run until Ctrl+C."
        ),

    )


    # -----------------------------------------------------------------------
    # Fog
    # -----------------------------------------------------------------------

    parser.add_argument(

        "--fog",

        type=float,

        default=0.0,

        help=(
            "Synthetic fog severity "
            "from 0.0 to 1.0."
        ),

    )


    # -----------------------------------------------------------------------
    # Log
    # -----------------------------------------------------------------------

    parser.add_argument(

        "--log",

        type=str,

        default=(

            "logs/pipeline_log.jsonl"

        ),

        help=(

            "Pipeline output log path."

        ),

    )


    # -----------------------------------------------------------------------
    # Quiet mode
    # -----------------------------------------------------------------------

    parser.add_argument(

        "--quiet",

        action="store_true",

        help=(

            "Suppress per-frame console output."

        ),

    )


    args = (

        parser.parse_args()

    )


    # -----------------------------------------------------------------------
    # Run system
    # -----------------------------------------------------------------------

    run(

        duration_s=args.duration,

        fog_severity=args.fog,

        log_path=args.log,

        quiet=args.quiet,

    )