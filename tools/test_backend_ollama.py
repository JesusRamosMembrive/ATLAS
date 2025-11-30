# SPDX-License-Identifier: MIT
"""
Utilidad de línea de comandos para probar el endpoint
`/integrations/ollama/test` sin necesidad de usar la UI.

Ejemplo:
    python tools/test_backend_ollama.py \
        --api http://127.0.0.1:8010 \
        --model gpt-oss:latest \
        --prompt "Ping de prueba"
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx

DEFAULT_API_BASE = "http://127.0.0.1:8010"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lanza un ping contra el endpoint /integrations/ollama/test del backend."
    )
    parser.add_argument(
        "--api",
        default=DEFAULT_API_BASE,
        help="URL base del backend (por defecto %(default)s)",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Nombre del modelo que quieres probar (ej. 'gpt-oss:latest').",
    )
    parser.add_argument(
        "--prompt",
        default="Di 'pong' si recibiste este mensaje.",
        help="Mensaje que se enviará al modelo.",
    )
    parser.add_argument(
        "--system-prompt",
        default=None,
        help="System prompt opcional a enviar junto al mensaje de usuario.",
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="Endpoint alternativo de Ollama (si se deja vacío, el backend usa el detectado).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Tiempo máximo de espera en segundos (vacío usa el valor por defecto del backend).",
    )
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    api_base = args.api.rstrip("/")
    url = f"{api_base}/integrations/ollama/test"

    payload: dict[str, object] = {
        "model": args.model,
        "prompt": args.prompt,
    }
    if args.system_prompt:
        payload["system_prompt"] = args.system_prompt
    if args.endpoint:
        payload["endpoint"] = args.endpoint
    if args.timeout:
        payload["timeout_seconds"] = args.timeout

    print(f"POST {url}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    start = time.perf_counter()
    timeout = args.timeout or 120.0
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        if response.status_code >= 400:
            print(f"\n⚠️  Respuesta HTTP {response.status_code} en {latency_ms:.0f} ms")
            try:
                detail = response.json()
                print(json.dumps(detail, ensure_ascii=False, indent=2))
            except json.JSONDecodeError:
                print(response.text or "(sin detalle)")
            return 2

        print(f"\n✅ Respuesta {response.status_code} en {latency_ms:.0f} ms")
        try:
            parsed = response.json()
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(response.text or "(sin cuerpo)")
        return 0
    except httpx.RequestError as exc:
        print(f"\n❌ Error de transporte: {exc}")
        return 3


if __name__ == "__main__":  # pragma: no cover - utilidad CLI
    sys.exit(run())
