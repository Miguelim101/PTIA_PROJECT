# main.py
# API del SIDP: recibe correos .eml (uno o un .zip con varios), extrae las características, aplica
# log1p y el StandardScaler del entrenamiento, y devuelve el score de riesgo del MLP.
# Todo se procesa en memoria: los correos no se guardan en disco ni se registran en los logs.
import io
import json
import os
import time
import zipfile
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import joblib  # noqa: E402
import numpy as np  # noqa: E402
from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.extractor import extract_email_features, to_vector  # noqa: E402

MODELS_DIR = Path(__file__).resolve().parent / "models"
MAX_EML_BYTES = 10 * 1024 * 1024        # 10 MB por correo
MAX_ZIP_BYTES = 50 * 1024 * 1024        # 50 MB por archivo .zip (igual que client_max_body_size en Nginx)
MAX_ZIP_UNCOMPRESSED = 300 * 1024 * 1024
MAX_ZIP_FILES = 2000

# Indicadores legibles para el usuario. Son reglas que acompañan al score, no la explicación del modelo.
REASONS = [
    ("display_name_mismatch", "El nombre visible del remitente menciona una marca que no coincide con su dominio"),
    ("num_link_mismatch", "Hay enlaces cuyo texto muestra un dominio distinto al destino real"),
    ("url_has_at_symbol", "Hay enlaces con un dominio falso antes de '@' para ocultar el destino real"),
    ("has_ip_url", "Hay enlaces que apuntan a una dirección IP en lugar de un dominio"),
    ("risky_attachment", "Incluye adjuntos de tipo riesgoso (ejecutables, HTML, comprimidos o macros)"),
    ("has_form", "El correo contiene un formulario HTML"),
    ("url_shortener_count", "Usa acortadores de enlaces que ocultan el destino"),
    ("generic_greeting", "Usa un saludo genérico (p. ej. 'Estimado cliente')"),
    ("urgency_words", "Usa lenguaje de urgencia o amenaza (suspensión, vencimiento)"),
    ("sensitive_words", "Menciona datos sensibles (contraseñas, tarjetas, credenciales)"),
    ("from_free_domain", "El remitente usa un servicio de correo gratuito"),
]


@lru_cache(maxsize=1)
def load_artifacts():
    """Carga el modelo, el scaler y los metadatos una sola vez por proceso."""
    import keras

    meta = json.loads((MODELS_DIR / "model_meta.json").read_text(encoding="utf-8"))
    scaler = joblib.load(MODELS_DIR / "scaler.pkl")
    model = keras.models.load_model(MODELS_DIR / "phishing_model.keras", compile=False)
    return model, scaler, meta


@asynccontextmanager
async def lifespan(_app):
    load_artifacts()  # falla al arrancar si faltan artefactos, no en la primera petición
    yield


app = FastAPI(title="SIDP - Sistema de Identificación de Phishing", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def reasons_for(features: dict) -> list:
    reasons = [text for name, text in REASONS if features.get(name)]
    if features.get("has_auth_results") and not (features.get("spf_pass") or features.get("dkim_pass")):
        reasons.insert(0, "El remitente no superó la verificación SPF ni DKIM del servidor que recibió el correo")
    elif not features.get("has_auth_results"):
        reasons.append("El correo no trae resultados de autenticación (SPF/DKIM)")
    return reasons


def score_emails(items):
    """items: lista de (nombre, bytes). Extrae, escala y predice en un solo lote."""
    model, scaler, meta = load_artifacts()
    names, all_features = zip(*((name, extract_email_features(raw)) for name, raw in items))
    X = scaler.transform(np.array([to_vector(f, meta["features"]) for f in all_features], dtype=np.float32))
    scores = model(X, training=False).numpy().ravel()
    threshold = meta["threshold"]
    return [
        {
            "filename": name,
            "score": round(float(score), 4),
            "label": "phishing" if score >= threshold else "legitimo",
            "threshold": threshold,
            "reasons": reasons_for(features),
            "features": features,
        }
        for name, score, features in zip(names, scores, all_features)
    ]


async def read_upload(file: UploadFile, limit: int) -> bytes:
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(413, f"El archivo supera el límite de {limit // (1024 * 1024)} MB")
    if not raw:
        raise HTTPException(400, "El archivo está vacío")
    return raw


@app.get("/health")
def health():
    _, _, meta = load_artifacts()
    return {
        "status": "ok",
        "model": meta["architecture"],
        "threshold": meta["threshold"],
        "features": meta["features"],
        "trained_at": meta["trained_at"],
        "metrics_test": meta["metrics_test"],
    }


@app.post("/evaluate-single")
async def evaluate_single(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".eml"):
        raise HTTPException(400, "Se requiere un archivo .eml")
    t0 = time.perf_counter()
    raw = await read_upload(file, MAX_EML_BYTES)
    result = score_emails([(file.filename, raw)])[0]
    result["time_s"] = round(time.perf_counter() - t0, 2)
    return result


@app.post("/evaluate-batch")
async def evaluate_batch(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(400, "Se requiere un archivo .zip")
    t0 = time.perf_counter()
    raw = await read_upload(file, MAX_ZIP_BYTES)
    items, errors = [], []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            entries = [info for info in zf.infolist() if not info.is_dir() and "__MACOSX" not in info.filename
                       and info.filename.lower().endswith(".eml")]
            if len(entries) > MAX_ZIP_FILES:
                raise HTTPException(413, f"El ZIP tiene más de {MAX_ZIP_FILES} correos")
            if sum(info.file_size for info in entries) > MAX_ZIP_UNCOMPRESSED:
                raise HTTPException(413, "El contenido descomprimido del ZIP es demasiado grande")
            for info in entries:
                name = info.filename.split("/")[-1]
                try:
                    items.append((name, zf.read(info)))
                except Exception as error:  # entrada dañada o cifrada dentro del ZIP
                    errors.append({"filename": name, "error": str(error)})
    except zipfile.BadZipFile:
        raise HTTPException(400, "ZIP inválido o corrupto")
    if not items and not errors:
        raise HTTPException(400, "El ZIP no contiene archivos .eml")

    results = score_emails(items) if items else []
    phishing = sum(1 for r in results if r["label"] == "phishing")
    return {
        "summary": {
            "total": len(results),
            "phishing": phishing,
            "legitimos": len(results) - phishing,
            "errores": len(errors),
            "time_s": round(time.perf_counter() - t0, 2),
        },
        "results": sorted(results, key=lambda r: r["score"], reverse=True),
        "errors": errors,
    }
