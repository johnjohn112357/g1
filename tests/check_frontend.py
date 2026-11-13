import re
from pathlib import Path
html=Path("static/index.html").read_text()
scripts=re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",html,re.S)
inline=[x for x in scripts if x.strip()]
if not inline:raise SystemExit("No inline JavaScript found")
Path("/tmp/giw-inline.js").write_text("\n".join(inline))
print("Extracted",len(inline),"inline script(s)")
