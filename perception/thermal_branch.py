"""
Thermal detection pipeline.

Implements:
    normalize -> quality check -> YOLO detection ->
    confidence filtering -> output detections.

Detector backends:

    - YoloThermalDetector:
      Uses the fine-tuned YOLOv8 thermal model.

    - BlobThermalDetector:
      Dependency-free fallback for synthetic testing.

Both implement:

    detect(image) -> list[ThermalDetection]

The pipeline can switch between them without changing
the rest of the perception architecture.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from common.types import (
    ThermalFrame,
    ThermalDetection,
    ThermalPerceptionOutput,
    ObjectClass,
)


# ---------------------------------------------------------------------------
# Image-quality scoring
# ---------------------------------------------------------------------------

def compute_image_quality(image: np.ndarray) -> float:
    """
    Compute a composite 0-1 image quality score.

    The score considers:

        1. Contrast
        2. Sharpness
        3. Saturation

    A lower score indicates that the frame should be considered
    less reliable by later stages of the pipeline.
    """

    img = image.astype(np.float32)

    # Normalize image if it is in the 0-255 range
    if img.max() > 1.5:
        img = img / 255.0

    # Contrast
    contrast = float(img.std())

    # Sharpness proxy using image gradients
    if img.ndim == 3:
        gray = img.mean(axis=2)
    else:
        gray = img

    dx = np.diff(gray, axis=1)
    dy = np.diff(gray, axis=0)

    sharpness = float(dx.var() + dy.var())

    # Saturation penalty
    saturated_fraction = float(
        np.mean(
            (img > 0.98) |
            (img < 0.02)
        )
    )

    saturation_score = 1.0 - saturated_fraction

    # Normalize scores
    contrast_score = float(
        np.clip(
            contrast / 0.15,
            0.0,
            1.0
        )
    )

    sharpness_score = float(
        np.clip(
            sharpness / 0.01,
            0.0,
            1.0
        )
    )

    quality = (
        0.5 * contrast_score +
        0.3 * sharpness_score +
        0.2 * saturation_score
    )

    return float(
        np.clip(
            quality,
            0.0,
            1.0
        )
    )


# ---------------------------------------------------------------------------
# Fallback detector
# ---------------------------------------------------------------------------

class BlobThermalDetector:
    """
    Simple bright-region detector.

    This detector is intended for the synthetic thermal source
    and as a fallback when the YOLO model is unavailable.

    It is NOT a real object detector.
    """

    def __init__(
        self,
        rel_threshold: float = 0.6,
        min_blob_px: int = 9,
    ):
        self.rel_threshold = rel_threshold
        self.min_blob_px = min_blob_px

    def detect(
        self,
        image: np.ndarray,
    ) -> list[ThermalDetection]:

        img = image.astype(np.float32)

        threshold = (
            img.mean()
            +
            self.rel_threshold
            *
            (
                img.max()
                -
                img.mean()
                +
                1e-6
            )
        )

        mask = img >= threshold

        if mask.sum() < self.min_blob_px:
            return []

        # Convert multi-channel mask to grayscale if necessary
        if mask.ndim == 3:
            mask = np.any(mask, axis=2)

        ys, xs = np.where(mask)

        if len(xs) == 0 or len(ys) == 0:
            return []

        x0 = float(xs.min())
        x1 = float(xs.max())

        y0 = float(ys.min())
        y1 = float(ys.max())

        peak_value = float(img.max())

        confidence = float(
            np.clip(
                (
                    peak_value
                    -
                    img.mean()
                )
                /
                (
                    img.max()
                    -
                    img.mean()
                    +
                    1e-6
                ),
                0.0,
                1.0,
            )
        )

        return [
            ThermalDetection(
                box_xyxy=(
                    x0,
                    y0,
                    x1,
                    y1,
                ),
                cls=ObjectClass.PERSON,
                confidence=confidence,
                image_quality=compute_image_quality(img),
            )
        ]


# ---------------------------------------------------------------------------
# YOLO thermal detector
# ---------------------------------------------------------------------------

class YoloThermalDetector:
    """
    YOLOv8 thermal object detector.

    Loads the fine-tuned MINEXIS thermal model.

    The model was trained on the following classes:

        bike
        bus
        car
        deer
        dog
        hydrant
        light
        motor
        other vehicle
        person
        scooter
        sign
        skateboard
        stroller
        train
        truck
    """

    CLASS_MAP = {

        # ---------------------------------------------------------------
        # Humans
        # ---------------------------------------------------------------

        "person": ObjectClass.PERSON,
        "pedestrian": ObjectClass.PERSON,
        "human": ObjectClass.PERSON,


        # ---------------------------------------------------------------
        # Vehicles
        # ---------------------------------------------------------------

        "bike": ObjectClass.VEHICLE,
        "bicycle": ObjectClass.VEHICLE,

        "bus": ObjectClass.VEHICLE,

        "car": ObjectClass.VEHICLE,

        "motor": ObjectClass.VEHICLE,
        "motorcycle": ObjectClass.VEHICLE,

        "other vehicle": ObjectClass.VEHICLE,

        "scooter": ObjectClass.VEHICLE,

        "train": ObjectClass.VEHICLE,

        "truck": ObjectClass.VEHICLE,

        "vehicle": ObjectClass.VEHICLE,

        "dumper": ObjectClass.VEHICLE,

        "haul truck": ObjectClass.VEHICLE,


        # ---------------------------------------------------------------
        # Obstacles
        # ---------------------------------------------------------------

        "deer": ObjectClass.LARGE_OBSTACLE,

        "dog": ObjectClass.LARGE_OBSTACLE,

        "hydrant": ObjectClass.LARGE_OBSTACLE,

        "sign": ObjectClass.LARGE_OBSTACLE,

        "skateboard": ObjectClass.LARGE_OBSTACLE,

        "stroller": ObjectClass.LARGE_OBSTACLE,

        "obstacle": ObjectClass.LARGE_OBSTACLE,

        "rock": ObjectClass.LARGE_OBSTACLE,

        "boulder": ObjectClass.LARGE_OBSTACLE,
    }


    def __init__(
        self,
        weights_path: str,
        conf_threshold: float = 0.20,
    ):
        """
        Parameters
        ----------
        weights_path:
            Path to trained YOLO model.

        conf_threshold:
            Minimum YOLO confidence required for a detection.
        """

        try:

            from ultralytics import YOLO

        except ImportError as e:

            raise ImportError(
                "ultralytics is not installed.\n"
                "Run:\n"
                "    pip install ultralytics"
            ) from e


        self.weights_path = Path(weights_path)

        if not self.weights_path.exists():

            raise FileNotFoundError(
                "\n"
                "YOLO thermal model was not found.\n"
                f"Expected path:\n"
                f"    {self.weights_path}\n"
            )


        print(
            "\n"
            "============================================================"
        )

        print(
            "LOADING MINEXIS THERMAL YOLO MODEL"
        )

        print(
            "============================================================"
        )

        print(
            f"Model path: {self.weights_path}"
        )

        print(
            f"Confidence threshold: {conf_threshold}"
        )


        self.model = YOLO(
            str(
                self.weights_path
            )
        )

        self.conf_threshold = conf_threshold


        print(
            "Thermal YOLO model loaded successfully."
        )

        print(
            f"Model classes: {self.model.names}"
        )

        print(
            "============================================================\n"
        )


    def detect(
        self,
        image: np.ndarray,
    ) -> list[ThermalDetection]:
        """
        Run YOLO inference on a thermal image.
        """

        img = image.astype(np.float32)


        # ---------------------------------------------------------------
        # Normalize image
        # ---------------------------------------------------------------

        if img.max() <= 1.5:

            img_u8 = (
                img * 255
            ).clip(
                0,
                255
            ).astype(
                np.uint8
            )

        else:

            img_u8 = img.clip(
                0,
                255
            ).astype(
                np.uint8
            )


        # ---------------------------------------------------------------
        # YOLO expects a 3-channel image
        # ---------------------------------------------------------------

        if img_u8.ndim == 2:

            img_u8 = np.stack(
                [
                    img_u8,
                    img_u8,
                    img_u8,
                ],
                axis=-1,
            )


        elif (
            img_u8.ndim == 3
            and
            img_u8.shape[2] == 1
        ):

            img_u8 = np.repeat(
                img_u8,
                3,
                axis=2,
            )


        # ---------------------------------------------------------------
        # Run YOLO
        # ---------------------------------------------------------------

        results = self.model.predict(

            source=img_u8,

            conf=self.conf_threshold,

            verbose=False,

        )


        # ---------------------------------------------------------------
        # Compute image quality
        # ---------------------------------------------------------------

        quality = compute_image_quality(
            image
        )


        detections: list[ThermalDetection] = []


        # ---------------------------------------------------------------
        # Process YOLO detections
        # ---------------------------------------------------------------

        for result in results:

            if result.boxes is None:

                continue


            for box in result.boxes:


                class_id = int(
                    box.cls[0].item()
                )


                class_name = self.model.names[
                    class_id
                ]


                # Normalize class name
                class_name = str(
                    class_name
                ).lower().strip()


                mapped_class = self.CLASS_MAP.get(

                    class_name,

                    ObjectClass.UNKNOWN,

                )


                xyxy_values = box.xyxy[
                    0
                ].tolist()


                x0 = float(
                    xyxy_values[0]
                )

                y0 = float(
                    xyxy_values[1]
                )

                x1 = float(
                    xyxy_values[2]
                )

                y1 = float(
                    xyxy_values[3]
                )


                confidence = float(

                    box.conf[0].item()

                )


                detection = ThermalDetection(

                    box_xyxy=(

                        x0,

                        y0,

                        x1,

                        y1,

                    ),

                    cls=mapped_class,

                    confidence=confidence,

                    image_quality=quality,

                )


                detections.append(

                    detection

                )


        return detections


# ---------------------------------------------------------------------------
# Thermal branch
# ---------------------------------------------------------------------------

class ThermalBranch:
    """
    Complete thermal perception branch.

    Flow:

        ThermalFrame
            ↓
        Image quality analysis
            ↓
        Detector
            ↓
        Confidence filtering
            ↓
        ThermalPerceptionOutput
    """


    def __init__(

        self,

        detector=None,

        confidence_threshold: float = 0.20,

    ):

        self.detector = (

            detector

            if detector is not None

            else BlobThermalDetector()

        )


        self.confidence_threshold = (

            confidence_threshold

        )


    def process(

        self,

        frame: ThermalFrame,

    ) -> ThermalPerceptionOutput:


        # ---------------------------------------------------------------
        # Image quality
        # ---------------------------------------------------------------

        frame_quality = (

            compute_image_quality(

                frame.image

            )

        )


        # ---------------------------------------------------------------
        # Run detector
        # ---------------------------------------------------------------

        raw_detections = (

            self.detector.detect(

                frame.image

            )

        )


        # ---------------------------------------------------------------
        # Confidence filtering
        # ---------------------------------------------------------------

        filtered_detections = [

            detection

            for detection

            in raw_detections

            if detection.confidence

            >= self.confidence_threshold

        ]


        # ---------------------------------------------------------------
        # Return perception output
        # ---------------------------------------------------------------

        return ThermalPerceptionOutput(

            timestamp=frame.timestamp,

            detections=filtered_detections,

            frame_quality=frame_quality,

        )