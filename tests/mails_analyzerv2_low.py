import email
from email import policy
from email.utils import parseaddr
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import numpy as np

# Definición del orden estricto de las características (Versión 1 y Versión 2)
FEATURE_NAMES = [
    # Versión 1 (15 características base)
    "num_urls", "has_ip_url", "max_url_length", "num_distinct_domains",
    "num_link_mismatch", "has_form", "is_html", "urgency_words",
    "sensitive_words", "uppercase_ratio", "exclamation_count", "body_length",
    "num_attachments", "risky_attachment", "from_replyto_mismatch",
    # Versión 2 (Adicionales)
    "has_auth_results", "spf_pass", "dkim_pass", "num_received_hops",
    "from_free_domain", "display_name_mismatch", "url_shortener_count",
    "url_has_at_symbol", "non_https_count", "max_subdomains",
    "generic_greeting", "digits_ratio", "image_count"
]

# Características que requieren transformación logarítmica (np.log1p) antes de la red neuronal
LOG_FEATURES = {
    "num_urls", "max_url_length", "num_distinct_domains", "num_link_mismatch",
    "urgency_words", "sensitive_words", "exclamation_count", "body_length",
    "num_attachments", "num_received_hops", "url_shortener_count",
    "non_https_count", "max_subdomains", "image_count"
}

# Listas bilingües constantes
URGENCY_WORDS = ['urgent', 'immediately', 'suspended', 'verify', 'expire', '24 hours', 'urgente', 'inmediatamente', 'suspendida', 'verifique', 'vence']
SENSITIVE_WORDS = ['password', 'credit card', 'ssn', 'account number', 'contraseña', 'tarjeta', 'clave', 'número de cuenta']
RISKY_EXTENSIONS = ['.exe', '.scr', '.zip', '.rar', '.js', '.vbs', '.html', '.htm', '.docm', '.xlsm', '.iso', '.bat', '.cmd', '.jar']
FREE_DOMAINS = ['gmail.com', 'outlook.com', 'yahoo.com', 'hotmail.com']
URL_SHORTENERS = ['bit.ly', 'tinyurl.com', 't.co', 'goo.gl']
GENERIC_GREETINGS = ['dear customer', 'estimado cliente', 'dear user', 'estimado usuario']

