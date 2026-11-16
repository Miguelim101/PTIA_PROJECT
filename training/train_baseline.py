# train_baseline.py
# Líneas base para comparar con el MLP: Regresión Logística y Random Forest, con el mismo
# preprocesamiento (log1p + StandardScaler ajustado solo con train). Se evalúan solo en validación;
# el conjunto de prueba se reserva para la evaluación final del MLP.
# Uso: python training/train_baseline.py
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from preprocessing import METRICS_HEADER, REPORTS_DIR, SEED, MODEL_FEATURES, evaluate, load_splits, metrics_row


def main():
    splits = load_splits()
    X_train, y_train, _ = splits["train"]
    X_val, y_val, _ = splits["val"]

    models = {
        "Regresión logística": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)),
        "Random Forest": make_pipeline(StandardScaler(), RandomForestClassifier(
            n_estimators=300, min_samples_leaf=2, n_jobs=-1, random_state=SEED)),
    }
    lines = [
        "# Líneas base (validación)",
        "",
        f"Entradas: {len(MODEL_FEATURES)} características (log1p + StandardScaler ajustado con train). "
        f"Train {len(y_train)} correos, validación {len(y_val)}. Umbral 0.5.",
        "",
        *METRICS_HEADER,
    ]
    importances = None
    for name, model in models.items():
        model.fit(X_train, y_train)
        metrics = evaluate(y_val, model.predict_proba(X_val)[:, 1])
        lines.append(metrics_row(name, metrics))
        if name == "Random Forest":
            importances = sorted(zip(MODEL_FEATURES, model[-1].feature_importances_), key=lambda i: -i[1])

    lines += ["", "## Importancia de características (Random Forest)", "", "| Característica | Importancia |",
              "|---|---|"]
    lines += [f"| {feature} | {value:.3f} |" for feature, value in importances]
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / "baseline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
