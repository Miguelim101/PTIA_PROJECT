# preprocessing.py
# Carga del dataset tabular y preprocesamiento común a la línea base y al MLP:
# vector del modelo (MODEL_FEATURES con log1p, igual que la API) y métricas de evaluación.
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score, recall_score,
                             roc_auc_score)

TRAINING_DIR = Path(__file__).resolve().parent
ROOT = TRAINING_DIR.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.extractor import LOG_FEATURES, MODEL_FEATURES, to_vector  # noqa: E402

DATASET_CSV = TRAINING_DIR / "datasets" / "dataset.csv"
REPORTS_DIR = TRAINING_DIR / "reports"
MODELS_DIR = ROOT / "backend" / "app" / "models"
SEED = 42


def load_splits():
    """Devuelve {"train"|"val"|"test": (X, y, filas)} con X ya transformado por to_vector (log1p)."""
    if not DATASET_CSV.exists():
        sys.exit("No existe dataset.csv: ejecute primero training/generate_dataset.py")
    data = pd.read_csv(DATASET_CSV)
    splits = {}
    for name in ("train", "val", "test"):
        rows = data[data["split"] == name].reset_index(drop=True)
        X = np.array([to_vector(row) for row in rows[MODEL_FEATURES].to_dict("records")], dtype=np.float32)
        splits[name] = (X, rows["label"].to_numpy(dtype=np.int32), rows)
    return splits


def evaluate(y_true, proba, threshold=0.5) -> dict:
    predicted = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return {
        "accuracy": accuracy_score(y_true, predicted),
        "precision": precision_score(y_true, predicted, zero_division=0),
        "recall": recall_score(y_true, predicted),
        "f1": f1_score(y_true, predicted),
        "auc": roc_auc_score(y_true, proba),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def best_threshold(y_true, proba) -> float:
    """Umbral que maximiza F1 en validación (en empate, el menor: favorece el recall)."""
    candidates = np.round(np.arange(0.05, 0.96, 0.01), 2)
    scores = [f1_score(y_true, (proba >= t).astype(int)) for t in candidates]
    return float(candidates[int(np.argmax(scores))])


def metrics_row(name, metrics) -> str:
    return (f"| {name} | {metrics['accuracy']:.1%} | {metrics['precision']:.1%} | {metrics['recall']:.1%} | "
            f"{metrics['f1']:.3f} | {metrics['auc']:.3f} | {metrics['fp']} | {metrics['fn']} |")


METRICS_HEADER = [
    "| Modelo / conjunto | Exactitud | Precisión | Recall | F1 | AUC | Falsos positivos | Falsos negativos |",
    "|---|---|---|---|---|---|---|---|",
]

__all__ = ["LOG_FEATURES", "MODEL_FEATURES", "MODELS_DIR", "REPORTS_DIR", "SEED", "load_splits", "evaluate",
           "best_threshold", "metrics_row", "METRICS_HEADER"]
