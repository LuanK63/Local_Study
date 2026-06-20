"""
utils/system_info.py
Utility module to collect hardware and software metadata for reproducibility of RAG benchmarks.
"""
import subprocess
import platform
import socket

def get_git_commit_hash() -> str:
    try:
        # Run git rev-parse HEAD to get current commit hash
        return subprocess.check_output("git rev-parse HEAD", shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""

def get_machine_name() -> str:
    try:
        return socket.gethostname()
    except Exception:
        node = platform.node()
        return node if node else ""

def get_gpu_name() -> str:
    try:
        # Try PowerShell Get-CimInstance first
        out = subprocess.check_output('powershell -Command "(Get-CimInstance Win32_VideoController).Name"', shell=True, stderr=subprocess.DEVNULL).decode().strip()
        if out:
            names = [line.strip() for line in out.splitlines() if line.strip()]
            if names:
                return ", ".join(names)
    except Exception:
        pass
    try:
        # Fallback to WMIC
        out = subprocess.check_output("wmic path win32_VideoController get name", shell=True, stderr=subprocess.DEVNULL).decode().strip().splitlines()
        gpus = [line.strip() for line in out[1:] if line.strip()]
        if gpus:
            return ", ".join(gpus)
    except Exception:
        pass
    return ""

def get_ram_gb() -> int:
    try:
        # Try WMIC total physical memory
        out = subprocess.check_output("wmic computersystem get totalphysicalmemory", shell=True, stderr=subprocess.DEVNULL).decode().strip().splitlines()
        bytes_val = int(out[1].strip())
        return round(bytes_val / (1024**3))
    except Exception:
        pass
    try:
        # Try PowerShell TotalVisibleMemorySize
        out = subprocess.check_output('powershell -Command "[Math]::Round((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize / 1024 / 1024)"', shell=True, stderr=subprocess.DEVNULL).decode().strip()
        if out:
            return int(out)
    except Exception:
        pass
    return 0

def get_ollama_version() -> str:
    try:
        # Try running ollama --version
        out = subprocess.check_output("ollama --version", shell=True, stderr=subprocess.DEVNULL).decode().strip()
        if out:
            # Example: "ollama version is 0.3.10" or similar
            return out.replace("ollama version is", "").strip()
    except Exception:
        pass
    try:
        # Fallback: Query local Ollama API if it is running
        import httpx
        resp = httpx.get("http://localhost:11434/api/version", timeout=2)
        if resp.status_code == 200:
            return resp.json().get("version", "")
    except Exception:
        pass
    return ""

def get_os_version() -> str:
    try:
        return f"{platform.system()} {platform.release()} (Version: {platform.version()})"
    except Exception:
        return ""

def collect_system_metadata() -> dict:
    """
    Collects system metadata required for RAG benchmark reproducibility.
    Returns a dictionary of:
    - git_commit_hash
    - machine_name
    - gpu_name
    - ram_gb
    - ollama_version
    - os_version
    """
    return {
        "git_commit_hash": get_git_commit_hash(),
        "machine_name": get_machine_name(),
        "gpu_name": get_gpu_name(),
        "ram_gb": get_ram_gb(),
        "ollama_version": get_ollama_version(),
        "os_version": get_os_version()
    }
