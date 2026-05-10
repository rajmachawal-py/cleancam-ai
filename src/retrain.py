"""
CleanCam AI — Retrain YOLOv8s on GPU
=====================================
RTX 4050 (6GB VRAM) optimized settings.

Usage:
    cd "CleanCam AI"
    python src/retrain.py

Output:
    model/train_v2/weights/best.pt
"""

from ultralytics import YOLO
import os
import torch

# =================== CONFIG ===================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_YAML = os.path.join(BASE_DIR, "Garbage_dataset", "data.yaml")
OUTPUT_DIR = os.path.join(BASE_DIR, "model")

# Training parameters (RTX 4050 6GB optimized)
MODEL = "yolov8s.pt"       # Upgrade from nano → small (better accuracy)
EPOCHS = 50                # Up from 10 → 50 (was still improving at epoch 10)
BATCH = -1                # 16 fits comfortably in 6GB VRAM with yolov8s
IMGSZ = 640                # Standard YOLO input size
DEVICE = "0"               # GPU 0 (your RTX 4050)

# =================== VERIFY GPU ===================
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
else:
    print("⚠️ CUDA not available — falling back to CPU (will be very slow)")
    DEVICE = "cpu"

print(f"\n{'='*60}")
print(f"  CleanCam AI — Model Retraining")
print(f"  Model:   {MODEL}")
print(f"  Epochs:  {EPOCHS}")
print(f"  Batch:   {BATCH}")
print(f"  ImgSize: {IMGSZ}")
print(f"  Device:  {DEVICE}")
print(f"  Dataset: {DATASET_YAML}")
print(f"  Output:  {OUTPUT_DIR}/train_v2/")
print(f"{'='*60}\n")

# =================== TRAIN ===================
if __name__ == '__main__':
    model = YOLO(MODEL)

    results = model.train(
        data=DATASET_YAML,
        epochs=EPOCHS,
        batch=BATCH,
        imgsz=IMGSZ,
        device=DEVICE,
        project=OUTPUT_DIR,
        name="train_v2",
        exist_ok=True,
        pretrained=True,
        workers=0,          # Required on Windows to avoid multiprocessing spawn error

        # --- Data Augmentation (for varying CCTV conditions) ---
        hsv_h=0.015,       # Hue variation
        hsv_s=0.7,         # Saturation variation
        hsv_v=0.4,         # Brightness variation
        degrees=10.0,      # ±10° rotation (tilted cameras)
        translate=0.1,     # ±10% translation
        scale=0.5,         # Scale variation
        flipud=0.1,        # Vertical flip (small chance)
        fliplr=0.5,        # Horizontal flip
        mosaic=1.0,        # Mosaic augmentation (4 images combined)
        mixup=0.1,         # MixUp augmentation (blend 2 images)
        erasing=0.4,       # Random erasing (occlusion simulation)

        # --- Training Hyperparameters ---
        optimizer="auto",   # Let YOLO pick the best optimizer
        lr0=0.01,           # Initial learning rate
        lrf=0.01,           # Final learning rate factor
        warmup_epochs=3.0,  # Warmup period
        patience=15,        # Early stopping if no improvement for 15 epochs
        cos_lr=True,        # Cosine annealing LR schedule (smoother training)

        # --- Output ---
        plots=True,         # Generate evaluation plots
        save=True,          # Save checkpoints
        verbose=True,
    )

    # =================== RESULTS ===================
    print(f"\n{'='*60}")
    print(f"  Training Complete!")
    print(f"  Best weights: {OUTPUT_DIR}/train_v2/weights/best.pt")
    print(f"{'='*60}")
    print(f"\n  To use the new model, update your .env:")
    print(f"  MODEL_PATH = \"{os.path.join(OUTPUT_DIR, 'train_v2', 'weights', 'best.pt')}\"")
