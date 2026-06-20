import subprocess
import tempfile
import os

def test():
    tmpdir = tempfile.mkdtemp()
    src = os.path.join(tmpdir, "main.cpp")
    exe = os.path.join(tmpdir, "main.exe")
    code = """#include <iostream>
using namespace std;
int main() {
    cout << "Hello, xin chào";
    return 0;
}
"""
    with open(src, "w", encoding="utf-8") as f:
        f.write(code)

    # Compile
    comp = subprocess.run(
        ["g++", src, "-o", exe],
        capture_output=True,
        encoding="utf-8",
        errors="replace"
    )

    # Run
    res = subprocess.run(
        [exe],
        capture_output=True,
        encoding="utf-8",
        errors="replace"
    )
    print("Decoded stdout length:", len(res.stdout))
    for char in res.stdout:
        print(f"Char: {repr(char)}, Codepoint: {hex(ord(char))}")

if __name__ == "__main__":
    test()
