# extractor.py
# Extrae las 28 características numéricas de un correo crudo (.eml) para el modelo de phishing.
# Se usa igual en el entrenamiento (training/) y en la API, y nunca lanza excepciones: ante un
# correo dañado o una parte ilegible, la característica afectada queda en 0.
import ipaddress
import math
import re
import unicodedata
import warnings
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

# Orden fijo del vector de entrada del modelo (1 x 28), agrupado por peso según el documento
FEATURE_NAMES = [
    # Peso crítico: infraestructura y redirección
    "num_link_mismatch", "spf_pass", "dkim_pass", "from_replyto_mismatch",
    # Peso significativo: ofuscación y estructura
    "url_has_at_symbol", "max_subdomains", "has_form", "has_ip_url", "url_shortener_count",
    "from_free_domain", "risky_attachment",
    # Peso contextual: cuantitativas y semánticas
    "body_length", "uppercase_ratio", "digits_ratio", "urgency_words", "sensitive_words",
    "exclamation_count", "image_count", "num_urls", "num_distinct_domains", "is_html",
    "max_url_length", "num_attachments", "has_auth_results", "num_received_hops",
    "display_name_mismatch", "generic_greeting", "non_https_count",
]

# Características que se extraen (y se muestran en la interfaz) pero el modelo no usa:
# - num_received_hops depende del servidor que recibió el correo (Outlook, Gmail...) y no del remitente:
#   en la auditoría del dataset hizo que el modelo reconociera el corpus de origen (training/reports/audit.md).
# - num_link_mismatch, is_html y has_auth_results no distinguen las clases (frecuencia casi igual o casi
#   constante), y exclamation_count y from_replyto_mismatch aportan muy poco. En el análisis de importancia
#   (permutación y ablación) quitarlas mejoró ligeramente el modelo en validación.
EXCLUDED_FROM_MODEL = {"num_received_hops", "num_link_mismatch", "is_html", "has_auth_results",
                       "exclamation_count", "from_replyto_mismatch"}
MODEL_FEATURES = [name for name in FEATURE_NAMES if name not in EXCLUDED_FROM_MODEL]

# Conteos con colas largas: se suavizan con log1p antes del StandardScaler
LOG_FEATURES = {
    "num_link_mismatch", "max_subdomains", "url_shortener_count", "body_length", "urgency_words",
    "sensitive_words", "exclamation_count", "image_count", "num_urls", "num_distinct_domains",
    "max_url_length", "num_attachments", "num_received_hops", "non_https_count",
}

# --- Vocabulario (inglés, español y portugués; se compara sin tildes y en minúsculas) ---
# Se evitan términos genéricos que aparecen en los pies legales de correos legítimos colombianos
# ("tratamiento de datos personales", "notificarlo inmediatamente al remitente") o con otro sentido
# ("palabras clave", "tarjetas de embarque"): en la revisión no distinguían phishing de legítimos.
URGENCY_WORDS = [
    "urgent", "immediately", "immediate action", "action required", "as soon as possible",
    "within 24 hours", "within 48 hours", "expire", "suspend", "deactivat", "will be closed",
    "final notice", "last warning", "final warning", "limited time",
    "urgente", "suspendid", "bloquead", "vence", "ultimo aviso", "accion requerida",
    "lo antes posible", "24 horas", "48 horas",
    "imediat", "suspens", "ultimo aviso", "acao necessaria", "o mais rapido possivel",
]
SENSITIVE_WORDS = [
    "password", "passcode", "credential", "login", "log in", "sign in", "verify your",
    "confirm your", "social security", "ssn", "credit card", "card number", "cvv", "pin code",
    "billing", "bank account", "account number", "wallet",
    "contrasena", "credenciales", "iniciar sesion", "verifica tu", "verifique su", "confirma tu",
    "numero de tarjeta", "tarjeta de credito", "datos de su tarjeta", "datos de tu tarjeta", "cedula",
    "cuenta bancaria",
    "senha", "credenciais", "numero do cartao", "cartao de credito", "dados do cartao", "cpf", "conta bancaria",
]
GENERIC_GREETINGS = [
    "dear customer", "dear user", "dear client", "dear member", "dear valued customer",
    "dear account holder", "dear sir", "dear madam", "dear sir/madam", "hello user", "dear friend",
    "estimado cliente", "estimado usuario", "querido usuario", "querido cliente", "apreciado cliente",
    "apreciado usuario", "estimado(a)", "hola usuario",
    "prezado cliente", "caro cliente", "prezado usuario", "caro usuario", "prezado(a)",
]

