# build_corpus.py
# Curado del corpus: valida, deduplica, filtra la calidad del phishing, limita campañas y remitentes
# repetidos, balancea por clase y fuente, y escribe los correos seleccionados en datasets/curated/
# junto con manifest.csv y el reporte corpus_report.md. Los correos de prueba locales (tests/eml_files/,
# incluidos los que están dentro de archivos .zip) se excluyen siempre, para que sigan siendo una prueba
# honesta del modelo con correos que nunca vio.
# Uso: python training/build_corpus.py [--phishing 2500] [--legitimate 2500] [--campaign-cap 2] [--sender-cap 15]
#      [--legit-sender-cap 60]
import argparse
import csv
import hashlib
import random
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime

from bs4 import BeautifulSoup

from data_sources import iter_emails
from phishing_quality import classify_phishing
from sources import CURATED_DIR, DATASETS_DIR, EXCLUDED_GMAIL_LABELS, HOLDOUT_DIR, SOURCES

SEED = 42
LABEL_NAMES = {1: "phishing", 0: "legitimate"}
SUBJECT_PREFIX = re.compile(r"^\s*((re|fw|fwd|rv|res)\s*(\[\d+\])?\s*:\s*)+", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)


def normalize_subject(subject: str) -> str:
    subject = SUBJECT_PREFIX.sub("", subject.lower())
    subject = re.sub(r"\d+", "#", subject)
    subject = re.sub(r"[^\w#%$]+", " ", subject)
    return " ".join(subject.split())[:120]


def sender_domain(from_header: str) -> str:
    address = parseaddr(from_header)[1]
    return address.rsplit("@", 1)[-1].lower() if "@" in address else ""


def read_parts(msg):
    """Devuelve (texto plano, html, nombres de adjuntos) recorriendo todas las partes MIME."""
    text, html, attachments = "", "", []
    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if filename:
            attachments.append(filename.lower())
            continue
        content_type = part.get_content_type()
        if content_type not in ("text/plain", "text/html"):
            continue
        try:
            content = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            content = payload.decode("utf-8", errors="ignore")
        if not isinstance(content, str):
            continue
        if content_type == "text/plain":
            text += content
        else:
            html += content
    return text, html, attachments


def inspect(raw: bytes, label: int, trusted: bool = False):
    """Analiza un correo crudo. Devuelve (registro, motivo_de_descarte)."""
    try:
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        from_header = str(msg.get("from", "") or "")
        subject = str(msg.get("subject", "") or "")
        message_id = str(msg.get("message-id", "") or "").strip()
        gmail_labels = str(msg.get("x-gmail-labels", "") or "")
        has_received = bool(msg.get_all("received"))
        auth_results = str(msg.get("authentication-results", "") or "").lower()
    except Exception:
        return None, "no_parseable"

    if not from_header or not has_received:
        return None, "sin_cabeceras"
    labels = {label.strip().lower() for label in gmail_labels.split(",") if label.strip()}
    if labels & EXCLUDED_GMAIL_LABELS:
        return None, "etiqueta_excluida"

    try:
        text, html, attachments = read_parts(msg)
    except Exception:
        return None, "cuerpo_ilegible"
    visible = text.strip()
    if html and len(visible) < 50:
        visible = html
    if "<" in visible and re.search(r"<(html|body|div|td|p|table)\b", visible, re.IGNORECASE):
        # Algunos correos declaran text/plain pero contienen HTML
        visible = BeautifulSoup(visible, "html.parser").get_text(" ", strip=True)
    visible = " ".join(visible.split())
    if not visible and not attachments:
        return None, "cuerpo_vacio"

    category, language = "", ""
    if label == 1:
        category, language, reason = classify_phishing(
            subject, visible, bool(URL_PATTERN.search(text + html)), attachments, trusted
        )
        if reason:
            return None, reason

    try:
        year = parsedate_to_datetime(str(msg.get("date"))).year
    except Exception:
        year = ""

    domain = sender_domain(from_header)
    return {
        "message_id": message_id,
        "subject": subject,
        "sender_domain": domain,
        "campaign_id": f"{normalize_subject(subject)}|{domain}",
        "category": category,
        "language": language,
        "year": year,
        "has_received": int(has_received),
        "has_auth_results": int(bool(auth_results)),
        "spf_pass": int("spf=pass" in auth_results),
        "dkim_pass": int("dkim=pass" in auth_results),
        "is_html": int(bool(html)),
    }, None


def message_id_of(raw: bytes) -> str:
    try:
        return str(BytesParser(policy=policy.default).parsebytes(raw, headersonly=True).get("message-id", "") or "").strip()
    except Exception:
        return ""


