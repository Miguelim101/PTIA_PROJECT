# test_extractor.py
# Pruebas del extractor de características: casos sintéticos para cada característica,
# los correos de ejemplo de tests/eml_files/ y un barrido del corpus curado (si existe).
import math
from email.message import EmailMessage
from pathlib import Path

import pytest

from app.extractor import FEATURE_NAMES, LOG_FEATURES, MODEL_FEATURES, extract_email_features, to_vector

ROOT = Path(__file__).resolve().parent.parent
EML_DIR = ROOT / "tests" / "eml_files"
CURATED_DIR = ROOT / "training" / "datasets" / "curated"
# Los correos de ejemplo son locales (no se versionan): las pruebas que los usan se omiten si faltan
needs_samples = pytest.mark.skipif(not (EML_DIR / "t3_p.eml").exists(),
                                   reason="correos de ejemplo locales no disponibles en tests/eml_files/")


def make_eml(html=None, plain=None, attachments=(), **headers) -> bytes:
    msg = EmailMessage()
    msg["From"] = headers.pop("from_", "Tienda <ventas@tienda.com>")
    msg["To"] = "usuario@example.com"
    msg["Subject"] = headers.pop("subject", "Hola")
    for name, value in headers.items():
        msg[name.replace("_", "-")] = value
    if plain is not None:
        msg.set_content(plain)
    if html is not None:
        if plain is None:
            msg.set_content(html, subtype="html")
        else:
            msg.add_alternative(html, subtype="html")
    for filename in attachments:
        msg.add_attachment(b"contenido", maintype="application", subtype="octet-stream", filename=filename)
    return msg.as_bytes()


# --- Contrato del vector ---

def test_feature_names_are_28_unique():
    assert len(FEATURE_NAMES) == 28
    assert len(set(FEATURE_NAMES)) == 28
    assert LOG_FEATURES <= set(FEATURE_NAMES)


def test_to_vector_order_and_log1p():
    features = extract_email_features(make_eml(plain="Visita https://tienda.com ahora"))
    vector = to_vector(features)
    assert len(vector) == len(MODEL_FEATURES) == 22
    assert "num_received_hops" not in MODEL_FEATURES and "is_html" not in MODEL_FEATURES
    index = MODEL_FEATURES.index("body_length")
    assert vector[index] == pytest.approx(math.log1p(features["body_length"]))
    assert vector[MODEL_FEATURES.index("uppercase_ratio")] == features["uppercase_ratio"]
    assert len(to_vector(features, FEATURE_NAMES)) == 28


@pytest.mark.parametrize("raw", [b"", b"\x00\xff basura sin cabeceras", b"From: <<<\r\n\r\n<html><a href='http://[::1'>x</a>"])
def test_never_raises_on_broken_input(raw):
    features = extract_email_features(raw)
    assert list(features) == FEATURE_NAMES


def test_accepts_path(tmp_path):
    path = tmp_path / "correo.eml"
    path.write_bytes(make_eml(plain="hola"))
    assert extract_email_features(path)["body_length"] == 4


# --- Cuerpo y URLs ---

def test_html_body_preferred_over_short_plain_part():
    html = "<html><body><p>Contenido real</p><a href='https://tienda.com/a'>ver</a></body></html>"
    features = extract_email_features(make_eml(plain="x", html=html))
    assert features["is_html"] == 1
    assert features["num_urls"] == 1
    assert features["body_length"] == len("Contenido real ver")


def test_html_declared_as_plain_is_parsed():
    raw = make_eml(plain="<html><body><a href='https://a.com'>a</a><img src='x.png'></body></html>")
    features = extract_email_features(raw)
    assert features["is_html"] == 1
    assert features["image_count"] == 1


def test_link_mismatch_compares_registrable_domains():
    html = (
        "<a href='https://evil.xyz/login'>https://www.paypal.com</a>"
        "<a href='https://click.tienda.com/r'>www.tienda.com</a>"   # mismo dominio registrable
        "<a href='https://evil.xyz/2'>Haz clic aquí</a>"              # el texto no aparenta un dominio
    )
    assert extract_email_features(make_eml(html=html))["num_link_mismatch"] == 1


def test_mailto_and_tel_are_not_urls():
    html = "<a href='mailto:soporte@tienda.com'>escríbenos</a><a href='tel:+571234'>llámanos</a>"
    features = extract_email_features(make_eml(html=html))
    assert features["num_urls"] == 0
    assert features["url_has_at_symbol"] == 0


