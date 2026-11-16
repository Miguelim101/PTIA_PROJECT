# SIDP: Sistema de Identificación de Phishing con Redes Neuronales

Este repositorio contiene el código fuente, los scripts de entrenamiento y la arquitectura de despliegue del **Detector de Phishing**, un proyecto desarrollado para la asignatura Principios de Inteligencia Artificial (PTIA).

## Contexto del Proyecto

El phishing es una técnica de ciberdelincuencia diseñada para robar información sensible engañando al usuario. Tradicionalmente, los servidores de correo usan "listas negras" o reglas estáticas para bloquear estos ataques, pero son ineficaces ante amenazas nuevas.

Este proyecto resuelve ese problema implementando un modelo de **Inteligencia Artificial (Red Neuronal Artificial)**. En lugar de interpretar el contenido con IA generativa (pesada y costosa), nuestro sistema analiza la **estructura técnica del correo** (cabeceras de autenticación, enlaces, adjuntos, HTML) y unas pocas señales léxicas (palabras de urgencia, saludos genéricos, solicitudes de datos sensibles) de manera instantánea y privada, extrayendo características numéricas que delatan el fraude.


El sistema (SIDP) clasifica correos electrónicos crudos (`.eml`) como legítimos o maliciosos (*phishing*) utilizando un enfoque puramente predictivo que combina **Feature Engineering estructurado** y **Deep Learning**, sin depender de APIs de Inteligencia Artificial generativa externas.

---

## Arquitectura del Sistema

El flujo de trabajo se basa en un *pipeline* determinista que transforma la estructura de un correo electrónico en un vector numérico evaluable por una Red Neuronal Artificial (Perceptrón Multicapa - MLP).

El procesamiento sigue un flujo estrictamente secuencial de 4 fases:

1.  **Extracción Nativa:** Análisis léxico y estructural del archivo `.eml` localmente usando librerías nativas para generar 28 características (ej. conteo de URLs, enlaces engañosos, adjuntos riesgosos, discrepancias de dominios). El modelo usa 22: `num_received_hops` se descartó porque la auditoría del dataset mostró que depende del servidor que recibió el correo y no del remitente (`training/reports/audit.md`), y otras cinco (`num_link_mismatch`, `is_html`, `has_auth_results`, `exclamation_count` y `from_replyto_mismatch`) porque no distinguían las clases y quitarlas mejoró el modelo en validación. La interfaz las sigue mostrando.
2.  **Tratamiento de Cabeceras:** Asignación de valores neutros (0) ante la ausencia de metadatos (ej. encabezados `Authentication-Results` faltantes). El extractor nunca lanza excepciones: una parte ilegible solo deja en 0 la característica afectada.
3.  **Suavizado Numérico:** Aplicación de `log1p` ($\ln(x + 1)$) a los conteos con variaciones extremas (como la longitud del cuerpo o las URLs).
4.  **Estandarización e Inferencia:** Escalado del vector con el `StandardScaler` ajustado en el entrenamiento y paso por el MLP (22 $\rightarrow$ 64 $\rightarrow$ 32 $\rightarrow$ 1, con Dropout y regularización L2), que retorna un score de riesgo entre 0 y 1 (salida sigmoide). El correo se clasifica como phishing cuando el score llega a 0,5.

### Resultados del modelo

Evaluación en el conjunto de prueba (487 correos de remitentes que el modelo no vio en el entrenamiento):

| | Exactitud | Precisión | Recall | F1 | AUC |
|---|---|---|---|---|---|
| Modelo entregado (partición oficial) | 94,7 % | 96,3 % | 93,2 % | 0,947 | 0,979 |
| Media de 5 particiones distintas | 94,7 % ± 0,6 % | 95,9 % ± 0,6 % | 93,6 % ± 0,7 % | 0,947 ± 0,006 | 0,987 ± 0,005 |

Detalle, curvas y errores en `training/reports/training.md` y `training/reports/robustness.md`.

---

## Tecnologías Utilizadas

