# data_sources.py
# Lectura uniforme de correos crudos: carpetas con un correo por archivo y archivos mbox.
import mailbox
from pathlib import Path

IGNORED_FILES = {"LICENSE.txt", "README.txt"}


def strip_unix_from(raw: bytes) -> bytes:
    # Algunos .eml exportados empiezan con una línea "From usuario fecha" (separador mbox),
    # que no es una cabecera RFC 5322 y confundiría al parser
    if raw.startswith(b"From "):
        newline = raw.find(b"\n")
        return raw[newline + 1 :] if newline != -1 else b""
    return raw


def iter_mbox(path: Path):
    box = mailbox.mbox(str(path), create=False)
    try:
        for key in box.keys():
            # get_bytes devuelve el mensaje original sin la línea separadora "From "
            yield f"{path.name}#{key}", box.get_bytes(key)
    finally:
        box.close()


def iter_emails(path: Path, mbox: bool = False):
    """Entrega tuplas (referencia, bytes crudos) de un archivo mbox o de una carpeta.

    - Un archivo pasado directamente se trata como mbox.
    - Dentro de una carpeta: los .mbox (o todos, si mbox=True, p. ej. phishing-2024 de Nazario)
      se leen como mbox y el resto como un correo por archivo.
    """
    path = Path(path)
    if path.is_file():
        yield from iter_mbox(path)
        return
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        if file_path.name in IGNORED_FILES or file_path.name.startswith("."):
            continue
        if mbox or file_path.suffix.lower() == ".mbox":
            yield from iter_mbox(file_path)
        else:
            yield str(file_path.relative_to(path)), strip_unix_from(file_path.read_bytes())
