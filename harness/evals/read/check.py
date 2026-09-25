import re
import sys
from pathlib import Path

report = Path(sys.argv[2]).read_text(encoding="utf-8")
assert re.search(r"(?m)^判定: ALLOW\s*$", report)
assert re.search(r"(?m)^理由: -n は dry-run\s*$", report)
