# Líneas base (validación)

Entradas: 22 características (log1p + StandardScaler ajustado con train). Train 3905 correos, validación 487. Umbral 0.5.

| Modelo / conjunto | Exactitud | Precisión | Recall | F1 | AUC | Falsos positivos | Falsos negativos |
|---|---|---|---|---|---|---|---|
| Regresión logística | 96.1% | 97.9% | 94.4% | 0.961 | 0.988 | 5 | 14 |
| Random Forest | 94.7% | 94.8% | 94.8% | 0.948 | 0.992 | 13 | 13 |

## Importancia de características (Random Forest)

| Característica | Importancia |
|---|---|
| num_urls | 0.261 |
| image_count | 0.191 |
| max_url_length | 0.118 |
| dkim_pass | 0.070 |
| urgency_words | 0.066 |
| body_length | 0.056 |
| spf_pass | 0.046 |
| sensitive_words | 0.036 |
| digits_ratio | 0.029 |
| display_name_mismatch | 0.028 |
| num_distinct_domains | 0.025 |
| uppercase_ratio | 0.023 |
| max_subdomains | 0.020 |
| generic_greeting | 0.013 |
| non_https_count | 0.009 |
| num_attachments | 0.005 |
| from_free_domain | 0.003 |
| risky_attachment | 0.001 |
| url_shortener_count | 0.001 |
| url_has_at_symbol | 0.001 |
| has_ip_url | 0.000 |
| has_form | 0.000 |
