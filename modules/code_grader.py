"""
modules/code_grader.py — M4b (grading)
Grade user code against predefined test cases.
"""
from dataclasses import dataclass
from modules.code_sandbox import run_c, run_python, RunResult
from utils.db_schema import get_connection
from datetime import datetime


@dataclass
class TestCase:
    stdin: str
    expected_stdout: str
    description: str = ""


@dataclass
class GradeResult:
    passed: int
    total: int
    details: list[dict]   # [{description, stdin, expected, actual, passed, elapsed_ms}]
    score: float          # 0.0 – 100.0

    @property
    def all_passed(self) -> bool:
        return self.passed == self.total


def grade(
    code: str,
    test_cases: list[TestCase],
    lang: str = "cpp",
    subject_id: str = "dsa",
) -> GradeResult:
    """Run code against all test cases and return grading result."""
    details = []
    passed = 0

    for tc in test_cases:
        if lang in ("c", "cpp"):
            result: RunResult = run_c(code, stdin=tc.stdin, lang=lang)
        else:
            result: RunResult = run_python(code, stdin=tc.stdin)

        actual = result.stdout.strip()
        expected = tc.expected_stdout.strip()
        ok = actual == expected and result.success

        if ok:
            passed += 1

        details.append({
            "description": tc.description,
            "stdin":       tc.stdin,
            "expected":    expected,
            "actual":      actual,
            "passed":      ok,
            "elapsed_ms":  result.elapsed_ms,
            "stderr":      result.stderr,
        })

    total = len(test_cases)
    score = (passed / total * 100) if total > 0 else 0.0
    grade_result = GradeResult(passed=passed, total=total, details=details, score=score)

    _save(code, grade_result, lang, subject_id)
    return grade_result


def _save(code: str, result: GradeResult, lang: str, subject_id: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO code_runs "
        "(timestamp, subject_id, lang, code, stdin, stdout, stderr, elapsed_ms, passed_cases, total_cases) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now().isoformat(), subject_id, lang, code,
            "", str(result.score), "", 0.0,
            result.passed, result.total,
        )
    )
    conn.commit()
    conn.close()
