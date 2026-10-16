"""Простое мутационное тестирование бизнес-логики (Lab 3, п. 5).

Скрипт по одному вносит в код «мутации» — ровно то, что делает преподаватель
на защите: меняет условие (`<` -> `<=`, `!=` -> `==`, `not in` -> `in`),
статус (`ACTIVE` -> `PLANNED`), число, константу шага ставки и т.д. — и
запускает тесты. Мутант «убит», если хотя бы один тест упал. Выживший мутант
означает, что изменение логики тестами не замечено.

Запуск: make mutation            (все файлы из TARGETS)
        python scripts/mutation_check.py app/services.py
Исходные файлы всегда восстанавливаются (в том числе при Ctrl+C).

Строка с комментарием «# no-mutate -- причина» не мутируется: так помечаются
только эквивалентные мутанты (изменение, не меняющее поведение программы).
"""

import io
import subprocess  # nosec B404 # -- запускаем только pytest с фиксированными аргументами
import sys
import time
import tokenize
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ["app/services.py", "app/auth.py"]
PYTEST = [
    sys.executable,
    "-m",
    "pytest",
    "-x",
    "-q",
    "-o",
    "addopts=",
    "-p",
    "no:cacheprovider",
    "tests",
]

OPERATOR_SWAPS = {
    "<": "<=",
    "<=": "<",
    ">": ">=",
    ">=": ">",
    "==": "!=",
    "!=": "==",
    "+": "-",
    "-": "+",
}
STATUS_SWAPS = {
    "PLANNED": "ACTIVE",
    "ACTIVE": "PLANNED",
    "FINISHED": "CANCELLED",
    "CANCELLED": "FINISHED",
    "AVAILABLE": "SOLD",
    "SOLD": "UNSOLD",
    "UNSOLD": "AVAILABLE",
}
CONSTANT_SWAPS = {'"100.00"': '"99.00"', "True": "False", "False": "True"}


@dataclass
class Mutant:
    path: Path
    line: int
    col: int
    old: str
    new: str

    def apply(self, source: str) -> str:
        lines = source.splitlines(keepends=True)
        text = lines[self.line - 1]
        if text[self.col : self.col + len(self.old)] != self.old:
            raise RuntimeError(
                f"Мутация не совпала с исходным кодом: {self.describe()}"
            )
        lines[self.line - 1] = (
            text[: self.col] + self.new + text[self.col + len(self.old) :]
        )
        return "".join(lines)

    def describe(self) -> str:
        rel = self.path.relative_to(ROOT)
        return f"{rel}:{self.line}: {self.old!r} -> {self.new!r}"


def generate(path: Path) -> list[Mutant]:
    source = path.read_text(encoding="utf-8")
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    skip_lines = set()
    for n, text in enumerate(source.splitlines(), 1):
        if "# no-mutate --" in text:
            # комментарий на отдельной строке относится к следующей строке кода
            skip_lines.add(n + 1 if text.lstrip().startswith("#") else n)
    mutants = []
    for i, tok in enumerate(tokens):
        (line, col), text = tok.start, tok.string
        if line in skip_lines:
            continue
        if tok.type == tokenize.OP and text in OPERATOR_SWAPS:
            if text in "+-" and tokens[i - 1].type == tokenize.OP:
                continue  # унарный минус/плюс
            mutants.append(Mutant(path, line, col, text, OPERATOR_SWAPS[text]))
        elif tok.type == tokenize.NAME and text == "not":
            nxt = tokens[i + 1]
            if nxt.string == "in":
                mutants.append(Mutant(path, line, col, "not in", "in"))
        elif tok.type == tokenize.NAME and text in STATUS_SWAPS:
            if tokens[i - 1].string == ".":
                mutants.append(Mutant(path, line, col, text, STATUS_SWAPS[text]))
        elif text in CONSTANT_SWAPS and tok.type in (tokenize.STRING, tokenize.NAME):
            mutants.append(Mutant(path, line, col, text, CONSTANT_SWAPS[text]))
        elif tok.type == tokenize.NUMBER and text.isdigit():
            mutants.append(Mutant(path, line, col, text, str(int(text) + 1)))
    return mutants


def run_tests() -> bool:
    result = (
        subprocess.run(  # nosec B603 # -- argv фиксирован, без shell и внешнего ввода
            PYTEST, cwd=ROOT, capture_output=True, text=True, timeout=300, check=False
        )
    )
    return result.returncode == 0


def main(argv: list[str]) -> int:
    targets = [ROOT / t for t in (argv or TARGETS)]
    print("Контрольный прогон тестов без мутаций...")
    if not run_tests():
        print("Тесты падают и без мутаций — сначала почините их.")
        return 2

    survived, total, started = [], 0, time.monotonic()
    for path in targets:
        original = path.read_text(encoding="utf-8")
        try:
            for mutant in generate(path):
                total += 1
                path.write_text(mutant.apply(original), encoding="utf-8")
                killed = not run_tests()
                print(("  убит    " if killed else "  ВЫЖИЛ   ") + mutant.describe())
                if not killed:
                    survived.append(mutant)
        finally:
            path.write_text(original, encoding="utf-8")

    killed = total - len(survived)
    score = 100 * killed / total if total else 100
    elapsed = time.monotonic() - started
    print(f"\nМутантов: {total}, убито: {killed}, выжило: {len(survived)}")
    print(f"Mutation score: {score:.1f}% ({elapsed:.0f} с)")
    for mutant in survived:
        print(f"  выжил: {mutant.describe()}")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
