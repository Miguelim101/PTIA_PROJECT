# phishing_quality.py
# Filtro de calidad para la clase phishing: conserva solo correos con un señuelo de phishing real
# (robo de credenciales, documento compartido, entrega, pago, cripto, suplantación) y descarta
# spam promocional, extorsión e idiomas fuera del alcance (inglés, español y portugués).
import re

LURES = {
    "credenciales": [
        r"password", r"passcode", r"contrase[ñn]a", r"\bsenha\b",
        r"verify (your|the|this)? ?(account|identity|email|e-mail|mailbox|details|information)",
        r"verif(ica|ique|icar) (tu|su|sua)? ?(cuenta|conta|identidad|identidade|datos|dados)",
        r"account (has been |was |is |will be )?(suspend|lock|disabl|restrict|limit|clos|deactivat|on hold|terminat)",
        r"(cuenta|conta) (ha sido |foi |será |sera )?(suspendida|bloqueada|desactivada|suspensa|cancelada)",
        r"unusual (sign|log)[ -]?in", r"unusual activity", r"(sign|log)[ -]?in attempt", r"new sign[ -]?in",
        r"inicio de sesi[oó]n", r"mailbox", r"buz[oó]n", r"storage (is )?(full|limit|almost)", r"quota",
        r"webmail", r"re-?activat", r"deactivat", r"session (has )?expired",
        r"(messages?|emails?) (on hold|pending|queued|held|undelivered|rejected|blocked)", r"pending (messages?|emails?)",
        r"mail (server|delivery) (notification|failure|error)", r"incoming (mail|messages?)",
        r"confirm (your|the) (account|identity|email|e-mail|details|information|ownership)",
        r"validat(e|ion) (your|of your)", r"security (alert|notice|update|warning|check)",
        r"update (your )?(billing|payment|account|information|details|credentials)",
        r"actualiz(a|ar|e) (tus|sus|los) datos", r"atualiz(e|ar) (seus|os) dados",
        r"two[- ]factor", r"\b2fa\b", r"one[- ]time (code|password)", r"c[oó]digo de (verificaci[oó]n|seguridad)",
        r"(microsoft|office ?365|outlook|apple ?id|icloud|netflix|paypal|amazon|facebook|instagram|whatsapp|"
        r"linkedin|google|gmail|yahoo|chase|wells fargo|bank of america|bancolombia|davivienda|nequi|"
        r"itau|ita[uú]|bradesco|santander|nubank|banco)\b.{0,60}(account|cuenta|conta|verify|sign|log|secur|"
        r"suspend|confirm|update|password|alert|unusual)",
    ],
    "documento_compartido": [
        r"shared (a |an )?(file|document|folder|item)", r"docusign", r"sharepoint", r"onedrive", r"dropbox",
        r"wetransfer", r"\be-?sign(ature)?\b", r"signature (required|request)", r"voice ?mail", r"scanned (document|file)", r"secure (message|document|file)",
        r"encrypted (message|email)", r"view (the )?document", r"\bfax\b", r"documento compartido",
        r"te (ha )?compartido", r"compartilhou",
    ],
    "entrega": [
        r"(package|parcel|shipment|delivery) (is |was |has been |could not|couldn.t|on hold|pending|failed|"
        r"attempt|suspended|undeliver)", r"delivery (notification|address|fee|failure)", r"tracking number",
        r"customs (fee|duty|charge)", r"\b(dhl|fedex|ups|usps|royal mail|correos|servientrega|"
        r"interrapidisimo|4-72|jadlog|sedex)\b", r"paquete", r"encomenda", r"taxa alfandeg", r"aduana",
    ],
    "pago_factura": [
        r"invoice", r"payment (failed|declined|pending|confirmation|request|due|advice|notice)",
        r"remittance", r"\bwire (transfer|payment)", r"\bach\b", r"refund", r"tax (return|refund)", r"\birs\b", r"\bdian\b",
        r"billing (problem|issue|information|details)", r"overdue", r"unpaid", r"purchase order", r"\bpo\b ?#?\d",
        r"factura", r"pago (pendiente|rechazado|fallido)", r"\bmulta\b", r"\bfatura\b", r"boleto", r"\bpix\b",
        r"comparendo", r"fotomulta", r"\bsimit\b", r"infra[çc][ãa]o", r"\bdetran\b", r"\bcnh\b",
        r"receita federal", r"valores a receber", r"gov\.br", r"subscription (has )?(expired|failed|cancel|renew)", r"membership (will be |has been )?cancel",
    ],
    "cripto": [
        r"airdrop", r"seed phrase", r"recovery phrase", r"metamask", r"trust ?wallet", r"ledger (live|wallet|recovery)",
        r"wallet (verification|sync|validation|connect)", r"claim (your )?(tokens?|eth|usdt|reward)",
        r"coinbase", r"binance", r"kraken",
    ],
    "suplantacion_bec": [
        r"are you available", r"quick (favor|request)", r"kindly (confirm|send|process|review)",
        r"urgent(ly)? (request|attention|response|payment)", r"payroll", r"direct deposit", r"\bw-?2\b",
        r"gift cards? for", r"change (of|in) (bank|banking) (details|information)",
    ],
}

