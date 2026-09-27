"""
Fine-tune YOLOv8 on the FLIR thermal dataset.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune YOLOv8 on a thermal dataset"
    )

    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to dataset data.yaml"
    )

    parser.add_argument(
        "--model",
        type=str,
        default="yolov8n.pt",
        help="Base YOLO model"
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=30,
        help="Number of training epochs"
    )

    parser.add_argument(
        "--imgsz",
        type=int,
        default=320,
        help="Training image size"
    )

    parser.add_argument(
        "--batch",
        type=int,
        default=4,
        help="Batch size"
    )

    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="cpu or GPU device number"
    )

    args = parser.parse_args()

    data_path = Path(args.data)

    if not data_path.exists():
        raise FileNotFoundError(
            f"Could not find dataset configuration: {data_path}"
        )

    from ultralytics import YOLO

    print("=" * 60)
    print("MINEXIS THERMAL AI TRAINING")
    print("=" * 60)

    print(f"\nLoading model: {args.model}")

    model = YOLO(args.model)

    print(f"\nDataset: {data_path}")
    print(f"Epochs: {args.epochs}")
    print(f"Image Size: {args.imgsz}")
    print(f"Batch Size: {args.batch}")
    print(f"Device: {args.device}")

    print("\nStarting training...\n")

    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,

        project="runs",
        name="thermal_training",

        exist_ok=True,

        patience=10,

        workers=0,

        pretrained=True,

        plots=True
    )

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)

    best_weights = Path(
        "runs/thermal_training/weights/best.pt"
    )

    if best_weights.exists():
        print(f"\nBest model saved at:\n{best_weights}")

    print("\nRunning final validation...\n")

    try:

        metrics = model.val(
            data=str(data_path),
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device
        )

        print("\nFINAL RESULTS")

        print(
            f"mAP50: {metrics.box.map50:.4f}"
        )

        print(
            f"mAP50-95: {metrics.box.map:.4f}"
        )

    except Exception as e:

        print(
            f"\nValidation skipped: {e}"
        )


if __name__ == "__main__":
    main()