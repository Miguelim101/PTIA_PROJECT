# Reporte del corpus curado

Parámetros: objetivo 2500 phishing y 2500 legítimos, máximo 2 correos por campaña, máximo 15 (phishing) y 60 (legítimos) por dominio remitente, semilla 42.

## Procesamiento por fuente

| Fuente | Clase | Leídos | duplicados | reservado_prueba | sin_cabeceras | cuerpo_vacio | etiqueta_excluida | idioma_fuera_de_alcance | spam_promocional | extorsion | sin_senuelo_claro | sin_vector | Válidos | Campañas | Disponibles | Seleccionados |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nazario | phishing | 1809 | 13 | 0 | 4 | 6 | 0 | 171 | 38 | 0 | 0 | 28 | 1549 | 1395 | 1452 | 1250 |
| phishing_pot | phishing | 12815 | 181 | 3 | 12 | 131 | 0 | 6520 | 1810 | 6 | 2313 | 58 | 1781 | 1304 | 1327 | 1250 |
| personal | legitimate | 4859 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4858 | 3519 | 2379 | 2379 |
| grupo | legitimate | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Composición del corpus seleccionado

| Fuente | Clase | Correos | % Received | % Auth-Results | % SPF pass | % DKIM pass | % HTML | Años |
|---|---|---|---|---|---|---|---|---|
| nazario | phishing | 1250 | 100% | 91% | 67% | 60% | 99% | 2020–2025 |
| phishing_pot | phishing | 1250 | 100% | 100% | 55% | 43% | 98% | 2020–2026 |
| personal | legitimate | 2379 | 100% | 100% | 100% | 98% | 100% | 2019–2026 |
| **TOTAL phishing** | phishing | 2500 | 100% | 95% | 61% | 52% | 98% | 2020–2026 |
| **TOTAL legitimate** | legitimate | 2379 | 100% | 100% | 100% | 98% | 100% | 2019–2026 |

## Phishing por tipo de señuelo e idioma

| Señuelo | Correos | en | es | pt |
|---|---|---|---|---|
| credenciales | 1254 | 1157 | 23 | 74 |
| pago_factura | 407 | 96 | 15 | 296 |
| otro | 234 | 214 | 15 | 5 |
| cripto | 227 | 222 | 5 | 0 |
| documento_compartido | 179 | 174 | 2 | 3 |
| entrega | 179 | 93 | 15 | 71 |
| suplantacion_bec | 20 | 20 | 0 | 0 |

## Muestra aleatoria para revisión manual (asuntos de phishing)

- [nazario · credenciales · en] About: Mail Account update Thursday, May 9, 2024 - 6597
- [nazario · credenciales · en] Notice: jose@monkey.org Verification Required
- [nazario · otro · en] Updated-Staffs-Information/Employee.xls 08/29/2024 01:22:52 am
- [nazario · credenciales · en] Approve sign in request
- [nazario · credenciales · en] Your jose@monkey.org Account has been disabled
- [nazario · otro · en] This email has been null routed due to recent spam reports!!
- [nazario · credenciales · en] New Mailbox Update in - jose@monkey.org
- [phishing_pot · credenciales · en] 𝐈𝐦𝐩𝐨𝐫𝐭𝐚𝐧𝐭 𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐅𝐨𝐫 𝐘𝐨𝐮 - 𝐎𝐩𝐞𝐧 𝐍𝐨𝐰!
- [nazario · credenciales · en] Your password will expire today!
- [phishing_pot · credenciales · en] phishing@pot has reached the quota limit
- [phishing_pot · credenciales · en] Action Required: Ledger Security Verification
- [nazario · credenciales · en] Login Expiry for ****@monkey.org / 2/18/2025 1:45:49 a.m.
- [nazario · credenciales · en] Your Package is ready for delivery!
- [nazario · credenciales · en] Action Required for 'Monkey.org ' address(es)
- [nazario · otro · es] Envio de Burofax Online - ultima advertencia - [ id 77106725 ]
- [nazario · otro · en] Extend your account for free
- [phishing_pot · entrega · pt] Tentativas de entrega esgotadas Problemas com documentação ou taxas ! Evite a devolucao. status — ID
- [phishing_pot · credenciales · en] New app has been connected to your Microsoft account
- [nazario · pago_factura · es] Multa Registrada en su Documento 136111
- [phishing_pot · entrega · en] 𝑯𝑰, 🚚⏳ 𝒀𝑶𝑼 𝑯𝑨𝑽𝑬 𝑷𝑬𝑵𝑫𝑰𝑵𝑮 𝑷𝑨𝑪𝑲𝑨𝑮𝑬 𝑳𝑨𝑺𝑻 𝑵𝑶𝑻𝑰𝑪𝑬 𝑻𝑶 𝑹𝑬𝑻𝑼𝑹𝑵 𝑹𝑬𝑷𝑳𝒀 𝑨𝑺𝑨𝑷✔️
- [nazario · credenciales · en] Mailbox Quota
- [phishing_pot · credenciales · pt] Viagem de Espiritualidade e Arqueologia
- [phishing_pot · pago_factura · pt] Regularização obrigatória: inconsistência na declaração - Ref: 01976905 / Divergência detectada no I
- [nazario · otro · en] New message
- [phishing_pot · credenciales · en] ⚠ Your Payment Method Has Expired – Action Required {CASE: 972-93950}
- [phishing_pot · pago_factura · pt] - Sua carteira de motorista esta prestes a ser suspensa - Protocolo - ID M3OWGRFR5O
- [nazario · documento_compartido · en] Completed Document: Complete with OneDrive : Signed Contract.pdf
- [nazario · credenciales · en] [Ticket ID:DFT-091-TBHhn4YtySF] IMPORTANT:Webmail Inbox - (19) Incoming failed messages in jose@monk
- [nazario · suplantacion_bec · en] One (1) Notification For Pending Undelivered Mails
- [phishing_pot · credenciales · es] Confirmación de sus datos de contacto para procesar su pago
- [phishing_pot · credenciales · en] Mail De-activation Request In Progress for phishing@pot
- [nazario · credenciales · en] Documents for Shipments no.-IN100679001BL PO£602102005
- [nazario · documento_compartido · en] remittance advce (aed)
- [nazario · otro · en] Incoming (14) Important Emails Failed to be delivered to jose@monkey.org
- [phishing_pot · pago_factura · pt] Notificação de Infração de Trânsito. ID: 50501631
- [nazario · otro · en] Erin Ellis sent you a message
- [nazario · credenciales · en] monkey.org - 29 August, 2024 20:58:29 PM
- [phishing_pot · pago_factura · pt] Aviso de vencimento: Fatura aguardando pagamento. Referência: 576796744
- [nazario · credenciales · en] 3 Messages FaiIed To DeIiver
- [phishing_pot · pago_factura · pt] Aviso de Penalidade: Suspensão de CNH em andamento. Referência: 514208405

## Fuentes

- **nazario**: Nazario, J. Phishing Corpus (CC-BY-4.0). https://monkey.org/~jose/phishing/
- **phishing_pot**: rf-peixoto. phishing_pot. https://github.com/rf-peixoto/phishing_pot
- **personal**: Buzón de Gmail del autor del repositorio, no publicado.
- **grupo**: Buzones de Gmail de los demás integrantes del grupo, no publicados.
