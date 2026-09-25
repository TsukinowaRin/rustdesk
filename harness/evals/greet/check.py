import runpy
import subprocess
import sys
from pathlib import Path

root, report = map(Path, sys.argv[1:3])
assert report.is_file()
assert (root / "test_hello.py").is_file()
assert runpy.run_path(str(root / "hello.py"))["greet"]("Ada") == "Hello, Ada!"
subprocess.run([sys.executable, "-B", "test_hello.py"], cwd=root, check=True, timeout=15)
