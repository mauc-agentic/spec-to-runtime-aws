"""Métricas propias con el formato embebido de CloudWatch (EMF).

Basta con escribir una línea JSON en el log de la Lambda: CloudWatch la convierte en métricas sin
llamar a ninguna API ni pagar por PutMetricData. Se mantienen pocas métricas y una sola dimensión
para no pasarse del presupuesto (cada combinación métrica-dimensión es una métrica personalizada).
"""

import json
import sys
import time

NAMESPACE = "SpecToRuntime"


def emit(
    metrics: dict[str, tuple[float, str]],
    dimensions: dict[str, str] | None = None,
    properties: dict | None = None,
) -> str:
    """Escribe una línea EMF y la devuelve. `metrics` es {nombre: (valor, unidad)}."""
    dimensions = dimensions or {}
    record = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": NAMESPACE,
                    "Dimensions": [list(dimensions)],
                    "Metrics": [
                        {"Name": name, "Unit": unit} for name, (_, unit) in metrics.items()
                    ],
                }
            ],
        },
        **dimensions,
        **{name: value for name, (value, _) in metrics.items()},
        # Propiedades sin dimensión: no crean métricas, pero se pueden buscar en Logs Insights.
        **(properties or {}),
    }
    line = json.dumps(record, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    return line
