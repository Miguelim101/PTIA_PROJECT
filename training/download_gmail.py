# download_gmail.py
# Descarga correos legítimos de una cuenta de Gmail por IMAP, uno por archivo .eml,
# en training/datasets/raw/personal/. Es de solo lectura: no marca como leído ni modifica el buzón.
# Requiere IMAP habilitado y una contraseña de aplicación (https://myaccount.google.com/apppasswords).
# Uso: GMAIL_APP_PASSWORD=xxxx python training/download_gmail.py --user cuenta@gmail.com [--limit 2500]
import argparse
import getpass
import imaplib
import os
import re
from pathlib import Path

from sources import RAW_DIR

IMAP_HOST = "imap.gmail.com"
# Búsqueda de Gmail aplicada sobre "Todos": se descartan spam, papelera, enviados, borradores y chats
DEFAULT_QUERY = "-in:spam -in:trash -in:sent -in:drafts -in:chats"
MAX_FILE_BYTES = 500_000  # mismo criterio que download_data.py: se omiten correos gigantes
BATCH_SIZE = 100

MSGID_RE = re.compile(rb"X-GM-MSGID (\d+)")
UID_RE = re.compile(rb"UID (\d+)")
SIZE_RE = re.compile(rb"RFC822\.SIZE (\d+)")


def all_mail_folder(conn) -> str:
    """Nombre de la carpeta "Todos" (depende del idioma de la cuenta), identificada por el flag \\All."""
    _, folders = conn.list()
    for line in folders:
        if b"\\All" in line:
            return line.decode().rsplit(' "/" ', 1)[-1]
    raise RuntimeError("No se encontró la carpeta 'Todos' (\\All). ¿Está visible en IMAP?")


def batches(items, size):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def select_uids(conn, query, limit, max_bytes):
    """UIDs de los `limit` correos más recientes que cumplen la búsqueda y el tamaño máximo."""
    _, data = conn.uid("SEARCH", "X-GM-RAW", f'"{query}"')
    uids = data[0].split()
    print(f"Coinciden con la búsqueda: {len(uids)}")
    selected = []
    skipped = 0
    # Se recorre de más reciente a más antiguo hasta completar el límite
    for chunk in batches(uids[::-1], BATCH_SIZE * 5):
        _, data = conn.uid("FETCH", b",".join(chunk), "(RFC822.SIZE)")
        sizes = {}
        for line in data:
            if isinstance(line, bytes) and (uid := UID_RE.search(line)) and (size := SIZE_RE.search(line)):
                sizes[uid.group(1)] = int(size.group(1))
        for uid in chunk:
            if sizes.get(uid, 0) > max_bytes:
                skipped += 1
                continue
            selected.append(uid)
            if len(selected) == limit:
                print(f"Omitidos por tamaño: {skipped}")
                return selected
    print(f"Omitidos por tamaño: {skipped}")
    return selected


def download(conn, uids, destination):
    destination.mkdir(parents=True, exist_ok=True)
    saved = existing = 0
    for chunk in batches(uids, BATCH_SIZE):
        # BODY.PEEK[] devuelve el mensaje original sin marcarlo como leído
        _, data = conn.uid("FETCH", b",".join(chunk), "(X-GM-MSGID BODY.PEEK[])")
        for item in data:
            if not isinstance(item, tuple):
                continue
            msgid = MSGID_RE.search(item[0])
            if not msgid:
                continue
            path = destination / f"gmail-{msgid.group(1).decode()}.eml"
            if path.exists():
                existing += 1
                continue
            partial = path.with_suffix(".eml.part")
            partial.write_bytes(item[1])
            partial.rename(path)
            saved += 1
        print(f"  {saved + existing}/{len(uids)}")
    print(f"Guardados: {saved} | ya existían: {existing} | carpeta: {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", required=True, help="Cuenta de Gmail")
    parser.add_argument("--limit", type=int, default=2500, help="Número de correos a descargar")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Búsqueda de Gmail para filtrar")
    parser.add_argument("--max-bytes", type=int, default=MAX_FILE_BYTES)
    parser.add_argument("--out", default=str(RAW_DIR / "personal"))
    args = parser.parse_args()

    password = os.environ.get("GMAIL_APP_PASSWORD") or getpass.getpass("Contraseña de aplicación: ")
    conn = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        conn.login(args.user, password.replace(" ", ""))
        folder = all_mail_folder(conn)
        conn.select(folder, readonly=True)
        print(f"Carpeta: {folder}")
        uids = select_uids(conn, args.query, args.limit, args.max_bytes)
        download(conn, uids, Path(args.out))
    finally:
        try:
            conn.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
