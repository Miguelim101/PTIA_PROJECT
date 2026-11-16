# audit_dataset.py
# Auditoría de fuga y sesgo del dataset tabular antes de entrenar. Escribe training/reports/audit.md
# y training/reports/feature_histograms.png. Solo usa la partición train (val y test quedan intactos).
# Uso: python training/audit_dataset.py
#
# Preguntas que responde:
#   1. ¿Alguna característica sola separa las clases casi a la perfección? (posible fuga)
#   2. ¿Cuánto depende un modelo de las cabeceras de infraestructura (SPF, DKIM, saltos)?
#   3. ¿Lo aprendido con una fuente de phishing sirve para la otra? (sesgo de fuente)
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import f1_score, roc_auc_score  # noqa: E402
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict  # noqa: E402
from sklearn.tree import DecisionTreeClassifier  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.extractor import FEATURE_NAMES, LOG_FEATURES  # noqa: E402

TRAINING_DIR = Path(__file__).resolve().parent
DATASET_CSV = TRAINING_DIR / "datasets" / "dataset.csv"
REPORTS_DIR = TRAINING_DIR / "reports"
SEED = 42
LEAK_THRESHOLD = 0.90   # exactitud de una sola característica que se considera sospechosa
INFRASTRUCTURE = ["spf_pass", "dkim_pass", "has_auth_results", "num_received_hops"]


def group_cv(n_splits=5):
    return StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=SEED)


def forest():
    return RandomForestClassifier(n_estimators=300, min_samples_leaf=2, n_jobs=-1, random_state=SEED)


def cv_scores(model, X, y, groups):
    """Exactitud, F1 y AUC con validación cruzada agrupada por remitente."""
    proba = cross_val_predict(model, X, y, groups=groups, cv=group_cv(), method="predict_proba")[:, 1]
    predicted = (proba >= 0.5).astype(int)
    return (predicted == y).mean(), f1_score(y, predicted), roc_auc_score(y, proba)


def single_feature_table(train):
    """Árbol de profundidad 2 por característica: cuánto acierta cada una por sí sola."""
    y, groups = train["label"].to_numpy(), train["sender_domain"].fillna("").to_numpy()
    rows = []
    for name in FEATURE_NAMES:
        X = train[[name]].to_numpy()
        accuracy, _, auc = cv_scores(DecisionTreeClassifier(max_depth=2, random_state=SEED), X, y, groups)
        phishing, legitimate = train.loc[train.label == 1, name], train.loc[train.label == 0, name]
        rows.append({
            "feature": name, "accuracy": accuracy, "auc": max(auc, 1 - auc),
            "mean_phishing": phishing.mean(), "mean_legitimate": legitimate.mean(),
            "nonzero_phishing": (phishing > 0).mean(), "nonzero_legitimate": (legitimate > 0).mean(),
        })
    return pd.DataFrame(rows).sort_values("accuracy", ascending=False)


def ablation_table(train):
    y, groups = train["label"].to_numpy(), train["sender_domain"].fillna("").to_numpy()
    sets = {
        "28 características": FEATURE_NAMES,
        "sin infraestructura (SPF, DKIM, Auth-Results, saltos)": [f for f in FEATURE_NAMES if f not in INFRASTRUCTURE],
        "solo infraestructura": INFRASTRUCTURE,
    }
    return [(name, *cv_scores(forest(), train[cols].to_numpy(), y, groups)) for name, cols in sets.items()]