*   **Feature Engineering:** Python 3 (librerías `email`, `re`, `urllib.parse`), `BeautifulSoup4` (para parseo DOM/HTML).
*   **Machine Learning / Deep Learning:** `TensorFlow/Keras` (modelado de la red neuronal), `scikit-learn` (escalado, partición estratificada y modelos de referencia), `numpy`.
*   **Backend (API Rest):** `FastAPI`, `Uvicorn` (asíncrono).
*   **Frontend:** Interfaz de usuario en HTML5/CSS3/JavaScript, servida por Nginx.
*   **DevOps y Despliegue:** `Docker`, `Docker Compose`, `Nginx` (servidor proxy estático).

---

## Estructura del Monorepo

El proyecto está diseñado bajo una arquitectura de microservicios aislados:

```text
PTIA_PROJECT/
├── backend/                     # Microservicio de procesamiento y API
│   ├── app/
│   │   ├── main.py              # Endpoints de FastAPI (/evaluate-single, /evaluate-batch y /health)
│   │   ├── extractor.py         # Extractor MIME de las 28 features (el modelo usa 22)
│   │   └── models/              # phishing_model.keras, scaler.pkl y model_meta.json (generados por train_ann.py)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                    # Interfaz de usuario (SIDP)
│   ├── src/index.html
│   ├── nginx.conf
│   └── Dockerfile
├── training/                    # Datos y entrenamiento (no se despliega)
│   ├── sources.py               # Catálogo de fuentes de correos
│   ├── download_data.py         # Descarga el phishing público (Nazario y phishing_pot)
│   ├── download_gmail.py        # Descarga correos legítimos de Gmail por IMAP
│   ├── data_sources.py          # Lectura de carpetas .eml y archivos .mbox
│   ├── phishing_quality.py      # Filtro de calidad del phishing
│   ├── build_corpus.py          # Curado y balanceo del corpus
│   ├── generate_dataset.py      # Corpus -> dataset.csv (28 características + partición)
│   ├── audit_dataset.py         # Auditoría de fuga y sesgo -> reports/
│   ├── preprocessing.py         # Carga del dataset, log1p y métricas comunes
│   ├── train_baseline.py        # Regresión logística y Random Forest (referencia)
│   ├── train_ann.py             # Entrenamiento del MLP y exportación a backend/app/models/
│   ├── evaluate_splits.py       # Robustez: métricas con 5 particiones distintas
│   ├── requirements.txt         # Dependencias de datos y entrenamiento
│   ├── reports/                 # Reportes versionados (auditoría, entrenamiento, robustez y gráficas)
│   └── datasets/                # Fuera de git, salvo sources/ y corpus_report.md
│       ├── raw/                 # Correos crudos por fuente (nazario, phishing_pot, personal, grupo)
│       ├── curated/             # Corpus final: phishing/ y legitimate/
│       ├── manifest.csv         # Un registro por correo curado
│       ├── corpus_report.md     # Estadísticas del corpus
│       └── sources/             # Lista versionada de archivos de phishing_pot
├── tests/                       # Pruebas con pytest (test_extractor.py, test_api.py)
│   └── eml_files/               # Correos de ejemplo locales (ignorados por git)
├── docker-compose.yml
└── .gitignore
```

---

## Modalidades de Uso

El frontend del SIDP ofrece dos vías de interacción directa y privada:

1.  **Análisis Singular:** 
    *   Diseñado para la verificación de un correo específico.
    *   El usuario carga/arrastra un único archivo `.eml`.
    *   El sistema responde en centésimas de segundo con la clasificación, el score de riesgo frente al umbral de decisión, los indicadores de riesgo encontrados (p. ej. "Usa acortadores de enlaces") y las 28 características extraídas.
2.  **Análisis Masivo (Por Lotes):**
    *   Diseñado para procesar datasets completos de prueba o bandejas de entrada corporativas.
    *   El usuario carga un archivo comprimido `.zip` conteniendo múltiples `.eml`.
    *   El backend descomprime y extrae las características en memoria, evalúa todos los correos en una sola pasada del modelo y devuelve el resumen (phishing, legítimos y errores), las alertas ordenadas por score y la descarga de un `.csv` con el resultado etiquetado.
    *   Límites: 10 MB por `.eml`, 50 MB por `.zip` y 2.000 correos por lote.

Los correos se procesan solo en memoria: no se guardan en disco, no se registran en los logs y no se envían a servicios externos.

---

## Guía rápida: comandos y configuración

Todos los comandos se ejecutan desde la raíz del repositorio (`PTIA_PROJECT/`).

### 1. Levantar y bajar la aplicación (Docker)

