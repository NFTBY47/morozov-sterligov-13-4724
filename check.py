"""Готовый запуск одной работы. Не менять при выполнении лабораторной."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = argparse.ArgumentParser()
    parser.add_argument("lab", choices=[f"lab{i:02d}" for i in range(1, 7)])
    parser.add_argument("--bonus", action="store_true")
    args = parser.parse_args()
    lab = Path(__file__).resolve().parent / "labs" / args.lab
    if not lab.is_dir():
        parser.error("Эта работа ещё не выдана: папка отсутствует.")
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONUTF8"] = "1"
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTHONPATH", None)
    # Отдельный процесс исключает импорт app из другой работы.
    command = [sys.executable, "-m", "pytest", "-q", "tests"]
    result = subprocess.run(command, cwd=lab, env=env, check=False)
    if result.returncode or not args.bonus:
        return result.returncode
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "bonus_tests"],
        cwd=lab, env=env, check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