FREE_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.es", "ymail.com", "hotmail.com", "hotmail.es",
    "outlook.com", "outlook.es", "live.com", "msn.com", "aol.com", "icloud.com", "me.com", "mail.com",
    "gmx.com", "gmx.net", "yandex.com", "yandex.ru", "proton.me", "protonmail.com", "zoho.com",
    "mail.ru", "qq.com", "163.com", "uol.com.br", "bol.com.br",
}
URL_SHORTENERS = {
    "bit.ly", "goo.gl", "tinyurl.com", "t.co", "is.gd", "ow.ly", "buff.ly", "rebrand.ly", "cutt.ly",
    "shorturl.at", "rb.gy", "t.ly", "tiny.cc", "s.id", "bl.ink", "qrco.de", "v.gd", "shorte.st",
    "tr.im", "x.co", "lnkd.in", "urlz.fr", "surl.li", "n9.cl",
}
RISKY_EXTENSIONS = (
    ".exe", ".scr", ".bat", ".cmd", ".com", ".pif", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".hta", ".ps1", ".msi", ".jar", ".lnk", ".iso", ".img", ".vhd", ".zip", ".rar", ".7z", ".gz",
    ".cab", ".docm", ".xlsm", ".pptm", ".dotm", ".xlam", ".html", ".htm", ".shtml", ".svg",
)
# Marca mencionada en el nombre visible -> nombres válidos del dominio registrable del remitente
# (p. ej. "paypal" acepta paypal.com o mail.paypal.com, pero no paypal-secure.xyz)
MICROSOFT = ("microsoft", "office", "outlook", "live", "microsoftonline", "office365", "sharepointonline")
BRANDS = {
    "paypal": ("paypal",), "microsoft": MICROSOFT, "office 365": MICROSOFT, "office365": MICROSOFT,
    "outlook": MICROSOFT, "onedrive": MICROSOFT, "sharepoint": MICROSOFT + ("sharepoint",),
    "apple": ("apple",), "icloud": ("apple", "icloud"), "amazon": ("amazon", "amazonaws"),
    "netflix": ("netflix",), "google": ("google",), "gmail": ("google",),
    "facebook": ("facebook", "facebookmail", "meta"), "instagram": ("instagram", "facebookmail", "meta"),
    "whatsapp": ("whatsapp", "facebookmail", "meta"), "linkedin": ("linkedin",),
    "docusign": ("docusign",), "dropbox": ("dropbox", "dropboxmail"), "adobe": ("adobe", "adobesign"),
    "wetransfer": ("wetransfer",), "dhl": ("dhl",), "fedex": ("fedex",), "usps": ("usps",),
    "wells fargo": ("wellsfargo",), "chase": ("chase",), "bank of america": ("bankofamerica", "bofa"),
    "bancolombia": ("bancolombia",), "davivienda": ("davivienda",), "nequi": ("nequi",),
    "mercado libre": ("mercadolibre", "mercadopago"), "mercadolibre": ("mercadolibre", "mercadopago"),
    "itau": ("itau",), "bradesco": ("bradesco",), "santander": ("santander",), "nubank": ("nubank", "nu"),
    "coinbase": ("coinbase",), "binance": ("binance",), "metamask": ("metamask",), "ledger": ("ledger",),
}
# Segundo nivel genérico bajo un TLD de país (p. ej. com.co, co.uk, gov.br)
SECOND_LEVEL = {"com", "co", "net", "org", "gov", "gob", "edu", "ac", "mil", "nom", "ne", "or"}

URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'(){}]+", re.IGNORECASE)
DOMAIN_LIKE = re.compile(r"^(https?://)?(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)+(/\S*)?$", re.IGNORECASE)
HTML_LIKE = re.compile(r"<(html|body|div|td|p|table|a)\b", re.IGNORECASE)
INVISIBLE = re.compile("[­͏᠎​-‏⁠-⁤﻿]")


def normalize(text: str) -> str:
    """Minúsculas, sin tildes ni caracteres invisibles, para comparar con el vocabulario."""
    text = INVISIBLE.sub("", text.lower())
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def compile_terms(terms):
    escaped = sorted({re.escape(normalize(t)) for t in terms}, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(escaped) + r")")


URGENCY_PATTERN = compile_terms(URGENCY_WORDS)
SENSITIVE_PATTERN = compile_terms(SENSITIVE_WORDS)
GREETING_PATTERN = compile_terms(GENERIC_GREETINGS)


def header(msg, name: str) -> str:
    try:
        value = msg.get(name)
        return str(value) if value is not None else ""
    except Exception:
        return ""


def address_domain(value: str) -> str:
    address = parseaddr(value)[1]
    return address.rsplit("@", 1)[-1].strip().lower() if "@" in address else ""


