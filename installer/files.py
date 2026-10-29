"""Portable owned-file primitives for serialized, user-owned install roots.

Existing links are rejected. Concurrent hostile directory replacement is outside
this API's guarantee; callers must serialize operations and establish root ownership.
"""
from pathlib import Path, PureWindowsPath
from tempfile import NamedTemporaryFile
import hashlib
import json
import os
import re
import stat
import time


def _reject_links(path: Path) -> None:
    for entry in (*reversed(path.parents), path):
        try:
            metadata = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
            raise ValueError(f'unsafe link/reparse point: {entry}')


def resolve_owned(root: Path, relative: str) -> Path:
    """Return a canonical destination, rejecting aliases on every host."""
    if not isinstance(relative, str) or not relative or '\\' in relative or relative.startswith('/') or PureWindowsPath(relative).drive:
        raise ValueError('destination must be a portable relative path')
    pieces = relative.split('/')
    for piece in pieces:
        if (piece in ('', '.', '..') or piece.endswith((' ', '.')) or PureWindowsPath(piece).is_reserved()
                or re.search(r'[<>:"|?*\x00-\x1f]', piece)):
            raise ValueError('unsafe destination component')
    base = Path(os.path.abspath(root))
    target = base.joinpath(*pieces)
    _reject_links(target)
    if not target.resolve().is_relative_to(base.resolve()):
        raise ValueError('destination leaves owned root')
    return target


def _replace_bytes(target: Path, content: bytes, prior_hash: str | None, receipt: bool) -> None:
    def validate():
        _reject_links(target)
        if target.exists():
            if not target.is_file():
                raise ValueError('destination is not a regular file')
            if not receipt and (prior_hash is None or hashlib.sha256(target.read_bytes()).hexdigest() != prior_hash):
                raise ValueError('existing file is unknown or modified')
    validate()
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = None
    try:
        with NamedTemporaryFile(mode='wb', prefix='.' + target.name + '.', suffix='.tmp', dir=target.parent, delete=False) as stream:
            stage = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(5):
            validate()
            try:
                os.replace(stage, target)
                break
            except PermissionError as exc:
                if os.name != 'nt' or getattr(exc, 'winerror', None) not in (5, 32, 33) or attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)


def write_owned(root: Path, relative: str, content: bytes, expected_sha256: str | None = None) -> str:
    """Write bytes; return their receipt hash. Prior hash comes from a trusted receipt."""
    if not isinstance(content, bytes) or (expected_sha256 is not None and (not isinstance(expected_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256))):
        raise ValueError('expected bytes and a valid optional ownership hash')
    _replace_bytes(resolve_owned(root, relative), content, expected_sha256, False)
    return hashlib.sha256(content).hexdigest()


def write_receipt(path: Path, receipt: dict) -> None:
    """Atomic generic JSON writer; caller must establish ownership of this receipt path.

    Serialization or pre-replace failures preserve existing bytes. This function
    does not decide whether an existing receipt belongs to this installer.
    """
    if not isinstance(receipt, dict):
        raise ValueError('receipt must be a dictionary')
    encoded = (json.dumps(receipt, allow_nan=False, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    _replace_bytes(Path(os.path.abspath(path)), encoded, None, True)
