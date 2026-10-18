"""Package the optimized project into a clean ZIP."""
import os
import shutil
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "python-constraint-opt")
STAGE = os.path.join(ROOT, "dist", "python-constraint-opt")
ZIP = os.path.join(ROOT, "dist", "python-constraint-optimized.zip")

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".benchmarks", ".vscode",
             ".mypy_cache", "build", "dist", ".ruff_cache"}
# Cython-generated C sources are build artifacts (~6 MB), not sources.
SKIP_EXT = {".pyc", ".pyo", ".so", ".pyd", ".c", ".o", ".obj"}
SKIP_FILES = {"coverage.xml", ".coverage"}


def main():
    # A .git directory inside the staging tree (left over from a previous
    # upload) cannot always be removed on Windows, so the staging directory is
    # cleaned file by file and .git is skipped when it refuses to go.
    """Stage the project and write the distributable ZIP."""
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE, exist_ok=True)

    copied = 0
    for dirpath, dirnames, filenames in os.walk(SRC):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, SRC)
        target = STAGE if rel == "." else os.path.join(STAGE, rel)
        os.makedirs(target, exist_ok=True)
        for name in filenames:
            if name in SKIP_FILES or os.path.splitext(name)[1] in SKIP_EXT:
                continue
            shutil.copy2(os.path.join(dirpath, name), os.path.join(target, name))
            copied += 1

    # benchmark harness (scripts + patches + raw data + logs)
    bench_dst = os.path.join(STAGE, "bench")
    os.makedirs(bench_dst, exist_ok=True)
    for name in os.listdir(HERE):
        src = os.path.join(HERE, name)
        if not os.path.isfile(src):
            continue
        if os.path.splitext(name)[1] in {".pyc"}:
            continue
        if name.startswith("_runner_tmp"):
            continue
        shutil.copy2(src, os.path.join(bench_dst, name))
        copied += 1

    if os.path.exists(ZIP):
        os.remove(ZIP)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for dirpath, dirnames, filenames in os.walk(STAGE):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                full = os.path.join(dirpath, name)
                arc = os.path.relpath(full, os.path.dirname(STAGE)).replace("\\", "/")
                zf.write(full, arc)

    size = os.path.getsize(ZIP)
    print("files staged:", copied)
    print("zip bytes:", size, f"({size/1024/1024:.2f} MB)")
    print("zip:", ZIP)


if __name__ == "__main__":
    main()
