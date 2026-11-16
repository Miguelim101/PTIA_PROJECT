# generate_dataset.py
# Construye el dataset tabular: recorre el corpus curado (manifest.csv), extrae las 28 características
# crudas de cada correo con el mismo extractor de la API y asigna la partición train/val/test.
# Uso: python training/generate_dataset.py
#
# La partición es 80/10/10, estratificada por clase y agrupada por dominio remitente: todos los correos
# de un mismo remitente (y por lo tanto de una misma campaña) quedan en una sola partición, para que el
# modelo se evalúe con remitentes que nunca vio. El CSV guarda valores crudos; log1p y StandardScaler se
# aplican al entrenar, ajustados solo con train.
import csv
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sklearn.model_selection import StratifiedGroupKFold

from sources import CURATED_DIR, DATASETS_DIR

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.extractor import FEATURE_NAMES, extract_email_features  # noqa: E402

SEED = 42
DATASET_CSV = DATASETS_DIR / "dataset.csv"
META_COLUMNS = ["file", "label", "source", "sender_domain", "campaign_id", "category", "language", "year", "split"]


def extract(relative_path: str) -> dict:
    return extract_email_features((CURATED_DIR / relative_path).read_bytes())


def assign_splits(rows):
    """80/10/10 con StratifiedGroupKFold (10 pliegues): un pliegue para test, otro para val."""
    labels = [row["label"] for row in rows]
    groups = [row["sender_domain"] or row["file"] for row in rows]
    folds = StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=SEED).split(rows, labels, groups)
    fold_of = {}
    for fold, (_, indices) in enumerate(folds):
        for index in indices:
            fold_of[index] = fold
    for index, row in enumerate(rows):
        row["split"] = "test" if fold_of[index] == 0 else "val" if fold_of[index] == 1 else "train"


def main():
    with open(DATASETS_DIR / "manifest.csv", encoding="utf-8") as fh:
        manifest = list(csv.DictReader(fh))
    if not manifest:
        sys.exit("manifest.csv está vacío: ejecute primero training/build_corpus.py")

    with ProcessPoolExecutor() as pool:
        features = list(pool.map(extract, [row["file"] for row in manifest], chunksize=50))

    rows = []
    for entry, values in zip(manifest, features):
        row = {column: entry.get(column, "") for column in META_COLUMNS}
        row["label"] = int(entry["label"])
        row["sender_domain"] = entry["campaign_id"].rsplit("|", 1)[-1]
        row.update(values)
        rows.append(row)
    assign_splits(rows)

    with open(DATASET_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=META_COLUMNS + FEATURE_NAMES)
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter((row["split"], row["label"]) for row in rows)
    print(f"{len(rows)} correos -> {DATASET_CSV}")
    for split in ("train", "val", "test"):
        phishing, legitimate = counts[(split, 1)], counts[(split, 0)]
        print(f"  {split:5}: {phishing + legitimate:5}  (phishing {phishing}, legítimos {legitimate})")


if __name__ == "__main__":
    main()
