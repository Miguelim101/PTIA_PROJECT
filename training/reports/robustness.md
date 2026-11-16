# Robustez de las métricas

MLP (22 entradas, capas [64, 32], Dropout 0.3, L2 0.01, lr 0.001, lotes de 128, umbral 0.5) entrenado con 5 particiones 80/10/10 distintas, estratificadas y agrupadas por dominio remitente. Métricas en el conjunto de prueba de cada partición.

| Partición | Exactitud | Precisión | Recall | F1 | AUC | Falsos positivos | Falsos negativos |
|---|---|---|---|---|---|---|---|
| 42 | 94.7% | 96.3% | 93.2% | 0.947 | 0.979 | 9 | 17 |
| 1 | 95.3% | 96.3% | 94.4% | 0.954 | 0.990 | 9 | 14 |
| 2 | 94.1% | 95.1% | 93.2% | 0.941 | 0.986 | 12 | 17 |
| 3 | 94.0% | 95.5% | 92.8% | 0.941 | 0.990 | 11 | 18 |
| 4 | 95.3% | 96.3% | 94.4% | 0.954 | 0.989 | 9 | 14 |
| **Media ± desv.** | 94.7% ± 0.6% | 95.9% ± 0.6% | 93.6% ± 0.7% | 0.947 ± 0.006 | 0.987 ± 0.005 | | |
