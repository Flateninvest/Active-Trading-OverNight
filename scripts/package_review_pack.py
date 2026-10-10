"""Package public review documents from exact committed Git blobs, not CRLF worktrees."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
from urllib.parse import quote
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = (
    "prompts/Grok_Overnight_Stock_Bot_Prompt_Current.txt",
    "spec/strategy_spec.provisional.json", "docs/DAILY_STRATEGY.md",
    "docs/DOUBLE_REVIEW.md", "docs/ORDER_MEMORY.md", "docs/TRADE_ACCOUNTING.md",
    "docs/HOMEWORK_CHECKLIST_2026-10-09.md", "docs/SHADOW_CONTROLS.md",
    "docs/IMPLEMENTATION_PLAN.md", "docs/VALIDATION.md", "docs/DATA_POLICY.md",
)


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True).stdout


def _portable_markdown(raw, relative, base):
    def link(match):
        target = match.group(2)
        if re.match(r"[a-zA-Z]+:", target) or target.startswith("#"):
            return match.group(0)
        path, separator, anchor = target.partition("#")
        path = posixpath.normpath(posixpath.join(posixpath.dirname(relative), path))
        return match.group(1) + base + quote(path, safe="/") + (separator + anchor if separator else "") + ")"
    return re.sub(r"(\[[^]]+\]\()([^)]+)\)", link, raw.decode("utf-8")).encode("utf-8")


def package_review_pack(output, *, commit="HEAD", paths=DEFAULT_PATHS, repo=ROOT,
                        portable_markdown=False):
    """Write a new ZIP; manifest hashes identify Git and exact archive bytes."""
    repo, output = Path(repo).resolve(), Path(output).expanduser().resolve()
    if output == repo or repo in output.parents or any((p / ".git").exists() for p in output.parents):
        raise ValueError("Review downloads must be outside every Git checkout")
    revision = _git(repo, "rev-parse", "--verify", commit + "^{commit}").decode("ascii").strip()
    base = "https://github.com/Flateninvest/Active-Trading-OverNight/blob/" + revision + "/"
    contents, manifest = {}, []
    for relative in paths:
        path = PurePosixPath(relative)
        if (path.is_absolute() or ".." in path.parts or ".git" in path.parts
                or relative in contents or relative in ("manifest.json", "START_HERE.txt")):
            raise ValueError("Unique repository-relative public file paths required")
        raw = _git(repo, "cat-file", "blob", revision + ":" + relative)
        data = _portable_markdown(raw, relative, base) if portable_markdown and path.suffix == ".md" else raw
        contents[relative] = data
        manifest.append({"path": relative,
                         "repository_bytes_sha256": hashlib.sha256(raw).hexdigest(),
                         "download_bytes_sha256": hashlib.sha256(data).hexdigest()})
    contents["START_HERE.txt"] = (
        "PUBLIC REVIEW PACK\nExact committed source: " + revision + "\n"
        "https://github.com/Flateninvest/Active-Trading-OverNight/tree/" + revision + "\n"
        "Read the shared specification and effective prompt together. This package does not\n"
        "enable broker writes, live trading, deployment or merge a pull request.\n"
        "Manifest repository hashes use exact committed Git blobs; download hashes use exact ZIP payload bytes.\n"
    ).encode("utf-8")
    contents["manifest.json"] = (json.dumps({"source_commit": revision,
        "repository_hash_basis": "EXACT_COMMITTED_GIT_BLOB_BYTES",
        "download_hash_basis": "EXACT_UNCOMPRESSED_ZIP_ENTRY_BYTES",
        "markdown_links_made_portable": portable_markdown, "contents": manifest}, indent=2) + "\n").encode("utf-8")
    with ZipFile(output, "x", ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            archive.writestr(name, data)
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("Review ZIP verification failed")
        for entry in manifest:
            if hashlib.sha256(archive.read(entry["path"])).hexdigest() != entry["download_bytes_sha256"]:
                raise ValueError("Review ZIP payload hash mismatch")
    return {"source_commit": revision, "zip_bytes_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "file_count": len(contents), "broker_writes": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New ZIP outside Git")
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--paths", nargs="+", default=DEFAULT_PATHS)
    parser.add_argument("--portable-markdown", action="store_true")
    args = parser.parse_args(argv)
    result = package_review_pack(args.output, commit=args.commit, paths=args.paths,
                                 portable_markdown=args.portable_markdown)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
