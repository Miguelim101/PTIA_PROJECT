# train_ann.py
# Entrena el Perceptrón Multicapa (entradas -> 64 -> 32 -> 1 por defecto) y exporta los artefactos que usa la API:
#   backend/app/models/phishing_model.keras  red entrenada
#   backend/app/models/scaler.pkl            StandardScaler ajustado solo con train
#   backend/app/models/model_meta.json       características, umbral y métricas
# Además escribe training/reports/training.md, curvas y matriz de confusión, y agrega una fila a
# training/reports/experiments.csv. El conjunto de prueba se evalúa una sola vez, al final.
# Uso: python training/train_ann.py [--hidden 64 32] [--dropout 0.3] [--l2 0.01] [--lr 0.001] [--batch-size 128]
#      [--epochs 300] [--patience 25] [--threshold 0.5] [--note "texto"]
# Hiperparámetros por defecto elegidos solo con validación (AUC y F1 promedio de 3 semillas).
# evaluate_splits.py acepta los mismos parámetros del modelo (add_model_args).
import argparse
import csv
import json
import os
from datetime import datetime

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import joblib  # noqa: E402
import keras  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import sklearn  # noqa: E402
import tensorflow as tf  # noqa: E402
from sklearn.metrics import ConfusionMatrixDisplay, RocCurveDisplay  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from preprocessing import (METRICS_HEADER, MODEL_FEATURES, LOG_FEATURES, MODELS_DIR, REPORTS_DIR, SEED,  # noqa: E402
                           best_threshold, evaluate, load_splits, metrics_row)


def build_model(n_inputs, dropout, learning_rate, l2=0.0, hidden=(64, 32)):
    regularizer = keras.regularizers.L2(l2) if l2 else None
    layers = [keras.Input(shape=(n_inputs,))]
    for units in hidden:
        layers += [keras.layers.Dense(units, activation="relu", kernel_regularizer=regularizer),
                   keras.layers.Dropout(dropout)]
    model = keras.Sequential(layers + [keras.layers.Dense(1, activation="sigmoid")])
    model.compile(optimizer=keras.optimizers.Adam(learning_rate), loss="binary_crossentropy",
                  metrics=["accuracy", keras.metrics.AUC(name="auc")])
    return model


def plot_history(history):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, metric, title in ((axes[0], "loss", "Pérdida (entropía cruzada)"), (axes[1], "accuracy", "Exactitud")):
        ax.plot(history.history[metric], label="train")
        ax.plot(history.history[f"val_{metric}"], label="validación")
        ax.set_title(title)
        ax.set_xlabel("Época")
        ax.legend()
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "training_curves.png", dpi=110)
    plt.close(fig)


def plot_evaluation(y_val, proba_val, y_test, proba_test, threshold):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    RocCurveDisplay.from_predictions(y_val, proba_val, name="validación", ax=axes[0])
    RocCurveDisplay.from_predictions(y_test, proba_test, name="prueba", ax=axes[0])
    axes[0].set_title("Curva ROC")
    ConfusionMatrixDisplay.from_predictions(y_test, (proba_test >= threshold).astype(int),
                                            display_labels=["legítimo", "phishing"], cmap="Blues",
                                            colorbar=False, ax=axes[1])
    axes[1].set_title(f"Matriz de confusión (prueba, umbral {threshold:.2f})")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "evaluation.png", dpi=110)
    plt.close(fig)


def add_model_args(parser):
    """Hiperparámetros del modelo, compartidos con evaluate_splits.py."""
    parser.add_argument("--hidden", type=int, nargs="+", default=[64, 32],
                        help="neuronas de cada capa oculta, p. ej. --hidden 64 32")
    parser.add_argument("--dropout", type=float, default=0.3, help="fracción de neuronas apagadas al entrenar")
    parser.add_argument("--l2", type=float, default=0.01, help="regularización L2 de las capas ocultas (0 = sin L2)")
    parser.add_argument("--lr", type=float, default=0.001, help="tasa de aprendizaje del optimizador Adam")
    parser.add_argument("--batch-size", type=int, default=128, help="correos por lote de entrenamiento")
    parser.add_argument("--epochs", type=int, default=300, help="máximo de épocas")
    parser.add_argument("--patience", type=int, default=25,
                        help="épocas sin mejorar la pérdida de validación antes de detenerse (EarlyStopping)")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="umbral de decisión. Se usa 0.5 fijo: la curva de F1 es plana y el umbral con máximo F1 "
                             "en validación variaba entre 0.13 y 0.73 según la partición, sin mejorar el F1")


