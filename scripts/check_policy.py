"""Проверка правил проекта (Lab 3, п. 14), запускается первой в `make verify`.

Запрещено без обоснования:
  * пропускать тесты (skip / skipif / xfail / pytest.skip / importorskip);
  * снижать порог покрытия ниже MIN_COVERAGE;
  * отключать проверки анализаторов комментариями (# noqa, # nosec,
    # pragma: no cover, # type: ignore) без пояснения после «--».

Пример допустимого исключения:
    from app import models  # noqa: F401 -- импорт регистрирует модели
"""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_COVERAGE = 85
SCANNED_DIRS = ("app", "tests", "alembic", "scripts")

SKIP_PATTERNS = re.compile(
    r"pytest\.mark\.(skip|skipif|xfail)\b|pytest\.(skip|xfail|importorskip)\("
)
SUPPRESSION = re.compile(r"#\s*(noqa|nosec|pragma:\s*no\s*cover|type:\s*ignore)\b")
JUSTIFIED = re.compile(r"--\s*\S.{4,}")


def python_files():
    for folder in SCANNED_DIRS:
        for path in sorted((ROOT / folder).rglob("*.py")):
            if path.resolve() != Path(__file__).resolve():
                yield path


def check_sources() -> list[str]:
    errors = []
    for path in python_files():
        rel = path.relative_to(ROOT)
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if rel.parts[0] == "tests" and SKIP_PATTERNS.search(line):
                errors.append(f"{rel}:{lineno}: пропуск тестов запрещён")
            match = SUPPRESSION.search(line)
            if match and not JUSTIFIED.search(line[match.end() :]):
                errors.append(
                    f"{rel}:{lineno}: «{match.group(0)}» без обоснования "
                    "(добавьте «-- причина»)"
                )
    return errors


def check_thresholds() -> list[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    fail_under = config["tool"]["coverage"]["report"].get("fail_under", 0)
    errors = []
    if fail_under < MIN_COVERAGE:
        errors.append(
            f"pyproject.toml: coverage fail_under={fail_under} < {MIN_COVERAGE}"
        )
    banned_options = re.compile(r"--cov-fail-under|--no-cov|--deselect|--ignore")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    if banned_options.search(makefile):
        errors.append("Makefile: запрещено переопределять порог/отбор тестов")
    addopts = " ".join(config["tool"]["pytest"]["ini_options"].get("addopts", []))
    if banned_options.search(addopts) or "--cov=app" not in addopts:
        errors.append(
            "pyproject.toml: addopts должны включать --cov=app без исключений"
        )
    return errors


def main() -> int:
    errors = check_sources() + check_thresholds()
    for error in errors:
        print(f"POLICY: {error}")
    if errors:
        print(f"Нарушений политики: {len(errors)} (см. CONTRIBUTING.md)")
        return 1
    print("Политика проверок соблюдена.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
