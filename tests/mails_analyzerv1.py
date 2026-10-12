import re
from email import policy
from email.parser import BytesParser
from urllib.parse import urlparse

def analyze_eml_links(eml_path):
    # 1. Leer y analizar el archivo .eml
    with open(eml_path, "rb") as file_handle:
        msg = BytesParser(policy=policy.default).parse(file_handle)

    # 2. Obtener el remitente y extraer su dominio principal
    sender = msg["from"] or ""
    sender_domain = ""
    if "@" in sender:
        # Extrae lo que está después de la '@' (ej: 'soporte@paypal.com' -> 'paypal.com')
        sender_domain = sender.split("@")[-1].strip(" <>").lower()

    # 3. Buscar enlaces en el cuerpo del correo (HTML o Texto Plano)
    html_body = ""
    text_body = ""

    # Extraer las partes del contenido que estén disponibles
    html_part = msg.get_body(preferencelist=("html",))
    text_part = msg.get_body(preferencelist=("plain",))

    if html_part:
        html_body = html_part.get_content()
    if text_part:
        text_body = text_part.get_content()

    # Expresión regular para capturar URLs que empiecen con http o https
    url_regex = r"https?://[^\s\"'>]+"
    found_links = re.findall(url_regex, text_body + html_body)

    # Eliminar enlaces duplicados manteniendo el orden original
    unique_links = list(dict.fromkeys(found_links))

    # 4. Mostrar el reporte de resultados en consola
    print(f"=== ANÁLISIS DE ENLACES PARA: {msg['subject']} ===")
    print(f"Remitente: {sender}")
    print(f"Dominio del Remitente: {sender_domain}")
    print(f"Enlaces únicos encontrados: {len(unique_links)}\n")

    if len(unique_links) > 0:
        print("Detalle de enlaces encontrados:")
        for url in unique_links:
            # Extraer el dominio del enlace de destino
            link_domain = urlparse(url).netloc.lower()

            # Alerta si el dominio del enlace no coincide con el dominio del remitente
            is_suspicious = (
                sender_domain not in link_domain if sender_domain else False
            )
            alert_status = (
                "⚠️ [SOSPECHOSO - No coincide]" if is_suspicious else "✅ [Coincide]"
            )

            print(f"- URL: {url}")
            print(f"  Dominio de Destino: {link_domain} {alert_status}\n")
    else:
        print("No se encontraron enlaces en el cuerpo del correo.")


# --- Ejemplo de uso ---
analyze_eml_links("/home/migue/Documents/UNIVERSITY/EighthSemester/PTIA/Project/PTIA_PROJECT/tests/eml_files/t2.eml")