def cross_source_table(train):
    """Entrena con una fuente de phishing y evalúa con la otra (legítimos separados por remitente)."""
    legit = train[train.label == 0]
    domains = np.array(sorted(legit["sender_domain"].fillna("").unique()))
    rng = np.random.default_rng(SEED)
    rng.shuffle(domains)
    held_out = set(domains[: len(domains) // 2])
    legit_a = legit[~legit.sender_domain.isin(held_out)]
    legit_b = legit[legit.sender_domain.isin(held_out)]
    rows = []
    for train_source, test_source in (("nazario", "phishing_pot"), ("phishing_pot", "nazario")):
        fit = pd.concat([train[train.source == train_source], legit_a])
        evaluate = pd.concat([train[train.source == test_source], legit_b])
        for name, cols in (("28 características", FEATURE_NAMES),
                           ("sin num_received_hops", [f for f in FEATURE_NAMES if f != "num_received_hops"]),
                           ("sin infraestructura", [f for f in FEATURE_NAMES if f not in INFRASTRUCTURE])):
            model = forest().fit(fit[cols].to_numpy(), fit["label"])
            proba = model.predict_proba(evaluate[cols].to_numpy())[:, 1]
            predicted = (proba >= 0.5).astype(int)
            y = evaluate["label"].to_numpy()
            recall = predicted[y == 1].mean()
            rows.append((f"{train_source} → {test_source}", name, (predicted == y).mean(), recall,
                         roc_auc_score(y, proba)))
    return rows


def hops_by_source(train):
    return train.groupby("source")["num_received_hops"].agg(["mean", "median"])


def short_email_coverage(data):
    """Proporción de correos con pocos enlaces por clase: si casi no hay legítimos así, el modelo
    tenderá a marcar como phishing cualquier correo corto (p. ej. de un profesor o un compañero)."""
    few = data["num_urls"] <= 3
    return {label: few[data.label == label].mean() for label in (0, 1)}


def source_detection(train):
    """¿Las características delatan la fuente de phishing? (Nazario vs phishing_pot)."""
    phishing = train[train.label == 1]
    y = (phishing["source"] == "nazario").astype(int).to_numpy()
    accuracy, _, auc = cv_scores(forest(), phishing[FEATURE_NAMES].to_numpy(), y,
                                 phishing["sender_domain"].fillna("").to_numpy())
    return accuracy, auc


def plot_histograms(train):
    columns = 4
    lines = math.ceil(len(FEATURE_NAMES) / columns)
    fig, axes = plt.subplots(lines, columns, figsize=(16, 3 * lines))
    for ax, name in zip(axes.flat, FEATURE_NAMES):
        values = train[name].astype(float)
        if name in LOG_FEATURES:
            values = np.log1p(values)
        bins = np.histogram_bin_edges(values, bins=30)
        for label, color, text in ((0, "#2b7bba", "legítimo"), (1, "#d6452a", "phishing")):
            ax.hist(values[train.label == label], bins=bins, alpha=0.55, color=color, label=text, density=True)
        ax.set_title(name + (" (log1p)" if name in LOG_FEATURES else ""), fontsize=9)
        ax.tick_params(labelsize=7)
    for ax in list(axes.flat)[len(FEATURE_NAMES):]:
        ax.axis("off")
    axes.flat[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "feature_histograms.png", dpi=110)
    plt.close(fig)


def main():
    data = pd.read_csv(DATASET_CSV)
    train = data[data.split == "train"].reset_index(drop=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    single = single_feature_table(train)
    ablation = ablation_table(train)
    cross = cross_source_table(train)
    source_accuracy, source_auc = source_detection(train)
    hops = hops_by_source(train)
    coverage = short_email_coverage(train)
    plot_histograms(train)

    split_counts = pd.crosstab(data["split"], data["label"]).reindex(["train", "val", "test"])
    lines = [
        "# Auditoría del dataset",
        "",
        f"Dataset: {len(data)} correos ({int((data.label == 1).sum())} phishing, {int((data.label == 0).sum())} legítimos). "
        "Todo se calcula solo con la partición train, con validación cruzada de 5 pliegues agrupada por "
        "dominio remitente (un remitente nunca está a la vez en entrenamiento y evaluación).",
        "",
        "## Partición (estratificada y agrupada por dominio remitente)",
        "",
        "| Partición | Phishing | Legítimos | Total |",
        "|---|---|---|---|",
    ]
    for split, row in split_counts.iterrows():
        lines.append(f"| {split} | {row.get(1, 0)} | {row.get(0, 0)} | {row.sum()} |")

    lines += [
        "",
        "## 1. Poder de cada característica por sí sola",
        "",
        f"Árbol de decisión de profundidad 2 entrenado con una sola característica. Una exactitud ≥ {LEAK_THRESHOLD:.0%} "
        "indica que esa variable casi decide sola la clase y debe revisarse.",
        "",
        "| Característica | Exactitud | AUC | Media phishing | Media legítimo | % ≠0 phishing | % ≠0 legítimo | Alerta |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in single.itertuples():
        alert = "⚠️" if r.accuracy >= LEAK_THRESHOLD else ""
        lines.append(
            f"| {r.feature} | {r.accuracy:.1%} | {r.auc:.3f} | {r.mean_phishing:.3f} | {r.mean_legitimate:.3f} | "
            f"{r.nonzero_phishing:.0%} | {r.nonzero_legitimate:.0%} | {alert} |"
        )

    lines += [
        "",
        "## 2. Dependencia de las cabeceras de infraestructura",
        "",
        "Random Forest de referencia (no es el modelo final). Si quitar SPF, DKIM, Authentication-Results y los "
        "saltos casi no cambia el resultado, el modelo no depende de cómo se recibió cada corpus.",
        "",
        "| Conjunto de características | Exactitud | F1 | AUC |",
        "|---|---|---|---|",
    ]
    lines += [f"| {name} | {acc:.1%} | {f1:.3f} | {auc:.3f} |" for name, acc, f1, auc in ablation]

    lines += [
        "",
        "## 3. Generalización entre fuentes de phishing",
        "",
        "Se entrena con el phishing de una fuente y se evalúa con el de la otra; los legítimos se dividen por "
        "remitente. Un recall alto indica que el modelo aprende rasgos de phishing y no rasgos de la fuente.",
        "",
        "| Entrenamiento → evaluación | Características | Exactitud | Recall phishing | AUC |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {pair} | {name} | {acc:.1%} | {recall:.1%} | {auc:.3f} |" for pair, name, acc, recall, auc in cross]

    lines += [
        "",
        f"Distinguir Nazario de phishing_pot con las 28 características: exactitud {source_accuracy:.1%}, "
        f"AUC {source_auc:.3f}. Es esperable que sea alto (son épocas y víctimas distintas); lo importante es "
        "que el punto 3 muestre que el phishing de una fuente se detecta con lo aprendido de la otra.",
        "",
        "Saltos `Received` por fuente (media / mediana): "
        + ", ".join(f"{source} {row['mean']:.1f} / {row['median']:.0f}" for source, row in hops.iterrows())
        + ". El número de saltos depende sobre todo del servidor que recibió cada corpus (Outlook para "
        "phishing_pot, monkey.org para Nazario, Gmail para los legítimos), no del remitente.",
        "",
        "## 4. Cobertura de correos legítimos cortos",
        "",
        f"Correos con 3 enlaces o menos: {coverage[0]:.1%} de los legítimos y {coverage[1]:.1%} del phishing. "
        "Si los legítimos son casi todos boletines con muchos enlaces e imágenes, el modelo asociará "
        "\"pocos enlaces\" con phishing y fallará con correos personales o institucionales cortos.",
        "",
        "## Histogramas por clase (train)",
        "",
        "![Histogramas](feature_histograms.png)",
        "",
    ]
    (REPORTS_DIR / "audit.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