| Acción | Comando |
|---|---|
| Construir y levantar (frontend en `http://localhost`, API en `http://localhost:8000/docs`) | `docker compose up --build -d` |
| Ver el estado de los contenedores (el backend debe quedar `healthy`) | `docker compose ps` |
| Ver los logs del backend en vivo | `docker compose logs -f backend` |
| Comprobar que la API responde y qué modelo cargó | `curl http://localhost:8000/health` |
| Detener y eliminar los contenedores | `docker compose down` |
| Aplicar un modelo recién entrenado (el modelo se copia dentro de la imagen) | `docker compose up --build -d backend` |

### 2. Preparar el entorno de entrenamiento (una sola vez)

Requiere Python 3.12 (TensorFlow aún no tiene versión estable para Python 3.14).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r training/requirements.txt
```

En cada terminal nueva basta con `source .venv/bin/activate`.

### 3. Entrenar el modelo

Pasos en orden. Los pasos 1 y 2 solo se repiten si cambian los correos; si solo se quieren probar otros hiperparámetros, basta con los pasos 6 y 7.

```bash
# 1. Descargar el phishing público (Nazario y phishing_pot, ~1,6 GB)
python training/download_data.py

# 2. Descargar correos legítimos de Gmail (requiere una contraseña de aplicación de Google)
GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx' python training/download_gmail.py --user cuenta@gmail.com --limit 2500
#    Correos de otros integrantes: agregar --out training/datasets/raw/grupo/<nombre>

# 3. Curar y balancear el corpus (2.500 por clase)
python training/build_corpus.py

# 4. Extraer las características y crear la partición 80/10/10
python training/generate_dataset.py

# 5. Auditar fugas y sesgos (opcional, recomendado si cambian los datos)
python training/audit_dataset.py

# 6. Líneas base de comparación (opcional)
python training/train_baseline.py

# 7. Entrenar el MLP y exportarlo a backend/app/models/
python training/train_ann.py --note "descripción del cambio"

# 8. Medir la robustez con 5 particiones distintas (mismos parámetros que el paso 7)
python training/evaluate_splits.py

