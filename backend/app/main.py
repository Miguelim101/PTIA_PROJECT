# main.py
import io
import random
import time
import zipfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.extractor import extract_email_features

app = FastAPI(title="SIDP - Backend temporal")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

THRESHOLD = 0.5


def mock_score() -> float:
    # TODO: reemplazar por scaler + log1p + modelo .h5
    return round(random.uniform(0, 1), 4)


def analyze(raw: bytes, name: str) -> dict:
    score = mock_score()
    return {
        "filename": name,
        "score": score,
        "label": "phishing" if score >= THRESHOLD else "legitimo",
        "features": extract_email_features(raw),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/evaluate-single")
async def evaluate_single(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".eml"):
        raise HTTPException(400, "Se requiere un archivo .eml")
    t0 = time.perf_counter()
    raw = await file.read()
    try:
        result = analyze(raw, file.filename)
    except Exception as e:
        raise HTTPException(422, f"No se pudo procesar el correo: {e}")
    result["time_s"] = round(time.perf_counter() - t0, 2)
    return result


@app.post("/evaluate-batch")
async def evaluate_batch(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(400, "Se requiere un archivo .zip")
    t0 = time.perf_counter()
    raw = await file.read()
    results, errors = [], []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                n = info.filename
                if info.is_dir() or "__MACOSX" in n or not n.lower().endswith(".eml"):
                    continue
                try:
                    results.append(analyze(zf.read(info), n.split("/")[-1]))
                except Exception as e:
                    errors.append({"filename": n, "error": str(e)})
    except zipfile.BadZipFile:
        raise HTTPException(400, "ZIP inválido o corrupto")
    if not results and not errors:
        raise HTTPException(400, "El ZIP no contiene archivos .eml")

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