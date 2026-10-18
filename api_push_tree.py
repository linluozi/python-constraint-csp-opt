"""Push a whole working tree to an empty repository through the Git Data API.

Needed when the git transport to github.com is down but api.github.com still
answers. Every file is uploaded as a blob, the tree is assembled from those
blobs (respecting the executable bit), then a root commit is created and the
branch is pointed at it.
"""
import base64
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = sys.argv[1] if len(sys.argv) > 1 else "linluozi/python-constraint-csp-opt"
ROOT = os.path.dirname(os.path.abspath(__file__))  # the script is copied into the tree root before running
MESSAGE = (
    "Optimize the default CSP solver: dynamic MRV, indexed search plan, "
    "scoped forward checking\n\n"
    "Based on python-constraint/python-constraint main @ d91ba03 (v2.7.3,\n"
    "BSD-2-Clause). See IMPROVEMENT_REPORT.md for the analysis and\n"
    "BENCHMARKS.md for the measured results.\n"
)

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".benchmarks", ".vscode",
             ".mypy_cache", ".ruff_cache", "build"}
SKIP_EXT = {".pyc", ".pyo", ".pyd", ".o", ".obj"}
SKIP_FILES = {"coverage.xml", ".coverage"}


def api(method, path, payload=None):
    """Call the GitHub REST API with gh and return parsed JSON."""
    cmd = ["gh", "api", "--method", method, f"repos/{REPO}/{path}"]
    if payload is not None:
        cmd += ["--input", "-"]
    proc = subprocess.run(cmd, input=json.dumps(payload) if payload else None,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"{method} {path} failed: {proc.stderr[:400]}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def collect():
    """Yield (repo relative path, absolute path, executable) for every file to ship."""
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name in SKIP_FILES or os.path.splitext(name)[1] in SKIP_EXT:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            mode = "100755" if os.access(full, os.X_OK) and name.endswith((".sh", ".py")) else "100644"
            out.append((rel, full, mode))
    return sorted(out)


def main():
    files = collect()
    print(f"{len(files)} files to upload")

    entries = []
    for i, (rel, full, mode) in enumerate(files, 1):
        with open(full, "rb") as fh:
            data = fh.read()
        blob = api("POST", "git/blobs", {
            "content": base64.b64encode(data).decode(),
            "encoding": "base64",
        })
        entries.append({"path": rel, "mode": mode, "type": "blob", "sha": blob["sha"]})
        if i % 20 == 0 or i == len(files):
            print(f"  uploaded {i}/{len(files)}")

    tree = api("POST", "git/trees", {"tree": entries})
    print("tree", tree["sha"][:7])

    commit = api("POST", "git/commits", {"message": MESSAGE, "tree": tree["sha"], "parents": []})
    print("commit", commit["sha"][:7])

    api("PATCH", "git/refs/heads/main", {"sha": commit["sha"], "force": True})
    print("main ->", commit["sha"][:7])


if __name__ == "__main__":
    main()
