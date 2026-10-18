"""Push a single-file change through the Git Data API.

Used when the git transport to github.com is unreachable but api.github.com is
not. Every subtree sha that does not change is reused from the remote, so the
resulting tree differs from the previous commit only in the target file.
"""
import base64
import json
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = "linluozi/python-constraint-solver-opt"
TARGET = ".github/workflows/build-test-python-package.yml"
MESSAGE = (
    "ci: allow running the build & test workflow manually\n\n"
    "The path filter only watches constraint/, tests/ and the build files, so a\n"
    "change that touches only bench/ could never be verified by CI."
)


def api(method, path, payload=None):
    """Call the GitHub REST API with gh and return parsed JSON."""
    cmd = ["gh", "api", "--method", method, f"repos/{REPO}/{path}"]
    if payload is not None:
        # gh only reads the body from stdin when told to, hence --input -
        cmd += ["--input", "-"]
    proc = subprocess.run(cmd, input=json.dumps(payload) if payload else None,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"{method} {path} failed: {proc.stderr[:400]}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def main():
    head = json.loads(subprocess.run(
        ["gh", "api", f"repos/{REPO}/commits/main"], capture_output=True, text=True
    ).stdout)
    parent = head["sha"]
    root = json.loads(subprocess.run(
        ["gh", "api", f"repos/{REPO}/git/commits/{parent}"], capture_output=True, text=True
    ).stdout)["tree"]["sha"]
    print("parent", parent[:7], "root tree", root[:7])

    parts = TARGET.split("/")
    dirs, name = parts[:-1], parts[-1]

    chain = []
    current = root
    for d in dirs:
        tree = api("GET", f"git/trees/{current}")
        entry = next((e for e in tree["tree"] if e["path"] == d and e["type"] == "tree"), None)
        if entry is None:
            raise SystemExit(f"{d} not found under {current[:7]}")
        chain.append((d, current))
        current = entry["sha"]

    with open(TARGET, "rb") as fh:
        content = fh.read().replace(b"\r\n", b"\n")

    blob = api("POST", "git/blobs",
               {"content": base64.b64encode(content).decode(), "encoding": "base64"})
    print("blob", blob["sha"][:7], len(content), "bytes")

    inner = api("POST", "git/trees", {
        "base_tree": current,
        "tree": [{"path": name, "mode": "100644", "type": "blob", "sha": blob["sha"]}],
    })
    print("tree with file", inner["sha"][:7])

    child = inner["sha"]
    for d, parent_tree in reversed(chain):
        res = api("POST", "git/trees", {
            "base_tree": parent_tree,
            "tree": [{"path": d, "mode": "040000", "type": "tree", "sha": child}],
        })
        child = res["sha"]
        print(f"  {d} -> {child[:7]}")

    commit = api("POST", "git/commits",
                 {"message": MESSAGE, "tree": child, "parents": [parent]})
    print("commit", commit["sha"][:7])

    api("PATCH", "git/refs/heads/main", {"sha": commit["sha"], "force": True})
    print("main ->", commit["sha"][:7])


if __name__ == "__main__":
    main()