def load_holdout():
    """Huellas (sha256 y Message-ID) de los correos de prueba locales, sueltos o dentro de .zip."""
    raws = []
    if HOLDOUT_DIR.exists():
        for path in HOLDOUT_DIR.rglob("*"):
            if path.suffix.lower() == ".eml":
                raws.append(path.read_bytes())
            elif path.suffix.lower() == ".zip":
                try:
                    with zipfile.ZipFile(path) as archive:
                        raws += [archive.read(n) for n in archive.namelist() if n.lower().endswith(".eml")]
                except zipfile.BadZipFile:
                    pass
    hashes = {hashlib.sha256(raw).hexdigest() for raw in raws}
    message_ids = {mid for mid in map(message_id_of, raws) if mid}
    return hashes, message_ids


def collect(source, seen_hashes, seen_message_ids, stats, holdout):
    records = []
    if not source["path"].exists():
        return records
    for ref, raw in iter_emails(source["path"], mbox=source.get("mbox", False)):
        stats["leidos"] += 1
        digest = hashlib.sha256(raw).hexdigest()
        if digest in seen_hashes:
            stats["duplicados"] += 1
            continue
        seen_hashes.add(digest)
        if digest in holdout[0] or message_id_of(raw) in holdout[1]:
            stats["reservado_prueba"] += 1
            continue
        record, reason = inspect(raw, source["label"], source.get("trusted", False))
        if reason:
            stats[reason] += 1
            continue
        if record["message_id"]:
            if record["message_id"] in seen_message_ids:
                stats["duplicados"] += 1
                continue
            seen_message_ids.add(record["message_id"])
        record.update(sha256=digest, raw=raw, ref=ref, source=source["name"], label=source["label"])
        records.append(record)
    return records


def cap_groups(records, key, cap, rng):
    """Conserva como máximo 'cap' correos por grupo (campaña o dominio remitente)."""
    groups = defaultdict(list)
    for record in records:
        groups[record[key]].append(record)
    kept = []
    for group in groups.values():
        rng.shuffle(group)
        kept.extend(group[:cap])
    return kept, len(groups)


def allocate(available, weights, total):
    """Reparte 'total' entre fuentes según sus pesos, redistribuyendo lo que falte."""
    quota = {name: 0 for name in available}
    remaining = total
    active = {name for name, count in available.items() if count > 0}
    while remaining > 0 and active:
        weight_sum = sum(weights[name] for name in active)
        assigned = 0
        for name in sorted(active):
            share = max(1, round(remaining * weights[name] / weight_sum))
            share = min(share, available[name] - quota[name], remaining - assigned)
            quota[name] += share
            assigned += share
        remaining -= assigned
        active = {name for name in active if quota[name] < available[name]}
        if assigned == 0:
            break
    return quota


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phishing", type=int, default=2500, help="correos de phishing a seleccionar")
    parser.add_argument("--legitimate", type=int, default=2500, help="correos legítimos a seleccionar")
    parser.add_argument("--campaign-cap", type=int, default=2,
                        help="máximo de correos por campaña (asunto normalizado + dominio remitente)")
    parser.add_argument("--sender-cap", type=int, default=15,
                        help="máximo de correos de phishing por dominio remitente")
    parser.add_argument("--legit-sender-cap", type=int, default=60,
                        help="máximo de correos legítimos por dominio remitente (evita que pocos boletines dominen)")
    args = parser.parse_args()
    rng = random.Random(SEED)
    # Un generador por fuente: agregar o quitar correos de una fuente no cambia la selección de las demás
    source_rng = {source["name"]: random.Random(f"{SEED}:{source['name']}") for source in SOURCES}
    holdout = load_holdout()
    print(f"Correos de prueba reservados (tests/eml_files/): {len(holdout[0])}")

    seen_hashes, seen_message_ids = set(), set()
    pools, stats = {}, {}
    for source in SOURCES:
        name = source["name"]
        stats[name] = Counter()
        records = collect(source, seen_hashes, seen_message_ids, stats[name], holdout)
        stats[name]["validos"] = len(records)
        records, stats[name]["campañas"] = cap_groups(records, "campaign_id", args.campaign_cap, source_rng[name])
        sender_cap = args.sender_cap if source["label"] == 1 else args.legit_sender_cap
        records, _ = cap_groups(records, "sender_domain", sender_cap, source_rng[name])
        pools[name] = records

    if CURATED_DIR.exists():
        shutil.rmtree(CURATED_DIR)
    selected = []
    for label in (1, 0):
        names = [s["name"] for s in SOURCES if s["label"] == label]
        weights = {s["name"]: s["weight"] for s in SOURCES if s["label"] == label}
        class_target = args.phishing if label == 1 else args.legitimate
        quota = allocate({n: len(pools[n]) for n in names}, weights, class_target)
        for name in names:
            source_rng[name].shuffle(pools[name])
            selected.extend(pools[name][: quota[name]])

    manifest_fields = ["file", "sha256", "label", "source", "ref", "category", "language",
                       "campaign_id", "year", "has_received", "has_auth_results", "spf_pass",
                       "dkim_pass", "is_html"]
    with open(DATASETS_DIR / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=manifest_fields, extrasaction="ignore")
        writer.writeheader()
        for record in selected:
            relative = f"{LABEL_NAMES[record['label']]}/{record['sha256'][:20]}.eml"
            target = CURATED_DIR / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(record["raw"])
            record["file"] = relative
            writer.writerow(record)

    write_report(selected, stats, pools, args, rng)