def test_fake_host_before_at_symbol():
    fake = extract_email_features(make_eml(plain="Entra a https://www.banco.com-seguro@malo.run.app/x"))
    plain_user = extract_email_features(make_eml(plain="Entra a http://usuario@tienda.com"))
    assert fake["url_has_at_symbol"] == 1
    assert plain_user["url_has_at_symbol"] == 0


@pytest.mark.parametrize("url", ["http://192.168.10.5/login", "http://3232235777/x", "http://[2001:db8::1]/a"])
def test_ip_urls(url):
    assert extract_email_features(make_eml(plain=f"Ingresa: {url}"))["has_ip_url"] == 1


def test_malformed_url_does_not_break_other_features():
    features = extract_email_features(make_eml(plain="Mal: http://[::1 y bien: https://tienda.com/ok"))
    assert features["num_urls"] == 2
    assert features["num_distinct_domains"] == 1


def test_subdomains_with_compound_tld():
    features = extract_email_features(make_eml(plain="https://www.portal.banco.com.co/a https://ejemplo.co.uk"))
    assert features["max_subdomains"] == 2


def test_shorteners_match_whole_host_only():
    raw = make_eml(plain="https://bit.ly/abc https://www.microsoft.com/es https://t.co/x")
    assert extract_email_features(raw)["url_shortener_count"] == 2


def test_url_counts():
    raw = make_eml(plain="http://a.com/1 https://b.org/2 https://b.org/2 http://sub.a.com/3")
    features = extract_email_features(raw)
    assert features["num_urls"] == 3
    assert features["num_distinct_domains"] == 2
    assert features["non_https_count"] == 2
    assert features["max_url_length"] == len("http://sub.a.com/3")


def test_form_and_images():
    html = "<form action='https://evil.xyz/post'><input name='pass'></form><img src='a.png'><img src='b.png'>"
    features = extract_email_features(make_eml(html=html))
    assert features["has_form"] == 1
    assert features["image_count"] == 2
    assert features["num_urls"] == 1


# --- Adjuntos ---

def test_risky_attachments():
    features = extract_email_features(make_eml(plain="adjunto", attachments=["factura.pdf", "Factura.HTML"]))
    assert features["num_attachments"] == 2
    assert features["risky_attachment"] == 1


def test_safe_attachment():
    features = extract_email_features(make_eml(plain="adjunto", attachments=["informe.pdf"]))
    assert features["num_attachments"] == 1
    assert features["risky_attachment"] == 0


def test_attachment_inside_forwarded_message_is_found():
    inner = EmailMessage()
    inner["Subject"] = "original"
    inner.set_content("ver adjunto")
    inner.add_attachment(b"MZ", maintype="application", subtype="octet-stream", filename="pago.exe")
    outer = EmailMessage()
    outer["From"] = "a@b.com"
    outer.set_content("reenvío")
    outer.add_attachment(inner)
    assert extract_email_features(outer.as_bytes())["risky_attachment"] == 1


# --- Texto ---

@pytest.mark.parametrize("text", [
    "URGENT: your account will be suspended, verify your password immediately",
    "URGENTE: su cuenta fue suspendida, verifique su contraseña de inmediato",
    "URGENTE: sua conta foi suspensa, confirme sua senha imediatamente",
])
def test_keywords_in_three_languages(text):
    features = extract_email_features(make_eml(plain=text))
    assert features["urgency_words"] >= 2
    assert features["sensitive_words"] >= 1


def test_keywords_ignore_accents_and_invisible_characters():
    # "contraseña" con un carácter invisible intercalado y "sesión" con tilde
    features = extract_email_features(make_eml(plain="Actualiza tu contrase​ña para iniciar sesión"))
    assert features["sensitive_words"] == 2


@pytest.mark.parametrize("greeting", ["Dear Customer,", "Estimado cliente:", "Prezado cliente,"])
def test_generic_greeting(greeting):
    assert extract_email_features(make_eml(plain=f"{greeting} gracias"))["generic_greeting"] == 1


def test_ratios_use_letters_and_visible_characters():
    features = extract_email_features(make_eml(plain="ABcd 12!!"))
    assert features["uppercase_ratio"] == 0.5          # 2 de 4 letras
    assert features["digits_ratio"] == pytest.approx(2 / 8, abs=1e-4)
    assert features["exclamation_count"] == 2


# --- Cabeceras ---

def test_reply_to_mismatch_uses_registrable_domain():
    other = make_eml(plain="x", from_="Banco <alertas@banco.com>", reply_to="pagos@gmail.com")
    same = make_eml(plain="x", from_="Banco <alertas@banco.com>", reply_to="Soporte <ayuda@mail.banco.com>")
    assert extract_email_features(other)["from_replyto_mismatch"] == 1
    assert extract_email_features(same)["from_replyto_mismatch"] == 0


