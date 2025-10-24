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


def copy_dirs_structure(src_root: str, dst_root: str) -> int:
    if not os.path.isdir(src_root):
        raise ValueError(f"Ruta de origen inválida: {src_root}")

    os.makedirs(dst_root, exist_ok=True)

    created = 0
    src_root_norm = os.path.normpath(src_root)
    dst_root_norm = os.path.normpath(dst_root)

    for dirpath, dirs, _files in os.walk(src_root_norm):
        rel = os.path.relpath(dirpath, src_root_norm)
        if rel != ".":
            target_dir = os.path.join(dst_root_norm, rel)
            if not os.path.exists(target_dir):
                try:
                    os.makedirs(target_dir, exist_ok=True)
                    created += 1
                except Exception:
                    pass

        for d in dirs:
            sub_src = os.path.join(dirpath, d)
            rel_sub = os.path.relpath(sub_src, src_root_norm)
            sub_dst = os.path.join(dst_root_norm, rel_sub)
            if not os.path.exists(sub_dst):
                try:
                    os.makedirs(sub_dst, exist_ok=True)
                    created += 1
                except Exception:
                    pass

    return created


def _copy_full_dir(src_dir: str, dst_dir: str, skip_existing: bool = True) -> Tuple[int, int]:
    files_copied = 0
    dirs_created = 0

    for dirpath, dirs, files in os.walk(src_dir):
        rel = os.path.relpath(dirpath, src_dir)
        target_dir = os.path.join(dst_dir, rel) if rel != "." else dst_dir
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir, exist_ok=True)
                dirs_created += 1
            except Exception:
                pass

        for d in dirs:
            d_src = os.path.join(dirpath, d)
            rel_d = os.path.relpath(d_src, src_dir)
            d_dst = os.path.join(dst_dir, rel_d)
            if not os.path.exists(d_dst):
                try:
                    os.makedirs(d_dst, exist_ok=True)
                    dirs_created += 1
                except Exception:
                    pass

        for f in files:
            s = os.path.join(dirpath, f)
            rel_f = os.path.relpath(s, src_dir)
            d = os.path.join(dst_dir, rel_f)
            try:
                if skip_existing and os.path.exists(d):
                    continue
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
                files_copied += 1
            except Exception:
                pass

    return files_copied, dirs_created


def copy_empresas_mixed(emp_src: str, emp_dst: str, reportes_name: str = "Reportes", skip_existing: bool = True) -> Tuple[int, int, int]:
    if not os.path.isdir(emp_src):
        raise ValueError(f"Ruta de empresas inválida: {emp_src}")

    os.makedirs(emp_dst, exist_ok=True)

    files_copied_reportes = 0
    dirs_created_reportes = 0
    dirs_structured_empresas = 0

    for name in os.listdir(emp_src):
        src_path = os.path.join(emp_src, name)
        dst_path = os.path.join(emp_dst, name)

        if os.path.isdir(src_path):
            if name.lower() == reportes_name.lower():
                fc, dc = _copy_full_dir(src_path, dst_path, skip_existing=skip_existing)
                files_copied_reportes += fc
                dirs_created_reportes += dc
            else:
                try:
                    dirs_structured_empresas += copy_dirs_structure(src_path, dst_path)
                except Exception:
                    pass
        else:
            continue

    return files_copied_reportes, dirs_created_reportes, dirs_structured_empresas
