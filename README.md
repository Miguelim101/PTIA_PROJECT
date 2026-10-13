# PTIA_PROJECT
Phising detection

# SIDP: Sistema de Identificación de Phishing con Redes Neuronales

Este repositorio contiene el código fuente, los scripts de entrenamiento y la arquitectura de despliegue del **Detector de Phishing**, un proyecto desarrollado para la asignatura Principios de Inteligencia Artificial (PTIA).

## Contexto del Proyecto

El phishing es una técnica de ciberdelincuencia diseñada para robar información sensible engañando al usuario. Tradicionalmente, los servidores de correo usan "listas negras" o reglas estáticas para bloquear estos ataques, pero son ineficaces ante amenazas nuevas.

Este proyecto resuelve ese problema implementando un modelo de **Inteligencia Artificial (Red Neuronal Artificial)**. En lugar de leer el texto del correo (lo cual requeriría IA generativa pesada y costosa), nuestro sistema analiza la **estructura técnica del correo** de manera instantánea y privada, extrayendo características numéricas que delatan el fraude.


El sistema (SIDP) clasifica correos electrónicos crudos (`.eml`) como legítimos o maliciosos (*phishing*) utilizando un enfoque puramente predictivo que combina **Feature Engineering estructurado** y **Deep Learning**, sin depender de APIs de Inteligencia Artificial generativa externas.

---

## Arquitectura del Sistema

El flujo de trabajo se basa en un *pipeline* determinista que transforma la estructura de un correo electrónico en un vector numérico evaluable por una Red Neuronal Artificial (Perceptrón Multicapa - MLP).

El procesamiento sigue un flujo estrictamente secuencial de 4 fases:

1.  **Extracción Nativa:** Análisis léxico y estructural del archivo `.eml` localmente usando librerías nativas para generar un vector tabular de 28 características (ej. conteo de URLs, enlaces engañosos, presencia de formularios, discrepancias de dominios).
2.  **Tratamiento de Cabeceras:** Normalización por software. Asignación de valores neutros (0) ante la ausencia de metadatos históricos (ej. encabezados `Authentication-Results` faltantes) para prevenir excepciones en ejecución.
3.  **Suavizado Numérico:** Aplicación de transformación matemática `log1p` ($\ln(x + 1)$) a variables con variaciones extremas (como la longitud del cuerpo o URLs).
4.  **Estandarización e Inferencia:** Escalado del vector mediante `StandardScaler` (comprimiendo la varianza) y paso a través del modelo MLP (arquitectura 28 $\rightarrow$ 64 $\rightarrow$ 32 $\rightarrow$ 1), que retorna un Score de Riesgo (probabilidad Sigmoid entre 0.0 y 1.0).

---

## Tecnologías Utilizadas

*   **Feature Engineering:** Python 3 (librerías `email`, `re`, `urllib.parse`), `BeautifulSoup4` (para parseo DOM/HTML).
*   **Machine Learning / Deep Learning:** `TensorFlow/Keras` (modelado de la red neuronal), `scikit-learn` (escalado y estratificación), `numpy`.
*   **Backend (API Rest):** `FastAPI`, `Uvicorn` (asíncrono).
*   **Frontend:** Interfaz de usuario renderizada en HTML5/CSS3/JS, servida de manera óptima.
*   **DevOps y Despliegue:** `Docker`, `Docker Compose`, `Nginx` (servidor proxy estático).

---

## Estructura del Monorepo

El proyecto está diseñado bajo una arquitectura de microservicios aislados:

```text
PTIA_PROJECT/
├── backend/                 # Microservicio de procesamiento y API
│   ├── app/
│   │   ├── main.py          # Endpoints de FastAPI (/evaluate-single y /evaluate-batch)
│   │   ├── extractor.py     # Script extractor MIME y preprocesamiento de las 28 features
│   │   ├── scaler.pkl       # Objeto StandardScaler ajustado en el entrenamiento
│   │   └── models/
│   │       └── phishing_model.h5  # Pesos entrenados del Perceptrón Multicapa (MLP)
│   ├── Dockerfile           # Instrucciones de contenedorización del backend
│   └── requirements.txt     # Dependencias de Python (FastAPI, TensorFlow, bs4, etc.)
├── frontend/                # Interfaz de Usuario (SIDP)
│   ├── src/                 # Archivos estáticos de la interfaz web (HTML/JS/CSS)
│   ├── nginx.conf           # Configuración del proxy web
│   └── Dockerfile           # Instrucciones de contenedorización de Nginx
├── training/                # Entorno aislado para modelado y datos (No se sube a prod)
│   ├── datasets/            # Volúmenes de datos crudos (se excluyen en .dockerignore)
│   │   ├── phishing_raw/    # Muestras .eml de Phishing (fuente: phishing_pot)
│   │   └── legitimate_raw/  # Muestras .eml de Ham (fuente: SpamAssassin)
│   ├── generate_dataset.py  # Construye el CSV iterando sobre los datasets crudos
│   └── train_ann.py         # Script de entrenamiento: ajusta la red, el scaler y exporta
├── tests/                   # Pruebas automatizadas del extractor y endpoints
├── docker-compose.yml       # Orquestador  principal de contenedores
├── .env                     # Variables de entorno (puertos, configuraciones CORS)
├── .gitignore               # Exclusión de archivos locales para el repositorio Git
└── .dockerignore            # Exclusión de carpetas pesadas (training/, tests/) para el build
```

