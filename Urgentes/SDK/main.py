import os
from pathlib import Path

cands = [
    r"C:\ProgramData\Compac\CAC",
    r"C:\Windows",
    r"C:\Program Files (x86)\Compac\COMERCIAL",
    r"C:\Compac\COMERCIAL",
    r"C:\Compac\Comercial",
    os.getcwd(),
]
found = []
for base in cands:
    p = Path(base) / "CAC.ini"
    if p.is_file(): found.append(str(p))
print("Posibles CAC.ini:")
for f in found: print("  ", f)