def extraer(raw_bytes: bytes) -> dict:
    """Extrae las características numéricas de los bytes de un archivo .eml."""
    # Inicializar diccionario con ceros para evitar fallos si algo no se encuentra
    d = {feature: 0 for feature in FEATURE_NAMES}
    d['uppercase_ratio'] = 0.0
    d['digits_ratio'] = 0.0
    
    try:
        msg = email.message_from_bytes(raw_bytes, policy=policy.default)
        
        # 1. Extracción de encabezados
        from_hdr = msg.get('From', '')
        replyto_hdr = msg.get('Reply-To', '')
        from_name, from_addr = parseaddr(from_hdr)
        _, replyto_addr = parseaddr(replyto_hdr)
        
        from_domain = from_addr.split('@')[-1].lower() if '@' in from_addr else ''
        replyto_domain = replyto_addr.split('@')[-1].lower() if '@' in replyto_addr else ''
        
        if from_domain and replyto_domain and from_domain != replyto_domain:
            d['from_replyto_mismatch'] = 1
            
        if from_domain in FREE_DOMAINS:
            d['from_free_domain'] = 1
            
        if from_name and ('@' in from_name or (from_domain and from_domain not in from_name.lower())):
            d['display_name_mismatch'] = 1
            
        auth_hdr = str(msg.get('Authentication-Results', '')).lower()
        if auth_hdr:
            d['has_auth_results'] = 1
            if 'spf=pass' in auth_hdr: d['spf_pass'] = 1
            if 'dkim=pass' in auth_hdr: d['dkim_pass'] = 1
            
        d['num_received_hops'] = len(msg.get_all('Received') or [])

        # 2. Extracción de cuerpo y adjuntos
        texto = ""
        html = ""
        
        for parte in msg.walk():
            tipo = parte.get_content_type()
            
            # Revisar adjuntos
            filename = parte.get_filename()
            if filename:
                d['num_attachments'] += 1
                ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
                if ext in RISKY_EXTENSIONS:
                    d['risky_attachment'] = 1
                    
            try:
                if tipo == "text/plain":
                    texto += parte.get_content()
                elif tipo == "text/html":
                    d['is_html'] = 1
                    html += parte.get_content()
            except Exception:
                pass # Ignorar partes con codificación rota
                
        # Consolidar texto analizable
        soup = BeautifulSoup(html, "html.parser")
        texto_visible = texto if texto else soup.get_text()
        texto_lower = texto_visible.lower()
        
        # 3. Análisis de texto
        d['body_length'] = len(texto_visible)
        
        letras = sum(1 for c in texto_visible if c.isalpha())
        mayusculas = sum(1 for c in texto_visible if c.isupper())
        if letras > 0:
            d['uppercase_ratio'] = mayusculas / letras
            
        d['exclamation_count'] = texto_visible.count('!')
        
        caracteres = len(texto_visible)
        digitos = sum(1 for c in texto_visible if c.isdigit())
        if caracteres > 0:
            d['digits_ratio'] = digitos / caracteres
            
        for word in URGENCY_WORDS:
            d['urgency_words'] += texto_lower.count(word)
            
        for word in SENSITIVE_WORDS:
            d['sensitive_words'] += texto_lower.count(word)
            
        for greeting in GENERIC_GREETINGS:
            if greeting in texto_lower[:500]: # Buscar en los primeros 500 caracteres
                d['generic_greeting'] = 1
                break

        # 4. Análisis HTML
        if d['is_html'] == 1:
            if soup.find('form'):
                d['has_form'] = 1
            d['image_count'] = len(soup.find_all('img'))
            
            for a in soup.find_all('a', href=True):
                href = a['href']
                texto_enlace = a.get_text().strip()
                if texto_enlace.startswith('http') and href.startswith('http'):
                    dominio_texto = urlparse(texto_enlace).netloc
                    dominio_href = urlparse(href).netloc
                    if dominio_texto and dominio_href and dominio_texto != dominio_href:
                        d['num_link_mismatch'] += 1

        # 5. Análisis de URLs (Texto + HTML)
        urls = re.findall(r'https?://[^\s<>"\']+', texto + html)
        d['num_urls'] = len(urls)
        
        dominios = set()
        for url in urls:
            d['max_url_length'] = max(d['max_url_length'], len(url))
            if '@' in url:
                d['url_has_at_symbol'] = 1
            
            parsed = urlparse(url)
            netloc = parsed.netloc
            dominios.add(netloc)
            
            if parsed.scheme == 'http':
                d['non_https_count'] += 1
                
            if re.search(r'\d+\.\d+\.\d+\.\d+', netloc):
                d['has_ip_url'] = 1
                
            if any(shortener in netloc for shortener in URL_SHORTENERS):
                d['url_shortener_count'] += 1
                
            partes_dominio = netloc.split('.')
            if len(partes_dominio) > 2:
                # Restar dominio principal y TLD para contar subdominios
                d['max_subdomains'] = max(d['max_subdomains'], len(partes_dominio) - 2)

        d['num_distinct_domains'] = len(dominios)

    except Exception as e:
        # Si algo crítico falla a nivel de parsing, retornamos los ceros iniciales
        pass

    return d

def a_vector(d: dict) -> np.ndarray:
    """Convierte el diccionario de características en un vector NumPy para la red neuronal, aplicando log1p donde corresponde."""
    vector = []
    for feature in FEATURE_NAMES:
        valor = d.get(feature, 0)
        if feature in LOG_FEATURES:
            valor = np.log1p(valor)
        vector.append(valor)
    return np.array(vector)

# === CÓMO PROBARLO ===
if __name__ == "__main__":
    # Asegúrate de tener un archivo 'prueba.eml' en la misma carpeta
    try:
        with open("/home/migue/Documents/UNIVERSITY/EighthSemester/PTIA/Project/PTIA_PROJECT/tests/eml_files/t1.eml", "rb") as f:
            raw_bytes = f.read()
            
        resultados = extraer(raw_bytes)
        print("Características extraídas crudas:")
        for k, v in resultados.items():
            print(f"{k}: {v}")
            
        vector = a_vector(resultados)
        print("\nVector final (con log1p aplicado) para la red neuronal:")
        print(vector)
    except FileNotFoundError:
        print("Para probar, coloca un archivo llamado 'prueba.eml' en esta carpeta.")