def test_from_with_at_in_display_name():
    raw = make_eml(plain="x", from_='"soporte@paypal.com" <ataque@gmail.com>')
    features = extract_email_features(raw)
    assert features["from_free_domain"] == 1
    assert features["display_name_mismatch"] == 1


@pytest.mark.parametrize("from_, expected", [
    ("PayPal Service <service@paypal-secure.xyz>", 1),
    ("Microsoft account team <no-reply@access-security.com>", 1),
    ("DHL Express <info@cargo-mail.ru>", 1),
    ("PayPal <service@paypal.com>", 0),
    ("Microsoft <account-security-noreply@accountprotection.microsoft.com>", 0),
    ("Mercado Libre <info@r.mercadolibre.com.co>", 0),
    ("Duolingo <hello@duolingo.com>", 0),
])
def test_display_name_mismatch(from_, expected):
    assert extract_email_features(make_eml(plain="x", from_=from_))["display_name_mismatch"] == expected


def test_authentication_results_uses_top_header_only():
    raw = (
        b"Authentication-Results: mx.receptor.com; spf=fail smtp.mailfrom=evil.xyz; dkim=none\r\n"
        b"Authentication-Results: falso.com; spf=pass; dkim=pass\r\n"
        b"Received: from a by b\r\nReceived: from c by d\r\n"
        b"From: x@evil.xyz\r\nSubject: s\r\n\r\ncuerpo"
    )
    features = extract_email_features(raw)
    assert features["has_auth_results"] == 1
    assert features["spf_pass"] == 0
    assert features["dkim_pass"] == 0
    assert features["num_received_hops"] == 2


def test_received_spf_fallback():
    raw = b"Received-SPF: Pass (dominio autorizado)\r\nFrom: x@tienda.com\r\n\r\ncuerpo"
    features = extract_email_features(raw)
    assert features["spf_pass"] == 1
    assert features["has_auth_results"] == 0


def test_exchange_internal_mail_counts_as_authenticated():
    internal = (b"Received: from a.prod.exchangelabs.com by b.prod.exchangelabs.com\r\n"
                b"X-MS-Exchange-Organization-AuthAs: Internal\r\nFrom: avisos@universidad.edu.co\r\n\r\ncuerpo")
    features = extract_email_features(internal)
    assert (features["has_auth_results"], features["spf_pass"], features["dkim_pass"]) == (1, 1, 1)


def test_exchange_internal_with_own_authentication_results():
    raw = (b"Authentication-Results: mx.microsoft.com 1; dkim=none (message not signed) header.d=none;"
           b"dmarc=none action=none header.from=universidad.edu.co;\r\n"
           b"X-MS-Exchange-Organization-AuthAs: Internal\r\nFrom: avisos@universidad.edu.co\r\n\r\ncuerpo")
    features = extract_email_features(raw)
    assert (features["spf_pass"], features["dkim_pass"]) == (1, 1)


def test_forged_exchange_header_is_ignored_when_receiver_added_results():
    forged = (b"Authentication-Results: mx.otro.com; spf=fail; dkim=none\r\n"
              b"X-MS-Exchange-Organization-AuthAs: Internal\r\nFrom: x@evil.xyz\r\n\r\ncuerpo")
    features = extract_email_features(forged)
    assert (features["spf_pass"], features["dkim_pass"]) == (0, 0)


def test_recipient_does_not_change_features():
    # Los corpus anonimizan al destinatario (jose@monkey.org, phishing@pot): no debe influir
    a = make_eml(plain="https://tienda.com")
    b = a.replace(b"usuario@example.com", b"jose@monkey.org")
    assert extract_email_features(a) == extract_email_features(b)


# --- Correos reales ---

@pytest.mark.parametrize("path", sorted(EML_DIR.glob("*.eml")), ids=lambda p: p.name)
def test_sample_emails(path):
    features = extract_email_features(path)
    assert list(features) == FEATURE_NAMES
    assert all(isinstance(v, (int, float)) and v >= 0 for v in features.values())
    assert features["body_length"] > 0


@needs_samples
def test_phishing_samples_flagged():
    t3 = extract_email_features(EML_DIR / "t3_p.eml")
    assert t3["url_shortener_count"] >= 1


@pytest.mark.skipif(not CURATED_DIR.exists(), reason="corpus curado no disponible (training/build_corpus.py)")
def test_curated_corpus_has_no_failures():
    files = list(CURATED_DIR.rglob("*.eml"))
    features = [extract_email_features(f.read_bytes()) for f in files]
    empty = [f for f in features if f["body_length"] == 0 and f["num_attachments"] == 0]
    assert files
    assert len(empty) / len(files) < 0.01