# Spam promocional o estafas que no son phishing (no intentan robar credenciales ni datos de pago)
SPAM = [
    r"casino", r"free spins", r"\bspins\b", r"jackpot", r"\bslots?\b", r"betting", r"\bbet\b", r"sweepstake",
    r"lottery", r"loter[ií]a", r"you('ve| have)? won", r"\bwinner\b", r"ganador", r"\bprize\b", r"premio",
    r"survey", r"encuesta", r"viagra", r"cialis", r"\bpills?\b", r"\bketo\b", r"weight loss", r"glp-?1",
    r"belly fat", r"dating", r"singles", r"hook ?up", r"married wom", r"\bsex", r"\bporn", r"\bnude",
    r"\bloan\b", r"mortgage", r"insurance quote", r"% off", r"discount", r"deal of", r"free trial",
    r"supplement", r"\bcbd\b", r"miracle", r"mystery box", r"selected to receive", r"warranty",
    r"credit (card )?limit", r"cashback", r"beneficiary", r"compensation fund", r"inheritance", r"secret (government|loophole)", r"mensualit", r"rebate",
]

# Extorsión ("sextortion"): estafa por amenaza, sin señuelo de phishing
EXTORTION = [r"hacked your", r"recorded you", r"pornographic", r"your (webcam|camera)", r"intimate video"]

LANG_WORDS = {
    "en": r"\b(the|your|you|and|to|account|please|click|here)\b",
    "es": r"\b(el|la|los|las|de|que|su|tu|cuenta|usted|por favor|aquí)\b",
    "pt": r"\b(você|voce|sua|seu|seus|não|nao|conta|olá|ola|clique|aqui|em|do|da|\w+ção|\w+ções)\b",
}

LURE_PATTERNS = {category: re.compile("|".join(patterns)) for category, patterns in LURES.items()}
SPAM_PATTERN = re.compile("|".join(SPAM))
EXTORTION_PATTERN = re.compile("|".join(EXTORTION))


# Caracteres invisibles usados para ofuscar palabras clave (p. ej. "P\u200dass\u200dword")
INVISIBLE = re.compile("[\u00ad\u034f\u180e\u200b-\u200f\u2060-\u2064\ufeff]")


# Idiomas frecuentes en el corpus que quedan fuera del alcance del proyecto
OUT_OF_SCOPE_WORDS = {
    "de": r"\b(und|der|die|das|ist|sie|ihre?|nicht|mit|f[üu]r|wir|bitte)\b",
    "nl": r"\b(het|een|uw|niet|voor|van|wij|met|bestelling|deze)\b",
    "fr": r"\b(le|les|des|vous|votre|vos|est|pour|avec|nous|dans)\b",
}
# Escrituras no latinas (árabe, hebreo, CJK, tailandés...). El cirílico no se incluye porque se usa
# como homoglifo para ofuscar palabras en inglés.
NON_LATIN = re.compile("[\u0590-\u06ff\u0e00-\u0e7f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def detect_language(text: str) -> str:
    if len(NON_LATIN.findall(text)) > 10:
        return "otro"
    counts = {lang: len(re.findall(pattern, text)) for lang, pattern in LANG_WORDS.items()}
    lang, hits = max(counts.items(), key=lambda item: item[1])
    other_hits = max(len(re.findall(pattern, text)) for pattern in OUT_OF_SCOPE_WORDS.values())
    words = max(len(text.split()), 1)
    # Con muy pocas coincidencias, o más palabras de otro idioma, el texto queda fuera del alcance
    if hits < 3 or hits / words < 0.02 or other_hits > hits:
        return "otro"
    return lang


def classify_phishing(subject: str, visible_text: str, has_url: bool, attachments: list, trusted: bool = False):
    """Devuelve (categoría, idioma, motivo_de_descarte). motivo_de_descarte es None si el correo sirve.

    trusted=True indica una fuente clasificada a mano (Nazario): si no se reconoce el señuelo,
    el correo se conserva como "otro" en lugar de descartarse.
    """
    text = INVISIBLE.sub("", f"{subject} {visible_text[:4000]}").lower()
    language = detect_language(text)
    subject_text = INVISIBLE.sub("", subject).lower()
    subject_foreign = any(re.search(pattern, subject_text) for pattern in OUT_OF_SCOPE_WORDS.values())
    subject_in_scope = any(re.search(pattern, subject_text) for pattern in LANG_WORDS.values())
    if language == "otro" or (subject_foreign and not subject_in_scope):
        return None, language, "idioma_fuera_de_alcance"
    if EXTORTION_PATTERN.search(text):
        return None, language, "extorsion"
    if SPAM_PATTERN.search(text):
        return None, language, "spam_promocional"
    category = next((name for name, pattern in LURE_PATTERNS.items() if pattern.search(text)), None)
    if category is None:
        if not trusted:
            return None, language, "sin_senuelo_claro"
        category = "otro"
    if not has_url and not attachments and category != "suplantacion_bec":
        return None, language, "sin_vector"
    return category, language, None
