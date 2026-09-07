"""Verify/install the GitHub main snapshot. Python 3.10+, Git; no third-party packages."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import zipfile

REMOTE = "https://github.com/fly-YaoPro/douni-script-review.git"
BRANCH = "main"


def git(*args: str, cwd: Path) -> str:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"Git {args[0]} failed; check repository access, network and Git credentials")
    return result.stdout.decode("utf-8").strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def linked(path: Path) -> bool:
    return path.is_symlink() or (path.exists() and bool(getattr(path.stat(), "st_file_attributes", 0) & 0x400))


def safe_path(root: Path, name: str) -> Path:
    parts = PurePosixPath(name).parts
    if (not parts or "\\" in name or ":" in name or name.startswith("/")
            or any(p in ("..", ".git", ".local") or p.endswith((".", " ")) for p in parts)
            or PurePosixPath(name).as_posix() != name):
        raise RuntimeError(f"Unsafe managed path: {name}")
    path = root.joinpath(*parts)
    for ancestor in (path, *path.parents):
        if ancestor == root:
            break
        if linked(ancestor):
            raise RuntimeError("Symlink/junction in managed path")
    if not path.resolve().is_relative_to(root.resolve()):
        raise RuntimeError("Managed path escapes installation")
    return path


def atomic_json(path: Path, value: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def install_snapshot(root: Path, stage: Path, files: dict[str, str], commit: str,
                     state_dir: Path) -> dict:
    state_path = state_dir / "github-state.json"
    prior = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    old_files = prior.get("files", {})
    if not prior:
        # Old manual installs have no manifest. References are package-owned.
        old_files = {p.relative_to(root).as_posix(): None
                     for p in (root / "references").rglob("*")
                     if p.is_file() and '.git' not in p.relative_to(root).parts}
    changed = [name for name, value in files.items()
               if not safe_path(root, name).is_file() or digest(safe_path(root, name)) != value]
    removed = [name for name in old_files if name not in files and safe_path(root, name).exists()]
    touched = sorted(set(changed + removed))
    backup = None
    if touched:
        backup_parent = root.parent / f".{root.name}-backups"
        if linked(backup_parent):
            raise RuntimeError("Backup directory cannot be a link")
        backup_parent.mkdir(exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix="update-", dir=backup_parent))
        existed = []
        for name in touched:
            path = safe_path(root, name)
            if path.exists():
                if not path.is_file():
                    raise RuntimeError(f"Managed file collides with directory: {name}")
                target = safe_path(backup, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                existed.append(name)
        atomic_json(state_dir / "transaction.json", {
            "backup": str(backup), "touched": touched, "existed": existed, "targetCommit": commit,
        })
        try:
            for name in changed:
                target = safe_path(root, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(safe_path(stage, name), target)
            for name in removed:
                safe_path(root, name).unlink()
            for name, expected in files.items():
                if digest(safe_path(root, name)) != expected:
                    raise RuntimeError("Post-update integrity check failed")
        except BaseException:
            for name in touched:
                target = safe_path(root, name)
                if name in existed:
                    shutil.copy2(safe_path(backup, name), target)
                elif target.is_file():
                    target.unlink()
            (state_dir / "transaction.json").unlink()
            raise
    atomic_json(state_path, {"repository": REMOTE, "branch": BRANCH, "commit": commit,
                            "checkedAt": datetime.now(timezone.utc).isoformat(), "files": files})
    (state_dir / "transaction.json").unlink(missing_ok=True)
    return {"ok": True, "status": "updated" if touched else "latest", "commit": commit,
            "changedFiles": len(changed), "removedFiles": len(removed),
            "backup": str(backup) if backup else None, "reloadSkill": bool(touched)}


def ensure_latest(root: Path, remote: str = REMOTE) -> dict:
    root = root.resolve()
    if not (root / "SKILL.md").is_file():
        raise RuntimeError("Installation must contain SKILL.md")
    state_dir = root / ".local"
    if linked(state_dir):
        raise RuntimeError("Local state directory cannot be a link")
    state_dir.mkdir(exist_ok=True)
    if (state_dir / "transaction.json").exists():
        raise RuntimeError("Interrupted update: restore files from .local/transaction.json before continuing")
    lock = state_dir / "update.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError("Update already running; after a crash verify process ended before removing update.lock")
    os.close(fd)
    try:
        cache = state_dir / "github-cache.git"
        if linked(cache):
            raise RuntimeError("Git cache cannot be a link")
        if not cache.exists():
            git("init", "--bare", str(cache), cwd=root)
        git("fetch", "--depth=1", "--no-tags", remote, f"refs/heads/{BRANCH}", cwd=cache)
        commit = git("rev-parse", "FETCH_HEAD^{commit}", cwd=cache)
        with tempfile.TemporaryDirectory(prefix="douni-review-update-") as temp:
            temporary = Path(temp)
            archive = temporary / "snapshot.zip"
            git("archive", "--format=zip", f"--output={archive}", commit, cwd=cache)
            stage = temporary / "stage"
            stage.mkdir()
            files = {}
            folded = set()
            with zipfile.ZipFile(archive) as bundle:
                for entry in bundle.infolist():
                    if entry.is_dir():
                        continue
                    name = entry.filename
                    target = safe_path(stage, name)
                    mode = entry.external_attr >> 16
                    if stat.S_ISLNK(mode) or name.casefold() in folded:
                        raise RuntimeError("Unsupported symlink or duplicate-case path in remote tree")
                    folded.add(name.casefold())
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(bundle.read(entry))
                    if os.name != "nt":
                        target.chmod(0o755 if mode & 0o111 else 0o644)
                    files[name] = digest(target)
            required = ["SKILL.md", "scripts/ensure_latest.py", "references/user-execution.md",
                        "references/local-sources/manifest.json",
                        "references/local-sources/meeting-review-alignment-full-transcript.txt"]
            if any(name not in files for name in required):
                raise RuntimeError("GitHub snapshot lacks required team Skill files")
            return install_snapshot(root, stage, files, commit, state_dir)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        result = ensure_latest(Path(__file__).resolve().parents[1])
    except Exception as error:
        print(json.dumps({"ok": False, "status": "blocked", "error": str(error)}, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False))
