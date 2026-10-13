# extractor.py

import re
from email import policy
from email.parser import BytesParser
from urllib.parse import urlparse
from bs4 import BeautifulSoup  # Requiere: pip install beautifulsoup4
import json

def extract_email_features(eml_source):
    # Acepta ruta (str/Path) o bytes en memoria
    if isinstance(eml_source, (bytes, bytearray)):
        msg = BytesParser(policy=policy.default).parsebytes(bytes(eml_source))
    else:
        with open(eml_source, "rb") as file_handle:
            msg = BytesParser(policy=policy.default).parse(file_handle)

    # Variables de soporte para el cuerpo del mensaje
    html_content = ""
    text_content = ""
    is_html = 0

    # Extraer contenido plano e HTML si existen
    html_part = msg.get_body(preferencelist=("html",))
    text_part = msg.get_body(preferencelist=("plain",))

    if html_part:
        html_content = html_part.get_content()
        is_html = 1
    if text_part:
        text_content = text_part.get_content()

    # Combinar texto completo para análisis semánticos y cuantitativos
    full_body_text = text_content or ""
    soup = None
    if html_content:
        soup = BeautifulSoup(html_content, "html.parser")
        if not full_body_text:
            full_body_text = soup.get_text()

    # --- EXTRACCIÓN DE URLS Y DOMINIOS ---
    # Recolectar URLs tanto del texto plano como de los atributos href de HTML
    urls = re.findall(r"https?://[^\s\"'>]+", text_content + html_content)
    if soup:
        for anchor in soup.find_all("a", href=True):
            urls.append(anchor["href"])
    urls = list(set(urls))  # Eliminar duplicados para ciertas métricas globales

    num_urls = len(urls)

    # Comprobar si alguna URL utiliza una dirección IP en lugar de un dominio
    ip_pattern = r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    has_ip_url = 1 if any(re.match(ip_pattern, url) for url in urls) else 0

    max_url_length = max([len(url) for url in urls]) if urls else 0

    # Extraer dominios únicos de las URLs
    domains = [urlparse(url).netloc.lower() for url in urls if urlparse(url).netloc]
    num_distinct_domains = len(set(domains))

    # Detectar enlaces engañosos (Mismatches: Texto visible vs Destino real)
    num_link_mismatch = 0
    if soup:
        for anchor in soup.find_all("a", href=True):
            link_text = anchor.get_text().strip()
            link_href = anchor["href"]
            # Si el texto visible simula ser una URL pero el href va a otro sitio
            if (
                re.match(r"https?://", link_text)
                and urlparse(link_text).netloc != urlparse(link_href).netloc
            ):
                num_link_mismatch += 1

    # --- CARACTERÍSTICAS ESTRUCTURALES HTML Y ADJUNTOS ---
    has_form = 1 if (soup and soup.find("form")) else 0
    image_count = len(soup.find_all("img")) if soup else 0

    # Procesar archivos adjuntos
    num_attachments = 0
    risky_attachment = 0
    risky_extensions = (
        ".exe",
        ".scr",
        ".zip",
        ".rar",
        ".bat",
        ".vbs",
        ".js",
        ".docm",
        ".xlsm",
    )

    for part in msg.iter_attachments():
        num_attachments += 1
        filename = part.get_filename()
        if filename and filename.lower().endswith(risky_extensions):
            risky_attachment = 1

    # --- ANÁLISIS TEXTUAL Y LINGÜÍSTICO ---
    # Listas básicas de palabras clave (pueden expandirse)
    urgency_keywords = [
        "urgente",
        "inmediato",
        "cuenta suspendida",
        "bloqueo",
        "expira",
        "urgency",
        "suspend",
    ]
    sensitive_keywords = [
        "contraseña",
        "password",
        "credenciales",
        "token",
        "verificar cuenta",
        "tarjeta",
        "cedula",
    ]

    urgency_words = sum(
        1 for word in urgency_keywords if word in full_body_text.lower()
    )
    sensitive_words = sum(
        1 for word in sensitive_keywords if word in full_body_text.lower()
    )

    # Validar saludos genéricos comunes en phishing
    generic_greetings = [
        "estimado cliente",
        "querido usuario",
        "dear customer",
        "dear user",
        "apreciado usuario",
    ]
    generic_greeting = (
        1
        if any(greeting in full_body_text.lower() for greeting in generic_greetings)
        else 0
    )

    # Métricas cuantitativas del cuerpo
    body_length = len(full_body_text)
    exclamation_count = full_body_text.count("!")

    uppercase_ratio = 0.0
    digits_ratio = 0.0
    if body_length > 0:
        uppercase_ratio = (
            sum(1 for c in full_body_text if c.isupper()) / body_length
        )
        digits_ratio = sum(1 for c in full_body_text if c.isdigit()) / body_length

    # Métricas del asunto
    subject_text = msg["subject"] or ""

    # --- ANÁLISIS DE ENCABEZADOS Y REMITENTE ---
    # Comparación de From vs Reply-To
    from_header = msg["from"] or ""
    reply_to_header = msg["reply-to"] or ""
    from_replyto_mismatch = 0
    if "@" in from_header and "@" in reply_to_header:
        from_domain = from_header.split("@")[-1].strip(" <>").lower()
        reply_domain = reply_to_header.split("@")[-1].strip(" <>").lower()
        if from_domain != reply_domain:
            from_replyto_mismatch = 1

    # Verificar si el remitente proviene de servicios de correo gratuitos
    free_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com"]
    from_free_domain = 0
    if "@" in from_header:
        current_from_domain = from_header.split("@")[-1].strip(" <>").lower()
        if current_from_domain in free_domains:
            from_free_domain = 1

    # Mismatch de Nombre Visible (ej: "PayPal Security <fraude@Xyz.com>")
    display_name_mismatch = 0
    if "<" in from_header:
        display_name = from_header.split("<")[0].lower()
        actual_email_domain = from_header.split("@")[-1].strip(" <>").lower()
        # Alerta si el nombre visible finge contener un dominio de marca que no posee el correo real
        if "paypal" in display_name and "paypal.com" not in actual_email_domain:
            display_name_mismatch = 1
        if "microsoft" in display_name and "microsoft.com" not in actual_email_domain:
            display_name_mismatch = 1

    # Contar saltos de red (Hops) basados en los encabezados 'Received'
    num_received_hops = len(msg.get_all("received") or [])

    # Evaluar parámetros de seguridad de autenticación (Authentication-Results)
    auth_header = msg["authentication-results"] or ""
    has_auth_results = 1 if auth_header else 0
    spf_pass = 1 if "spf=pass" in auth_header.lower() else 0
    dkim_pass = 1 if "dkim=pass" in auth_header.lower() else 0

    # --- ANÁLISIS AVANZADO DE URLS ---
    shorteners = ["bit.ly", "goo.gl", "tinyurl.com", "t.co", "is.gd"]
    url_shortener_count = 0
    url_has_at_symbol = 0
    non_https_count = 0
    max_subdomains = 0

    for url in urls:
        parsed_url = urlparse(url)
        netloc = parsed_url.netloc.lower()

        # Contar acortadores
        if any(shortener in netloc for shortener in shorteners):
            url_shortener_count += 1

        # Buscar el símbolo @ en la URL (usado para ocultar el verdadero destino)
        if "@" in url:
            url_has_at_symbol = 1

        # Contar protocolos inseguros (http)
        if parsed_url.scheme == "http":
            non_https_count += 1

        # Calcular subdominios (ej: ://dominio.com -> 3 partes en el host)
        subdomain_parts = netloc.split(".")
        if len(subdomain_parts) > 2:
            # Descontamos el dominio principal y el TLD (ej: 'com')
            count = len(subdomain_parts) - 2
            if count > max_subdomains:
                max_subdomains = count

    # --- 2. RETORNAR DICCIONARIO CON LAS 28 CARACTERÍSTICAS ---
    return {
        # Versión 1: Características Base (15 columnas)
        "num_urls": num_urls,
        "has_ip_url": has_ip_url,
        "max_url_length": max_url_length,
        "num_distinct_domains": num_distinct_domains,
        "num_link_mismatch": num_link_mismatch,
        "has_form": has_form,
        "is_html": is_html,
        "urgency_words": urgency_words,
        "sensitive_words": sensitive_words,
        "uppercase_ratio": uppercase_ratio,
        "exclamation_count": exclamation_count,
        "body_length": body_length,
        "num_attachments": num_attachments,
        "risky_attachment": risky_attachment,
        "from_replyto_mismatch": from_replyto_mismatch,
        # Versión 2: Características Adicionales (13 columnas)
        "has_auth_results": has_auth_results,
        "spf_pass": spf_pass,
        "dkim_pass": dkim_pass,
        "num_received_hops": num_received_hops,
        "from_free_domain": from_free_domain,
        "display_name_mismatch": display_name_mismatch,
        "url_shortener_count": url_shortener_count,
        "url_has_at_symbol": url_has_at_symbol,
        "non_https_count": non_https_count,
        "max_subdomains": max_subdomains,
        "generic_greeting": generic_greeting,
        "digits_ratio": digits_ratio,
        "image_count": image_count,
    }
