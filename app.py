from __future__ import annotations

import argparse
import time
from pathlib import Path

from core.runtime import relaunch_in_project_venv


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memecoin Early-Warning Radar")
    parser.add_argument("--once", action="store_true", help="Ejecuta un solo ciclo")
    return parser.parse_args()


def main() -> int:
    relaunch_in_project_venv(PROJECT_ROOT)
    from core.config import ConfigError, load_settings
    from radar import Radar

    args = parse_args()
    try:
        settings = load_settings()
        radar = Radar(settings)
    except ConfigError as exc:
        print(f"[config] {exc}")
        return 2
    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"[radar] ciclo {cycle}")
            radar.run_cycle()
            if args.once:
                return 0
            seconds = int(settings["poll_seconds"])
            print(f"[sleep] {seconds}s")
            time.sleep(seconds)
    except KeyboardInterrupt:
        print("\n[radar] detenido limpiamente")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
