# sources.py
# Catálogo de fuentes de correos crudos usadas para construir el corpus.
# label: 1 = phishing, 0 = legítimo. weight: proporción deseada dentro de su clase.
from pathlib import Path

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
RAW_DIR = DATASETS_DIR / "raw"            # correos crudos descargados (fuera de git)
CURATED_DIR = DATASETS_DIR / "curated"    # corpus final balanceado (fuera de git)
LISTS_DIR = DATASETS_DIR / "sources"      # listas pequeñas versionadas en git
# Correos locales para probar el modelo a mano: nunca deben entrar al entrenamiento
HOLDOUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "eml_files"

NAZARIO_URL = "https://monkey.org/~jose/phishing/"
PHISHING_POT_RAW_URL = "https://raw.githubusercontent.com/rf-peixoto/phishing_pot/main/email/"
PHISHING_POT_TREE_URL = "https://api.github.com/repos/rf-peixoto/phishing_pot/git/trees/main?recursive=1"

SOURCES = [
    # --- Phishing ---
    {
        "name": "nazario",
        "label": 1,
        "weight": 0.5,
        "path": RAW_DIR / "nazario",
        "kind": "url_files",
        "mbox": True,
        "trusted": True,  # clasificado a mano por su autor
        "urls": [NAZARIO_URL + f"phishing-{year}" for year in range(2020, 2026)],
        "citation": "Nazario, J. Phishing Corpus (CC-BY-4.0). https://monkey.org/~jose/phishing/",
    },
    {
        "name": "phishing_pot",
        "label": 1,
        "weight": 0.5,
        "path": RAW_DIR / "phishing_pot",
        "kind": "github_list",
        "list_file": LISTS_DIR / "phishing_pot_files.txt",
        "citation": "rf-peixoto. phishing_pot. https://github.com/rf-peixoto/phishing_pot",
    },
    # --- Legítimos ---
    {
        "name": "personal",
        "label": 0,
        "weight": 1.0,
        "path": RAW_DIR / "personal",
        "kind": "manual",  # Gmail: download_gmail.py, Google Takeout (.mbox) o "Descargar mensaje" (.eml)
        "citation": "Buzón de Gmail del autor del repositorio, no publicado.",
    },
]

# Correos legítimos de los demás integrantes: una subcarpeta por persona en raw/grupo/<nombre>/.
# Cada integrante es una fuente con el mismo peso que el buzón personal, de modo que los legítimos
# se reparten en partes iguales entre los buzones (lo que falte en uno se completa con los demás).
GROUP_DIR = RAW_DIR / "grupo"
if GROUP_DIR.exists():
    for member in sorted(p for p in GROUP_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")):
        SOURCES.append({
            "name": f"grupo_{member.name}",
            "label": 0,
            "weight": 1.0,
            "path": member,
            "kind": "manual",
            "citation": f"Buzón del integrante {member.name}, no publicado.",
        })

# Etiquetas de Gmail (cabecera X-Gmail-Labels de Takeout) que NO se consideran legítimas
EXCLUDED_GMAIL_LABELS = {"spam", "trash", "papelera", "sent", "enviados", "draft", "borradores", "chat"}
