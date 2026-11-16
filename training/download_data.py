# download_data.py
# Descarga las fuentes públicas de phishing en training/datasets/raw/.
# Uso: python training/download_data.py [--refresh-list]
# Los correos legítimos (Gmail) se copian a mano en training/datasets/raw/personal/.
import argparse
import json
import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sources import PHISHING_POT_RAW_URL, PHISHING_POT_TREE_URL, SOURCES

MAX_FILE_BYTES = 500_000  # se omiten correos gigantes (relleno masivo o adjuntos pesados)


def download(url: str, destination: Path) -> Path:
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, open(partial, "wb") as out:
        shutil.copyfileobj(response, out)
    partial.rename(destination)
    return destination


def fetch_url_files(source):
    for url in source["urls"]:
        print(f"  {url}")
        download(url, source["path"] / url.rsplit("/", 1)[-1])


def build_phishing_pot_list(source):
    """Lista todos los correos del repositorio que no superan MAX_FILE_BYTES."""
    with urllib.request.urlopen(PHISHING_POT_TREE_URL, timeout=120) as response:
        tree = json.load(response)["tree"]
    names = [
        item["path"].removeprefix("email/")
        for item in tree
        if item["type"] == "blob" and item["path"].startswith("email/sample-")
        and item.get("size", 0) <= MAX_FILE_BYTES
    ]
    source["list_file"].parent.mkdir(parents=True, exist_ok=True)
    source["list_file"].write_text("\n".join(sorted(names)) + "\n")
    print(f"  lista con {len(names)} archivos en {source['list_file'].name}")


def fetch_github_list(source, refresh=False):
    if refresh or not source["list_file"].exists():
        build_phishing_pot_list(source)
    target = source["path"]
    target.mkdir(parents=True, exist_ok=True)
    names = source["list_file"].read_text().split()

    def fetch(name):
        destination = target / name
        if destination.exists():
            return True
        try:
            download(PHISHING_POT_RAW_URL + name, destination)
            return True
        except Exception as error:
            print(f"  no se pudo obtener {name}: {error}")
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        available = sum(pool.map(fetch, names))
    print(f"  {available}/{len(names)} archivos disponibles en {target}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-list", action="store_true",
                        help="vuelve a generar la lista de phishing_pot desde GitHub")
    args = parser.parse_args()
    for source in SOURCES:
        print(f"[{source['name']}]")
        if source["kind"] == "url_files":
            fetch_url_files(source)
        elif source["kind"] == "github_list":
            fetch_github_list(source, refresh=args.refresh_list)
        else:
            source["path"].mkdir(parents=True, exist_ok=True)
            print(f"  fuente manual: coloque los archivos en {source['path']}")


if __name__ == "__main__":
    main()
