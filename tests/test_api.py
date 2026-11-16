# test_api.py
# Pruebas de los endpoints de la API con el modelo entrenado (backend/app/models/).
import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main

EML_DIR = Path(__file__).resolve().parent / "eml_files"
# Los correos de ejemplo son locales (no se versionan): las pruebas que los usan se omiten si faltan
needs_samples = pytest.mark.skipif(
    not all((EML_DIR / name).exists() for name in ("t1.eml", "t2.eml", "t3_p.eml", "t4_p.eml", "mails.zip")),
    reason="correos de ejemplo locales no disponibles en tests/eml_files/")


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def upload(client, endpoint, name, content):
    return client.post(f"/{endpoint}", files={"file": (name, content)})


def make_zip(files: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def test_health_reports_model(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert 0 < body["threshold"] < 1
    assert body["metrics_test"]["f1"] > 0.9
    assert len(body["features"]) == 22


@needs_samples
@pytest.mark.parametrize("name, expected", [
    ("t1.eml", "legitimo"), ("t2.eml", "legitimo"), ("t3_p.eml", "phishing"), ("t4_p.eml", "phishing"),
])
def test_single_classifies_sample_emails(client, name, expected):
    response = upload(client, "evaluate-single", name, (EML_DIR / name).read_bytes())
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == expected
    assert 0 <= body["score"] <= 1
    assert len(body["features"]) == 28
    assert isinstance(body["reasons"], list)


@needs_samples
def test_phishing_sample_has_reasons(client):
    body = upload(client, "evaluate-single", "t3_p.eml", (EML_DIR / "t3_p.eml").read_bytes()).json()
    assert any("acortadores" in reason for reason in body["reasons"])


@needs_samples
def test_single_is_deterministic(client):
    raw = (EML_DIR / "t2.eml").read_bytes()
    first = upload(client, "evaluate-single", "t2.eml", raw).json()["score"]
    assert upload(client, "evaluate-single", "t2.eml", raw).json()["score"] == first


def test_single_handles_garbage_content(client):
    response = upload(client, "evaluate-single", "roto.eml", b"\x00\xff no es un correo")
    assert response.status_code == 200


@pytest.mark.parametrize("name, content, status", [
    ("correo.txt", b"hola", 400),
    ("vacio.eml", b"", 400),
])
def test_single_rejects_invalid_uploads(client, name, content, status):
    assert upload(client, "evaluate-single", name, content).status_code == status


def test_single_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_EML_BYTES", 100)
    assert upload(client, "evaluate-single", "grande.eml", b"x" * 200).status_code == 413


@needs_samples
def test_batch_with_sample_zip(client):
    response = upload(client, "evaluate-batch", "mails.zip", (EML_DIR / "mails.zip").read_bytes())
    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {**body["summary"], "total": 4, "phishing": 2, "legitimos": 2, "errores": 0}
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)


@needs_samples
def test_batch_ignores_non_eml_and_macos_metadata(client):
    content = make_zip({
        "a/t3_p.eml": (EML_DIR / "t3_p.eml").read_bytes(),
        "__MACOSX/a/._t3_p.eml": b"basura",
        "notas.txt": b"hola",
    })
    body = upload(client, "evaluate-batch", "lote.zip", content).json()
    assert body["summary"]["total"] == 1
    assert body["results"][0]["filename"] == "t3_p.eml"


@pytest.mark.parametrize("content, status", [
    (b"esto no es un zip", 400),
    (make_zip({"notas.txt": b"hola"}), 400),
])
def test_batch_rejects_invalid_zip(client, content, status):
    assert upload(client, "evaluate-batch", "lote.zip", content).status_code == status


def test_batch_rejects_too_many_files(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_ZIP_FILES", 2)
    content = make_zip({f"{i}.eml": b"From: a@b.com\r\n\r\nhola" for i in range(3)})
    assert upload(client, "evaluate-batch", "lote.zip", content).status_code == 413


def test_batch_rejects_wrong_extension(client):
    assert upload(client, "evaluate-batch", "lote.rar", b"x").status_code == 400
