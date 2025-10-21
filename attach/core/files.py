import os
import shutil
from typing import List, Tuple

def copy_data_tree(src_dir: str, dst_dir: str, skip_existing: bool = True) -> List[Tuple[str, str]]:
    os.makedirs(dst_dir, exist_ok=True)
    copied: List[Tuple[str, str]] = []

    for root, _, files in os.walk(src_dir):
        for name in files:
            lower = name.lower()
            if not (lower.endswith(".mdf") or lower.endswith(".ldf")):
                continue

            src_path = os.path.normpath(os.path.join(root, name))
            dst_path = os.path.normpath(os.path.join(dst_dir, name))

            try:
                if skip_existing and os.path.exists(dst_path):
                    continue
                shutil.copy2(src_path, dst_path)
                copied.append((src_path, dst_path))
            except Exception:
                continue

    return copied