# 9. Verificar con las pruebas y aplicar el modelo en Docker
python -m pytest -q tests
docker compose up --build -d backend
```

Cada script escribe su reporte en `training/reports/` (`audit.md`, `baseline.md`, `training.md`, `robustness.md`) y cada entrenamiento agrega una fila a `training/reports/experiments.csv`.

### 4. Parámetros del modelo

Se pasan como argumentos a `train_ann.py` y, con los mismos nombres, a `evaluate_splits.py`. Los valores por defecto son los del modelo entregado, elegidos solo con el conjunto de validación.

| Parámetro | Por defecto | Qué controla |
|---|---|---|
| `--hidden` | `64 32` | Neuronas de cada capa oculta. `--hidden 128 64 32` agrega una tercera capa |
| `--dropout` | `0.3` | Fracción de neuronas que se apagan al entrenar. Más alto = menos sobreajuste |
| `--l2` | `0.01` | Regularización L2 de las capas ocultas. `0` la desactiva |
| `--lr` | `0.001` | Tasa de aprendizaje del optimizador Adam |
| `--batch-size` | `128` | Correos por lote de entrenamiento |
| `--epochs` | `300` | Máximo de épocas |
| `--patience` | `25` | Épocas sin mejorar la pérdida de validación antes de detenerse (EarlyStopping); se conservan los mejores pesos |
| `--threshold` | `0.5` | Score desde el cual un correo se clasifica como phishing. Se guarda en `model_meta.json` y la API y la interfaz lo leen de ahí |
| `--note` | (vacío) | Texto que se guarda en `experiments.csv` para identificar el experimento |

Ejemplo de experimento:

```bash
python training/train_ann.py --lr 0.0005 --dropout 0.5 --note "lr 0.0005 y dropout 0.5"
python training/evaluate_splits.py --lr 0.0005 --dropout 0.5
```

`train_ann.py` reemplaza el modelo de `backend/app/models/`. Para comparar experimentos, use las métricas de validación de `training.md` y la media de `robustness.md`; el conjunto de prueba no debe usarse para elegir entre configuraciones. Para volver al modelo entregado, ejecute `python training/train_ann.py` sin argumentos: el entrenamiento es determinista y lo reproduce exactamente.

### 5. Parámetros del corpus (`build_corpus.py`)

| Parámetro | Por defecto | Qué controla |
|---|---|---|
| `--phishing` | `2500` | Correos de phishing a seleccionar |
| `--legitimate` | `2500` | Correos legítimos a seleccionar |
| `--campaign-cap` | `2` | Máximo de correos por campaña (asunto normalizado + dominio remitente) |
| `--sender-cap` | `15` | Máximo de correos de phishing por dominio remitente |
| `--legit-sender-cap` | `60` | Máximo de correos legítimos por dominio remitente |

Después de cambiar el corpus hay que repetir desde el paso 4 de la sección 3.

### 6. Otros ajustes (en el código)

| Qué | Dónde |
|---|---|
| Características que el modelo no usa | `EXCLUDED_FROM_MODEL` en `backend/app/extractor.py` (luego, pasos 4 a 9) |
| Vocabulario de urgencia, datos sensibles y saludos genéricos | `URGENCY_WORDS`, `SENSITIVE_WORDS` y `GENERIC_GREETINGS` en `backend/app/extractor.py` (luego, pasos 4 a 9) |
| Fuentes de datos y su peso en cada clase | `SOURCES` en `training/sources.py` |
| Filtro de calidad del phishing | `training/phishing_quality.py` |
| Límites de carga de la API (10 MB por `.eml`, 50 MB y 2.000 correos por `.zip`) | `MAX_EML_BYTES`, `MAX_ZIP_BYTES` y `MAX_ZIP_FILES` en `backend/app/main.py`; si se sube el límite del `.zip`, también `client_max_body_size` en `frontend/nginx.conf` |
| Puertos publicados (80 y 8000) | `ports` en `docker-compose.yml` |
| Semilla aleatoria (reproducibilidad) | `SEED` en `training/preprocessing.py`, `training/generate_dataset.py` y `training/build_corpus.py` |

---

## Instrucciones de Ejecución (Despliegue con Docker)

El proyecto está listo para ejecutarse en cualquier entorno mediante Docker. No es necesario instalar Python, TensorFlow ni otras dependencias a nivel de sistema operativo.

### Prerrequisitos
*   [Docker](https://docs.docker.com/get-docker/) instalado.
*   [Docker Compose](https://docs.docker.com/compose/install/) instalado.

### Pasos para iniciar el sistema

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/Miguelim101/PTIA_PROJECT.git
    cd PTIA_PROJECT
    ```

2.  **Puertos:** el frontend se publica en el puerto `80` y el backend en el `8000` (se cambian en `docker-compose.yml`). El modelo entrenado ya viene en `backend/app/models/`, así que no hace falta entrenar para usar la aplicación.

3.  **Construir y levantar los contenedores:**
    Abre una terminal en la raíz del proyecto (`PTIA_PROJECT/`) y ejecuta:
    ```bash
    docker compose up --build -d
    ```
    *(El parámetro `-d` levanta el servicio en segundo plano. Omítelo si deseas ver los logs en tiempo real). La primera construcción descarga TensorFlow y tarda unos minutos; la imagen del backend ocupa unos 2,4 GB.*

4.  **Acceder a la aplicación:**
    *   **Frontend (UI del SIDP):** Abre tu navegador en `http://localhost` (o el puerto configurado).

        Una vez que Docker confirme que los contenedores están corriendo, **no necesitas conocimientos técnicos ni abrir herramientas de backend** para probar la inteligencia artificial.

        1. **Abre tu navegador web** y dirígete a: `http://localhost`
        2. Verás la interfaz gráfica del Sistema de Identificación de Phishing (SIDP).
        3. **Tienes dos formas de usarlo:**
        * **Análisis Singular:** 
            1. Haz clic en la tarjeta izquierda o arrastra el archivo sobre ella.
            2. Sube un archivo de correo crudo en formato `.eml` (en Gmail: menú ⋮ del correo → "Descargar mensaje"). El análisis empieza al seleccionarlo.
            3. Verás la clasificación, el score de riesgo sobre una barra con el umbral de decisión, los indicadores encontrados y las características extraídas.
        * **Análisis Masivo (Lotes):** 
            1. Haz clic en la tarjeta derecha o arrastra el archivo sobre ella.
            2. Sube un archivo comprimido `.zip` que contenga varios archivos `.eml`.
            3. Verás el resumen del lote y las alertas prioritarias, con la opción de descargar los resultados en `.csv`.
        * Para tus pruebas puedes guardar correos propios en `tests/eml_files/`: esa carpeta es local y git la ignora, porque los correos contienen datos personales.

    *   **Backend / Documentación de API (Swagger):** Navega a `http://localhost:8000/docs` para probar los *endpoints* interactivos autogenerados por FastAPI.

