import runpy
import subprocess
import sys
from pathlib import Path

root, report = map(Path, sys.argv[1:3])
assert report.is_file()
subprocess.run([sys.executable, "-B", "harness/evals/fix/test_total.py"], cwd=root, check=True, timeout=15)
total = runpy.run_path(str(root / "harness/evals/fix/total.py"))["total"]
assert total([5]) == 5
assert total([-2, 4, 7]) == 9
