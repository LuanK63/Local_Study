"""
modules/code_sandbox.py — M4b
Compile and run C/C++ (via GCC/G++) or Python code safely with timeout.
Uses portable GCC bundled with the app (data/gcc/) or system GCC.
"""
import subprocess
import tempfile
import os
import time
import shutil
from pathlib import Path
from dataclasses import dataclass
from utils.config import get_config


_UNBUFFER_SRC = Path(__file__).parent / "sandbox_unbuffer.c"


@dataclass
class RunResult:
    stdout: str
    stderr: str
    elapsed_ms: float
    exit_code: int
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def _find_compiler(lang: str) -> str:
    """Find GCC/G++ — prefer bundled portable version."""
    cfg = get_config()
    if lang == "c":
        bundled = Path("data/gcc/bin/gcc.exe")
        return str(bundled) if bundled.exists() else cfg["sandbox"]["gcc_path"]
    else:
        bundled = Path("data/gcc/bin/g++.exe")
        return str(bundled) if bundled.exists() else cfg["sandbox"]["gpp_path"]


def run_c(code: str, stdin: str = "", lang: str = "cpp") -> RunResult:
    """Compile and run C or C++ code. lang = 'c' | 'cpp'"""
    timeout = get_config()["sandbox"]["timeout_seconds"]
    ext = ".c" if lang == "c" else ".cpp"
    compiler = _find_compiler(lang)

    with tempfile.TemporaryDirectory(prefix="sandbox_") as tmpdir:
        src = os.path.join(tmpdir, f"main{ext}")
        exe = os.path.join(tmpdir, "main.exe")

        with open(src, "w", encoding="utf-8") as f:
            f.write(code)

        # Compile
        compile_result = subprocess.run(
            [compiler, src, "-o", exe, "-Wall", "-O2", "-lm"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=30, cwd=tmpdir
        )
        if compile_result.returncode != 0:
            return RunResult(
                stdout="", stderr=compile_result.stderr,
                elapsed_ms=0, exit_code=compile_result.returncode
            )

        # Run
        start = time.perf_counter()
        try:
            run_result = subprocess.run(
                [exe],
                input=stdin, capture_output=True, encoding="utf-8", errors="replace",
                timeout=timeout, cwd=tmpdir
            )
            elapsed = (time.perf_counter() - start) * 1000
            return RunResult(
                stdout=run_result.stdout[:get_config()["sandbox"]["max_output_chars"]],
                stderr=run_result.stderr,
                elapsed_ms=round(elapsed, 2),
                exit_code=run_result.returncode,
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.perf_counter() - start) * 1000
            return RunResult(
                stdout="", stderr=f"[Timeout] Chương trình chạy quá {timeout}s",
                elapsed_ms=round(elapsed, 2), exit_code=-1, timed_out=True
            )


def compile_c(code: str, lang: str = "cpp") -> tuple[str, str, str]:
    """Compile C/C++ to an exe. Returns (exe_path, tmpdir, error_msg)."""
    ext = ".c" if lang == "c" else ".cpp"
    compiler = _find_compiler(lang)

    tmpdir = tempfile.mkdtemp(prefix="sandbox_interactive_")
    src = os.path.join(tmpdir, f"main{ext}")
    exe = os.path.join(tmpdir, "main.exe")

    try:
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)

        compile_cmd = [compiler, src]
        if _UNBUFFER_SRC.exists():
            compile_cmd.append(str(_UNBUFFER_SRC))
        compile_cmd.extend(["-o", exe, "-Wall", "-O2", "-lm"])

        compile_result = subprocess.run(
            compile_cmd,
            capture_output=True, encoding="utf-8", errors="replace", timeout=30, cwd=tmpdir
        )
        if compile_result.returncode != 0:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return "", "", compile_result.stderr
        return exe, tmpdir, ""
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return "", "", f"Lỗi biên dịch: {e}"


def prepare_python(code: str) -> tuple[str, str, str]:
    """Validate and save Python source to a temp file. Returns (py_path, tmpdir, error_msg)."""
    blocked = ["import os", "import sys", "import socket", "import subprocess",
               "import shutil", "__import__"]
    for b in blocked:
        if b in code:
            return "", "", f"[BLOCKED] '{b}' không được phép trong sandbox"

    tmpdir = tempfile.mkdtemp(prefix="sandbox_interactive_")
    src = os.path.join(tmpdir, "main.py")
    try:
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)
        return src, tmpdir, ""
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return "", "", f"Lỗi tạo tệp tạm: {e}"


def run_python(code: str, stdin: str = "") -> RunResult:
    """Run Python code safely."""
    timeout = get_config()["sandbox"]["timeout_seconds"]
    blocked = ["import os", "import sys", "import socket", "import subprocess",
               "import shutil", "__import__"]
    for b in blocked:
        if b in code:
            return RunResult(
                stdout="", stderr=f"[BLOCKED] '{b}' không được phép trong sandbox",
                elapsed_ms=0, exit_code=-1
            )

    with tempfile.TemporaryDirectory(prefix="sandbox_") as tmpdir:
        src = os.path.join(tmpdir, "main.py")
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)

        start = time.perf_counter()
        try:
            import sys
            env = {**os.environ, "PYTHONUTF8": "1"}
            result = subprocess.run(
                [sys.executable or "python", src],
                input=stdin, capture_output=True, encoding="utf-8", errors="replace",
                env=env, timeout=timeout, cwd=tmpdir
            )
            elapsed = (time.perf_counter() - start) * 1000
            return RunResult(
                stdout=result.stdout[:5000], stderr=result.stderr,
                elapsed_ms=round(elapsed, 2), exit_code=result.returncode
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.perf_counter() - start) * 1000
            return RunResult(
                stdout="", stderr=f"[Timeout] Chương trình chạy quá {timeout}s",
                elapsed_ms=round(elapsed, 2), exit_code=-1, timed_out=True
            )