5.  **Detener el sistema:**
    ```bash
    docker compose down
    ```

---

## Pruebas (Desarrollo)

Con el entorno de la sección "Guía rápida" (paso 2) activado:

```bash
python -m pytest -q tests
```

`tests/test_extractor.py` prueba cada una de las 28 características con correos sintéticos. `tests/test_api.py` prueba los endpoints con el modelo entrenado: indicadores, límites de tamaño y ZIP inválidos. Las pruebas que necesitan datos locales se omiten automáticamente si no están disponibles: las que clasifican correos reales usan `tests/eml_files/` (`t1.eml` y `t2.eml` legítimos, `t3_p.eml` y `t4_p.eml` phishing, `mails.zip` con los cuatro), y la que recorre el corpus completo usa `training/datasets/curated/`.

---

## Detalle de los pasos de entrenamiento

Qué hace cada paso de la sección "Guía rápida: comandos y configuración":

1. **`download_data.py`** descarga las fuentes públicas de phishing (Nazario 2020–2025 y phishing_pot) en `training/datasets/raw/`.
2. **`download_gmail.py`** descarga correos **legítimos** de Gmail por IMAP (solo lectura) en `training/datasets/raw/personal/`; también sirven `.mbox` de Google Takeout o `.eml` de "Descargar mensaje". Se excluyen Spam, Papelera, Enviados y Borradores, y estos correos nunca se suben a git. Los correos de los demás integrantes van en `training/datasets/raw/grupo/<nombre>/`: el corpus legítimo se reparte a partes iguales entre `personal` y `grupo`, y lo que falte en una fuente se completa con la otra.
3. **`build_corpus.py`** construye el corpus curado en `training/datasets/curated/`, con `manifest.csv` y el reporte `corpus_report.md`. El phishing pasa un filtro de calidad (`training/phishing_quality.py`): debe tener un señuelo real (credenciales, documento compartido, entrega, pago, cripto, suplantación) y un enlace o adjunto, y se descartan el spam promocional, la extorsión y los idiomas distintos de inglés, español y portugués. Además se deduplica y se limita a 2 correos por campaña y a 15 (phishing) o 60 (legítimos) por dominio remitente. Los correos de `tests/eml_files/` (sueltos o dentro de un `.zip`) se excluyen siempre, para que sigan siendo una prueba con correos que el modelo nunca vio.
4. **`generate_dataset.py`** extrae las 28 características de cada correo con el mismo extractor de la API y asigna la partición 80/10/10, estratificada y agrupada por dominio remitente (un remitente nunca queda a la vez en train y test). Resultado: `training/datasets/dataset.csv`.
5. **`audit_dataset.py`** busca fugas de información antes de entrenar: el poder de cada característica por sí sola, la dependencia de las cabeceras de infraestructura y la generalización entre fuentes de phishing. Resultado: `training/reports/audit.md` y `feature_histograms.png`.
6. **`train_baseline.py`** entrena la Regresión Logística y el Random Forest de referencia, evaluados solo en validación (`training/reports/baseline.md`).
7. **`train_ann.py`** entrena el MLP y exporta a `backend/app/models/` los artefactos que carga la API: `phishing_model.keras`, `scaler.pkl` (ajustado solo con train) y `model_meta.json` (características, umbral y métricas). Los hiperparámetros se eligieron solo con validación y el umbral de decisión es 0,5 fijo, porque la curva de F1 es plana y el umbral "óptimo" en validación cambiaba mucho entre particiones. El conjunto de prueba nunca se usa para tomar decisiones: cada ejecución lo evalúa una vez, al final. Resultado: `training/reports/training.md`, gráficas y una fila en `experiments.csv`.
8. **`evaluate_splits.py`** repite el entrenamiento con 5 particiones distintas y reporta la media y la desviación de las métricas (`training/reports/robustness.md`).