def hostname(url: str) -> str:
    try:
        return (urlsplit(url.strip()).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        # Formas ofuscadas: entero decimal (http://3232235777) o hexadecimal (http://0xC0A80001)
        return bool(re.fullmatch(r"\d{8,10}|0x[0-9a-f]{8}", host))


def registrable_domain(host: str) -> str:
    """Dominio registrable aproximado: ejemplo.com, ejemplo.com.co, ejemplo.co.uk."""
    if not host or is_ip(host):
        return host
    parts = host.split(".")
    size = 3 if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in SECOND_LEVEL else 2
    return ".".join(parts[-size:])


def subdomain_count(host: str) -> int:
    if not host or is_ip(host):
        return 0
    return max(len(host.split(".")) - len(registrable_domain(host).split(".")), 0)


def read_parts(msg):
    """Recorre todo el árbol MIME. Devuelve (texto plano, html, nombres de adjuntos)."""
    plain, html, attachments = [], [], []
    for part in msg.walk():
        if part.is_multipart():
            continue
        try:
            filename = part.get_filename()
            disposition = (part.get_content_disposition() or "").lower()
        except Exception:
            filename, disposition = None, ""
        content_type = part.get_content_type()
        if disposition == "attachment" or (filename and disposition != "inline"):
            attachments.append((filename or "").lower())
            continue
        if content_type not in ("text/plain", "text/html"):
            continue
        try:
            content = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            content = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else ""
        if not isinstance(content, str):
            continue
        # Algunos correos declaran text/plain pero envían HTML
        if content_type == "text/html" or HTML_LIKE.search(content):
            html.append(content)
        else:
            plain.append(content)
    return "\n".join(plain), "\n".join(html), attachments


def empty_features() -> dict:
    return {name: 0 for name in FEATURE_NAMES}


def parse_message(eml_source):
    if isinstance(eml_source, (bytes, bytearray)):
        raw = bytes(eml_source)
    else:
        raw = Path(eml_source).read_bytes()
    return BytesParser(policy=policy.default).parsebytes(raw)


def extract_email_features(eml_source) -> dict:
    """Acepta bytes o una ruta a un .eml y devuelve las 28 características (dict ordenado)."""
    features = empty_features()
    try:
        msg = parse_message(eml_source)
    except Exception:
        return features
    for step in (header_features, body_features):
        try:
            step(msg, features)
        except Exception:
            # Una sección ilegible no invalida el resto del vector
            pass
    return features


def header_features(msg, f):
    from_header = header(msg, "from")
    from_domain = address_domain(from_header)

    # Reply-To hacia otro dominio registrable (las respuestas llegan al atacante)
    reply_domains = {d for d in (address_domain(a) for a in header(msg, "reply-to").split(",")) if d}
    if from_domain and reply_domains:
        f["from_replyto_mismatch"] = int(any(registrable_domain(d) != registrable_domain(from_domain)
                                             for d in reply_domains))

    f["from_free_domain"] = int(from_domain in FREE_MAIL_DOMAINS)

    # Nombre visible que menciona una marca o una dirección distinta del remitente real
    display_name = normalize(getaddresses([from_header])[0][0] if from_header else "")
    sender_name = registrable_domain(from_domain).split(".")[0]
    mismatch = 0
    for brand, allowed in BRANDS.items():
        if re.search(r"\b" + re.escape(brand) + r"\b", display_name) and sender_name not in allowed:
            mismatch = 1
            break
    embedded = re.search(r"[\w.+-]+@([\w-]+\.[\w.-]+)", display_name)
    if embedded and from_domain and registrable_domain(embedded.group(1)) != registrable_domain(from_domain):
        mismatch = 1
    f["display_name_mismatch"] = mismatch

    f["num_received_hops"] = len(msg.get_all("received") or [])

    # Solo cuenta el Authentication-Results superior, que añade el servidor que recibe el correo
    auth = header(msg, "authentication-results").lower()
    if is_exchange_internal(msg, auth):
        auth = "exchange-internal; spf=pass; dkim=pass"
    f["has_auth_results"] = int(bool(auth))
    spf = re.search(r"\bspf=(\w+)", auth)
    if spf:
        f["spf_pass"] = int(spf.group(1) == "pass")
    else:
        f["spf_pass"] = int(header(msg, "received-spf").lower().strip().startswith("pass"))
    f["dkim_pass"] = int(bool(re.search(r"\bdkim=pass\b", auth)))


def is_exchange_internal(msg, auth: str) -> bool:
    """Correo interno de Microsoft 365 / Exchange (p. ej. de la universidad a sus estudiantes).

    Exchange autentica al remitente como interno (AuthAs: Internal) y no evalúa SPF ni DKIM, así que el
    correo llega sin Authentication-Results o con uno propio (mx.microsoft.com) sin spf=. Exchange elimina
    esta cabecera de los correos externos; si el Authentication-Results lo agregó otro servidor, la
    cabecera pudo ser falsificada por el remitente y no se tiene en cuenta.
    """
    if header(msg, "x-ms-exchange-organization-authas").strip().lower() != "internal":
        return False
    return not auth or (auth.startswith("mx.microsoft.com") and "spf=" not in auth)


def body_features(msg, f):
    plain, html, attachments = read_parts(msg)
    f["is_html"] = int(bool(html))
    f["num_attachments"] = len(attachments)
    f["risky_attachment"] = int(any(name.endswith(RISKY_EXTENSIONS) for name in attachments))

    soup = BeautifulSoup(html, "html.parser") if html else None
    # Texto visible: lo que muestra el cliente de correo (HTML si existe, si no el texto plano)
    visible = soup.get_text(" ", strip=True) if soup else plain
    if soup and len(visible) < 20 and len(plain.strip()) > len(visible):
        visible = plain  # HTML sin texto (solo imágenes): se usa la versión de texto plano
    visible = INVISIBLE.sub("", " ".join(visible.split()))

    links, mismatches = [], 0
    if soup:
        f["has_form"] = int(soup.find("form") is not None)
        f["image_count"] = len(soup.find_all("img"))
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href.lower().startswith(("http://", "https://")):
                continue  # mailto:, tel:, anclas internas
            links.append(href)
            # El texto visible aparenta un dominio distinto del destino real
            text = anchor.get_text(" ", strip=True).lower()
            if DOMAIN_LIKE.match(text):
                shown = hostname(text if "://" in text else "http://" + text)
                target = hostname(href)
                if shown and target and registrable_domain(shown) != registrable_domain(target):
                    mismatches += 1
        for form in soup.find_all("form", action=True):
            if form["action"].lower().startswith(("http://", "https://")):
                links.append(form["action"].strip())
    f["num_link_mismatch"] = mismatches

    links += URL_IN_TEXT.findall(plain) + URL_IN_TEXT.findall(visible)
    urls = sorted({u.rstrip(".,;:!?") for u in links})
    hosts = [hostname(u) for u in urls]
    f["num_urls"] = len(urls)
    f["max_url_length"] = max((len(u) for u in urls), default=0)
    f["num_distinct_domains"] = len({registrable_domain(h) for h in hosts if h})
    f["has_ip_url"] = int(any(is_ip(h) for h in hosts if h))
    f["max_subdomains"] = max((subdomain_count(h) for h in hosts), default=0)
    f["url_shortener_count"] = sum(1 for h in hosts if h in URL_SHORTENERS)
    f["non_https_count"] = sum(1 for u in urls if u.lower().startswith("http://"))
    f["url_has_at_symbol"] = int(any(fake_host_before_at(u) for u in urls))

    subject = header(msg, "subject")
    searchable = normalize(f"{subject} {visible}")
    f["urgency_words"] = len(set(URGENCY_PATTERN.findall(searchable)))
    f["sensitive_words"] = len(set(SENSITIVE_PATTERN.findall(searchable)))
    f["generic_greeting"] = int(bool(GREETING_PATTERN.search(searchable)))

    f["body_length"] = len(visible)
    f["exclamation_count"] = visible.count("!")
    letters = [c for c in visible if c.isalpha()]
    f["uppercase_ratio"] = round(sum(c.isupper() for c in letters) / len(letters), 4) if letters else 0.0
    non_space = len(visible.replace(" ", ""))
    f["digits_ratio"] = round(sum(c.isdigit() for c in visible) / non_space, 4) if non_space else 0.0


def fake_host_before_at(url: str) -> bool:
    """URL con un dominio falso antes de la @: el navegador ignora todo lo previo a la @, así que
    http://www.banco.com-login@sitio-malo.app lleva a sitio-malo.app. Un usuario simple (jose@) no cuenta."""
    try:
        netloc = urlsplit(url).netloc
    except ValueError:
        return False
    return "@" in netloc and "." in netloc.rsplit("@", 1)[0]


def to_vector(features: dict, names=None) -> list:
    """Vector de entrada del scaler: valores en el orden de `names` (por defecto MODEL_FEATURES),
    con log1p aplicado a LOG_FEATURES."""
    vector = []
    for name in names or MODEL_FEATURES:
        value = float(features.get(name, 0) or 0)
        vector.append(math.log1p(max(value, 0.0)) if name in LOG_FEATURES else value)
    return vector