def percent(values):
    return f"{100 * sum(values) / len(values):.0f}%" if values else "-"


def write_report(selected, stats, pools, args, rng):
    reasons = ["duplicados", "reservado_prueba", "sin_cabeceras", "cuerpo_vacio", "etiqueta_excluida", "idioma_fuera_de_alcance",
               "spam_promocional", "extorsion", "sin_senuelo_claro", "sin_vector"]
    lines = [
        "# Reporte del corpus curado",
        "",
        f"Parámetros: objetivo {args.phishing} phishing y {args.legitimate} legítimos, máximo {args.campaign_cap} correos por campaña, "
        f"máximo {args.sender_cap} (phishing) y {args.legit_sender_cap} (legítimos) por dominio remitente, semilla {SEED}.",
        "",
        "## Procesamiento por fuente",
        "",
        "| Fuente | Clase | Leídos | " + " | ".join(reasons) + " | Válidos | Campañas | Disponibles | Seleccionados |",
        "|---" * (7 + len(reasons)) + "|",
    ]
    by_source = defaultdict(list)
    for record in selected:
        by_source[record["source"]].append(record)
    for source in SOURCES:
        name = source["name"]
        s = stats[name]
        lines.append(
            f"| {name} | {LABEL_NAMES[source['label']]} | {s['leidos']} | "
            + " | ".join(str(s[r]) for r in reasons)
            + f" | {s['validos']} | {s['campañas']} | {len(pools[name])} | {len(by_source[name])} |"
        )

    lines += ["", "## Composición del corpus seleccionado", "",
              "| Fuente | Clase | Correos | % Received | % Auth-Results | % SPF pass | % DKIM pass | % HTML | Años |",
              "|---|---|---|---|---|---|---|---|---|"]
    groups = list(by_source.items()) + [
        (f"**TOTAL {LABEL_NAMES[label]}**", [r for r in selected if r["label"] == label]) for label in (1, 0)
    ]
    for name, records in groups:
        if not records:
            continue
        years = Counter(r["year"] for r in records if r["year"])
        year_range = f"{min(years)}–{max(years)}" if years else "-"
        lines.append(
            f"| {name} | {LABEL_NAMES[records[0]['label']]} | {len(records)} | "
            f"{percent([r['has_received'] for r in records])} | {percent([r['has_auth_results'] for r in records])} | "
            f"{percent([r['spf_pass'] for r in records])} | {percent([r['dkim_pass'] for r in records])} | "
            f"{percent([r['is_html'] for r in records])} | {year_range} |"
        )

    phishing = [r for r in selected if r["label"] == 1]
    if phishing:
        lines += ["", "## Phishing por tipo de señuelo e idioma", "", "| Señuelo | Correos | en | es | pt |",
                  "|---|---|---|---|---|"]
        by_category = defaultdict(Counter)
        for record in phishing:
            by_category[record["category"]][record["language"]] += 1
        for category, langs in sorted(by_category.items(), key=lambda item: -sum(item[1].values())):
            lines.append(f"| {category} | {sum(langs.values())} | {langs['en']} | {langs['es']} | {langs['pt']} |")

        lines += ["", "## Muestra aleatoria para revisión manual (asuntos de phishing)", ""]
        for record in rng.sample(phishing, min(40, len(phishing))):
            subject = " ".join(record["subject"].split())[:100].replace("|", "/")
            lines.append(f"- [{record['source']} · {record['category']} · {record['language']}] {subject}")

    lines += ["", "## Fuentes", ""] + [f"- **{s['name']}**: {s['citation']}" for s in SOURCES]
    report = "\n".join(lines) + "\n"
    (DATASETS_DIR / "corpus_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