---

## Modalidades de Uso

El frontend del SIDP ofrece dos vías de interacción directa y privada:

1.  **Análisis Singular:** 
    *   Diseñado para la verificación de un correo específico.
    *   El usuario carga/arrastra un único archivo `.eml`.
    *   El sistema responde en $\sim$0.12s con una alerta visual (Score de Riesgo) y un desglose básico de la evaluación.
2.  **Análisis Masivo (Por Lotes):**
    *   Diseñado para procesar datasets completos de prueba o bandejas de entrada corporativas.
    *   El usuario carga un archivo comprimido `.zip` conteniendo múltiples `.eml`.
    *   El backend extrae iterativamente en memoria, procesa todos los mensajes en paralelo y devuelve métricas consolidadas (Phishing vs Legítimos), habilitando la descarga de un `.csv` con la matriz etiquetada resultante.

---

## Instrucciones de Ejecución (Despliegue con Docker)

El proyecto está listo para ejecutarse en cualquier entorno mediante Docker. No es necesario instalar Python, TensorFlow ni otras dependencias a nivel de sistema operativo.

### Prerrequisitos
*   [Docker](https://docs.docker.com/get-docker/) instalado.
*   [Docker Compose](https://docs.docker.com/compose/install/) instalado.

### Pasos para iniciar el sistema

1.  **Clonar el repositorio:**
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd PTIA_PROJECT
    ```

2.  **Configurar Variables de Entorno:**
    *   Crea un archivo `.env` en la raíz (si no existe) basado en un `.env.example` o configura el puerto deseado. Por defecto, el orquestador mapeará el frontend al puerto `80` y el backend al `8000`.

3.  **Construir y levantar los contenedores:**
    Abre una terminal en la raíz del proyecto (`PTIA_PROJECT/`) y ejecuta:
    ```bash
    docker compose up --build -d
    ```
    *(El parámetro `-d` levanta el servicio en segundo plano. Omítelo si deseas ver los logs en tiempo real).*

4.  **Acceder a la aplicación:**
    *   **Frontend (UI del SIDP):** Abre tu navegador en `http://localhost` (o el puerto configurado).

        Una vez que Docker confirme que los contenedores están corriendo, **no necesitas conocimientos técnicos ni abrir herramientas de backend** para probar la inteligencia artificial.

        1. **Abre tu navegador web** y dirígete a: `http://localhost`
        2. Verás la interfaz gráfica del Sistema de Identificación de Phishing (SIDP).
        3. **Tienes dos formas de usarlo:**
        * **Análisis Singular:** 
            1. Haz clic en "Seleccionar Archivo" en la tarjeta izquierda.
            2. Sube un archivo de correo crudo en formato `.eml` (puedes descargar uno real desde Gmail seleccionando "Descargar mensaje").
            3. Haz clic en "Procesar Archivo". Verás cómo la interfaz muestra el *Score de Riesgo* y te alerta visualmente si es phishing o legítimo.
        * **Análisis Masivo (Lotes):** 
            1. Haz clic en la tarjeta derecha.
            2. Sube un archivo comprimido `.zip` que contenga varios archivos `.eml`.
            3. El sistema procesará todos a la vez y te entregará un resumen detallado con la opción de descargar los resultados en Excel/CSV.

    *   **Backend / Documentación de API (Swagger):** Navega a `http://localhost:8000/docs` para probar los *endpoints* interactivos autogenerados por FastAPI.

5.  **Detener el sistema:**
    ```bash
    docker compose down
    ```

---

## Retraining (Opcional - Desarrollo)

Si deseas reentrenar el modelo con nuevos datos:
1. Navega al directorio `training/`.
2. Alimenta las carpetas `datasets/phishing_raw/` y `datasets/legitimate_raw/` con tus archivos `.eml`.
3. Ejecuta `python generate_dataset.py` para generar el vector tabular `.csv`.
4. Ejecuta `python train_ann.py` para ajustar los pesos del MLP.
5. Traslada los archivos generados (`phishing_model.h5` y `scaler.pkl`) a la carpeta `backend/app/` y en producción a `backend/app/models/`. Reinicia los contenedores.