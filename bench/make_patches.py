"""Regenerate the diff files as a/ b/ patches and prove they apply byte-for-byte.

The patches shipped earlier carried the local directory names as paths
(upstream/..., python-constraint-opt/...), so `patch -p1` could not find the
target and skipped every hunk. They are rebuilt here with the conventional
a/ b/ prefixes, LF line endings, and are then applied to a pristine copy of the
upstream files and compared with `==` on raw bytes.
"""
import os
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.join(ROOT, "upstream")
OPT = os.path.join(ROOT, "python-constraint-opt")
BENCH = os.path.join(ROOT, "bench")

PAIRS = [
    ("constraint/solvers.py", "solvers.patch"),
    ("constraint/constraints.py", "constraints.patch"),
    ("constraint/domain.py", "domain.patch"),
    ("constraint/problem.py", "problem.patch"),
    ("constraint/parser.py", "parser.patch"),
]


def read(path):
    """Return the raw bytes of a file."""
    with open(path, "rb") as fh:
        return fh.read()


def to_lf(data):
    """Return the given bytes with CRLF line endings normalised to LF."""
    return data.replace(b"\r\n", b"\n")


def main():
    """Write a/ b/ patches and verify each one reproduces the shipped file."""
    written = []
    for rel, name in PAIRS:
        old = to_lf(read(os.path.join(UP, rel)))
        new = to_lf(read(os.path.join(OPT, rel)))
        if old == new:
            print(f"{rel}: unchanged upstream, no patch needed")
            continue

        with tempfile.TemporaryDirectory() as tmp:
            os.path.join(tmp, "a", rel)
            os.path.join(tmp, "b", rel)
            for base, data in (("a", old), ("b", new)):
                p = os.path.join(tmp, base, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as fh:
                    fh.write(data)

            proc = subprocess.run(
                ["diff", "-u", "-p",
                 os.path.join("a", rel), os.path.join("b", rel)],
                cwd=tmp, capture_output=True,
            )
            patch_bytes = proc.stdout
            if not patch_bytes.strip():
                print(f"{rel}: diff produced nothing, skipped")
                continue
            if not patch_bytes.endswith(b"\n"):
                patch_bytes += b"\n"
            out = os.path.join(BENCH, name)
            with open(out, "wb") as fh:
                fh.write(patch_bytes)
            written.append(name)
            print(f"wrote {name}: {len(patch_bytes)} bytes, {patch_bytes.count(b'@@')} hunks")

    # --- prove every patch reproduces the shipped file byte for byte --------- #
    ok = True
    for rel, name in PAIRS:
        p = os.path.join(BENCH, name)
        if not os.path.exists(p):
            continue
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "w")
            os.makedirs(os.path.join(work, os.path.dirname(rel)))
            # start from the upstream file, converted to LF like the patch expects
            with open(os.path.join(work, rel), "wb") as fh:
                fh.write(to_lf(read(os.path.join(UP, rel))))

            with open(p, "rb") as fh:
                proc = subprocess.run(["patch", "-p1", "--binary"], cwd=work,
                                      stdin=fh, capture_output=True)
            if proc.returncode != 0:
                print(f"FAIL {name}: {proc.stdout.decode(errors='replace')[-300:]}")
                ok = False
                continue

            got = read(os.path.join(work, rel))
            want = to_lf(read(os.path.join(OPT, rel)))
            same = got == want
            print(f"{'OK  ' if same else 'FAIL'} {name}: {len(got)} vs {len(want)} bytes, "
                  f"{'identical' if same else 'DIFFERENT'}")
            ok = ok and same

    print("\nall patches verified:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