def main():
    parser = argparse.ArgumentParser()
    add_model_args(parser)
    parser.add_argument("--note", default="", help="nota para el registro de experimentos")
    args = parser.parse_args()

    keras.utils.set_random_seed(SEED)
    tf.config.experimental.enable_op_determinism()

    splits = load_splits()
    X_train, y_train, _ = splits["train"]
    X_val, y_val, _ = splits["val"]
    X_test, y_test, test_rows = splits["test"]

    scaler = StandardScaler().fit(X_train)
    X_train_s, X_val_s, X_test_s = (scaler.transform(X) for X in (X_train, X_val, X_test))

    model = build_model(X_train.shape[1], args.dropout, args.lr, args.l2, args.hidden)
    stop = keras.callbacks.EarlyStopping(monitor="val_loss", patience=args.patience, restore_best_weights=True)
    history = model.fit(X_train_s, y_train, validation_data=(X_val_s, y_val), epochs=args.epochs,
                        batch_size=args.batch_size, callbacks=[stop], verbose=0)
    epochs_run = len(history.history["loss"])
    best_epoch = int(np.argmin(history.history["val_loss"])) + 1

    proba_train = model.predict(X_train_s, verbose=0).ravel()
    proba_val = model.predict(X_val_s, verbose=0).ravel()
    threshold = args.threshold
    # Solo informativo: umbral que maximizaría F1 en validación (no se usa; ver --threshold)
    val_best = best_threshold(y_val, proba_val)
    results = {
        "train": evaluate(y_train, proba_train, threshold),
        "val": evaluate(y_val, proba_val, threshold),
        "val@best": evaluate(y_val, proba_val, val_best),
    }
    # Evaluación final: el conjunto de prueba se usa una sola vez
    proba_test = model.predict(X_test_s, verbose=0).ravel()
    results["test"] = evaluate(y_test, proba_test, threshold)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)
    model.save(MODELS_DIR / "phishing_model.keras")
    joblib.dump(scaler, MODELS_DIR / "scaler.pkl")
    meta = {
        "features": MODEL_FEATURES,
        "log_features": sorted(LOG_FEATURES & set(MODEL_FEATURES)),
        "threshold": threshold,
        "architecture": " -> ".join(map(str, [X_train.shape[1], *args.hidden, 1]))
                        + f" (ReLU, Dropout {args.dropout}, L2 {args.l2}, sigmoide)",
        "metrics_test": {k: round(v, 4) if isinstance(v, float) else v for k, v in results["test"].items()},
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "versions": {"tensorflow": tf.__version__, "keras": keras.__version__, "scikit-learn": sklearn.__version__},
    }
    (MODELS_DIR / "model_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    plot_history(history)
    plot_evaluation(y_val, proba_val, y_test, proba_test, threshold)

    # Errores del conjunto de prueba, para el análisis de casos (sin asuntos ni remitentes privados)
    predicted = (proba_test >= threshold).astype(int)
    errors = test_rows.assign(score=proba_test)[predicted != y_test]

    lines = [
        "# Entrenamiento del MLP",
        "",
        f"Arquitectura: {meta['architecture']}. Adam (lr {args.lr}), entropía cruzada binaria, lotes de "
        f"{args.batch_size}. EarlyStopping sobre la pérdida de validación (paciencia {args.patience}): "
        f"{epochs_run} épocas ejecutadas, mejor época {best_epoch}.",
        "",
        f"Umbral de decisión: **{threshold:.2f}** (fijo). En validación, el umbral con máximo F1 sería "
        f"{val_best:.2f} (F1 {results['val@best']['f1']:.3f}, frente a {results['val']['f1']:.3f} con "
        f"{threshold:.2f}): la curva de F1 es plana y ese máximo cambia mucho entre particiones, así que no se ajusta.",
        "",
        *METRICS_HEADER,
        metrics_row("MLP · train", results["train"]),
        metrics_row("MLP · validación", results["val"]),
        metrics_row(f"**MLP · prueba (umbral {threshold:.2f})**", results["test"]),
        "",
        "Metas del documento: exactitud, precisión, recall y F1 > 90 %; AUC ≥ 0,9.",
        "",
        "Los hiperparámetros se eligen solo con validación. El conjunto de prueba nunca se usa para "
        "tomar decisiones; cada ejecución lo evalúa una vez y queda registrada en `experiments.csv`.",
        "",
        "![Curvas de entrenamiento](training_curves.png)",
        "",
        "![ROC y matriz de confusión](evaluation.png)",
        "",
        "## Errores en prueba",
        "",
        "| Archivo | Clase real | Fuente | Score |",
        "|---|---|---|---|",
    ]
    for row in errors.sort_values("score").itertuples():
        lines.append(f"| {row.file} | {'phishing' if row.label else 'legítimo'} | {row.source} | {row.score:.3f} |")
    (REPORTS_DIR / "training.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    log = REPORTS_DIR / "experiments.csv"
    new_log = not log.exists()
    with open(log, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if new_log:
            writer.writerow(["fecha", "entradas", "dropout", "l2", "lr", "batch", "epocas", "mejor_epoca", "umbral",
                             "val_f1", "val_auc", "test_accuracy", "test_precision", "test_recall", "test_f1",
                             "test_auc", "nota"])
        v, t = results["val"], results["test"]
        writer.writerow([meta["trained_at"], X_train.shape[1], args.dropout, args.l2, args.lr, args.batch_size, epochs_run,
                         best_epoch, threshold, f"{v['f1']:.4f}", f"{v['auc']:.4f}", f"{t['accuracy']:.4f}",
                         f"{t['precision']:.4f}", f"{t['recall']:.4f}", f"{t['f1']:.4f}", f"{t['auc']:.4f}", args.note])
    print("\n".join(lines[:14]))


if __name__ == "__main__":
    main()
