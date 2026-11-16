# evaluate_splits.py
# Robustez de las métricas: repite el entrenamiento del MLP con 5 particiones 80/10/10 distintas
# (estratificadas y agrupadas por dominio remitente) y reporta la media y la desviación en prueba.
# Con ~490 correos de prueba, una sola partición puede mover las métricas varios puntos.
# Escribe training/reports/robustness.md.
# Uso: python training/evaluate_splits.py [mismos parámetros del modelo que train_ann.py, p. ej. --lr 0.0005]
import argparse
import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import keras  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.model_selection import StratifiedGroupKFold  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from preprocessing import DATASET_CSV, MODEL_FEATURES, REPORTS_DIR, SEED, evaluate, to_vector  # noqa: E402
from train_ann import add_model_args, build_model  # noqa: E402

SPLIT_SEEDS = (42, 1, 2, 3, 4)   # 42 es la partición oficial de generate_dataset.py
METRICS = ("accuracy", "precision", "recall", "f1", "auc")


def main():
    parser = argparse.ArgumentParser()
    add_model_args(parser)
    args = parser.parse_args()
    data = pd.read_csv(DATASET_CSV)
    X = np.array([to_vector(row) for row in data[MODEL_FEATURES].to_dict("records")], dtype=np.float32)
    y = data["label"].to_numpy()
    groups = data["sender_domain"].fillna(data["file"]).to_numpy()

    rows = []
    for split_seed in SPLIT_SEEDS:
        folds = list(StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=split_seed).split(X, y, groups))
        test, val = folds[0][1], folds[1][1]
        train = np.setdiff1d(np.arange(len(y)), np.concatenate([test, val]))
        scaler = StandardScaler().fit(X[train])
        keras.utils.set_random_seed(SEED)
        model = build_model(X.shape[1], args.dropout, args.lr, args.l2, args.hidden)
        model.fit(scaler.transform(X[train]), y[train], validation_data=(scaler.transform(X[val]), y[val]),
                  epochs=args.epochs, batch_size=args.batch_size, verbose=0,
                  callbacks=[keras.callbacks.EarlyStopping(monitor="val_loss", patience=args.patience,
                                                           restore_best_weights=True)])
        proba = model.predict(scaler.transform(X[test]), verbose=0).ravel()
        rows.append({"partición": split_seed, **evaluate(y[test], proba, args.threshold)})
        print(f"partición {split_seed}: " + ", ".join(f"{m} {rows[-1][m]:.3f}" for m in METRICS), flush=True)

    table = pd.DataFrame(rows)
    lines = [
        "# Robustez de las métricas",
        "",
        f"MLP ({len(MODEL_FEATURES)} entradas, capas {args.hidden}, Dropout {args.dropout}, L2 {args.l2}, lr {args.lr}, "
        f"lotes de {args.batch_size}, umbral {args.threshold}) entrenado con {len(SPLIT_SEEDS)} particiones 80/10/10 "
        "distintas, estratificadas y agrupadas por dominio remitente. Métricas en el conjunto de prueba de cada partición.",
        "",
        "| Partición | Exactitud | Precisión | Recall | F1 | AUC | Falsos positivos | Falsos negativos |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['partición']} | {r['accuracy']:.1%} | {r['precision']:.1%} | {r['recall']:.1%} | "
                     f"{r['f1']:.3f} | {r['auc']:.3f} | {r['fp']} | {r['fn']} |")
    mean, std = table[list(METRICS)].mean(), table[list(METRICS)].std()
    lines.append(f"| **Media ± desv.** | {mean.accuracy:.1%} ± {std.accuracy:.1%} | {mean.precision:.1%} ± {std.precision:.1%} | "
                 f"{mean.recall:.1%} ± {std.recall:.1%} | {mean.f1:.3f} ± {std.f1:.3f} | {mean.auc:.3f} ± {std.auc:.3f} | | |")
    (REPORTS_DIR / "robustness.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
