#!/usr/bin/env python3
"""Muestra una traza de punta a punta como árbol de spans, con el tiempo de cada tramo.

Lee los spans de CloudWatch Logs (`aws/spans`, Transaction Search). Sirve para enseñar en la charla
por dónde pasó una pregunta: orquestador -> agente -> búsqueda en el repositorio -> memoria -> modelo.

SQS no continúa la traza de quien envía el mensaje: la ENLAZA. Por eso una pregunta son dos trazas
(la de la Lambda `api` y la del orquestador con el agente); este script sigue el enlace y muestra las dos.

Uso:
  uv run python scripts/show_trace.py                        # la última pregunta
  uv run python scripts/show_trace.py --request-id 1790...-ab12
  uv run python scripts/show_trace.py --trace-id 1-5759e988-bd862e3fe1be46a994272793
Los spans tardan 1 o 2 minutos en aparecer después de la pregunta.
"""

import argparse
import json
import sys
import time

import boto3

REGION = "us-east-1"
SHOWN_ATTRIBUTES = (
    "app.outcome", "app.profile", "app.role", "app.request_id", "app.passages", "app.top_score",
    "app.citations", "app.input_tokens", "app.output_tokens", "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens",
)  # fmt: skip


def w3c_id(trace_id: str) -> str:
    """1-5759e988-bd862e3fe1be46a994272793 -> 5759e988bd862e3fe1be46a994272793."""
    return trace_id.replace("1-", "", 1).replace("-", "") if trace_id.startswith("1-") else trace_id


def latest_trace_id(request_id: str | None) -> str:
    table = boto3.resource("dynamodb", region_name=REGION).Table("spec-to-runtime-requests")
    items = [i for i in table.scan()["Items"] if i.get("trace_id")]
    if request_id:
        items = [i for i in items if i["request_id"] == request_id]
    if not items:
        sys.exit("No hay preguntas con traza registrada. Haz una pregunta y espera un minuto.")
    return max(items, key=lambda i: i["created_at"])["trace_id"]


def fetch_spans(trace_id: str, wait_seconds: int = 240) -> list[dict]:
    """Consulta `aws/spans` hasta que aparezcan spans de la traza (tardan un poco en ingerirse)."""
    logs = boto3.client("logs", region_name=REGION)
    deadline = time.time() + wait_seconds
    while True:
        end = int(time.time())
        query = logs.start_query(
            logGroupName="aws/spans", startTime=end - 6 * 3600, endTime=end + 60,
            queryString=f'fields @message | filter traceId = "{w3c_id(trace_id)}" | limit 400',
        )  # fmt: skip
        while (result := logs.get_query_results(queryId=query["queryId"]))["status"] in (
            "Running",
            "Scheduled",
        ):
            time.sleep(1)
        spans = [
            json.loads(next(f["value"] for f in row if f["field"] == "@message"))
            for row in result["results"]
        ]
        # Un span en curso llega sin duración y luego otra vez completo: se queda con el completo.
        best: dict[str, dict] = {}
        for span in spans:
            if span["spanId"] not in best or span.get("durationNano"):
                best[span["spanId"]] = span
        if best or time.time() > deadline:
            return list(best.values())
        print("  (esperando a que lleguen los spans…)", file=sys.stderr)
        time.sleep(15)


def service_of(span: dict) -> str:
    resource = span.get("resource", {}).get("attributes", {})
    return resource.get("service.name") or span.get("attributes", {}).get("aws.local.service", "")


def linked_traces(spans: list[dict]) -> list[str]:
    ids = []
    for span in spans:
        for link in span.get("links") or []:
            if link["traceId"] not in ids and link["traceId"] != span["traceId"]:
                ids.append(link["traceId"])
    return ids


def render(spans: list[dict]) -> str:
    known = {s["spanId"] for s in spans}
    children: dict[str, list[dict]] = {}
    for span in spans:
        parent = span.get("parentSpanId") or ""
        children.setdefault(parent if parent in known else "", []).append(span)
    started = [int(s.get("startTimeUnixNano") or 0) for s in spans if s.get("startTimeUnixNano")]
    origin = min(started) if started else 0
    lines: list[str] = []

    def walk(parent: str, depth: int) -> None:
        for span in sorted(
            children.get(parent, []), key=lambda s: int(s.get("startTimeUnixNano") or 0)
        ):
            name = span.get("name") or "(cola SQS)"
            service = service_of(span)
            label = f"{'  ' * depth}{name}" + (
                f"  [{service}]" if service and service not in name else ""
            )
            offset = (int(span.get("startTimeUnixNano") or origin) - origin) / 1e6
            duration = int(span["durationNano"]) / 1e6 if span.get("durationNano") else None
            timing = f"+{offset:7.0f} ms  " + (
                f"{duration:7.0f} ms" if duration is not None else "   en curso"
            )
            attrs = span.get("attributes", {})
            extra = "  " + " ".join(
                f"{k.removeprefix('app.')}={attrs[k]}" for k in SHOWN_ATTRIBUTES if k in attrs
            )
            lines.append(f"{label:<74} {timing}{extra.rstrip()}")
            walk(span["spanId"], depth + 1)

    walk("", 0)
    return "\n".join(lines)


def show(trace_id: str, title: str, follow: bool) -> None:
    spans = fetch_spans(trace_id)
    if not spans:
        print(
            f"{title} {trace_id}: todavía sin spans (Transaction Search puede tardar un par de minutos)."
        )
        return
    print(
        f"\n{title}  {trace_id}  ({len(spans)} spans)\n{'span':<74} {'inicio':>11}  {'duración':>10}\n{render(spans)}"
    )
    if follow:
        for other in linked_traces(spans):
            other_id = f"1-{other[:8]}-{other[8:]}"
            show(other_id, "Traza enlazada", follow=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--request-id")
    parser.add_argument("--trace-id")
    args = parser.parse_args()
    show(args.trace_id or latest_trace_id(args.request_id), "Traza", follow=True)


if __name__ == "__main__":
    main()
