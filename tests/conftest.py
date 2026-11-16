# conftest.py
# Permite importar el backend como en el contenedor: from app.extractor import ...
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
