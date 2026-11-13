from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.runtime import relaunch_in_project_venv  # noqa: E402

relaunch_in_project_venv(ROOT)

from core.config import load_settings  # noqa: E402
from models.schemas import Candidate  # noqa: E402
from radar import Radar  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Analiza un mint de Solana inmediatamente")
    parser.add_argument("mint", help="Dirección del token")
    parser.add_argument("--no-llm", action="store_true", help="No fuerza análisis con Ollama")
    args = parser.parse_args()
    settings = load_settings(ROOT)
    if args.no_llm:
        settings["ollama"]["enabled"] = False
    radar = Radar(settings)
    result = radar.analyze_token(
        Candidate(network=settings["network"], address=args.mint, sources=["manual_cli"]),
        force_llm=not args.no_llm,
    )
    if result is None:
        print("No se encontró un par válido para el token.")
        return 1
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
