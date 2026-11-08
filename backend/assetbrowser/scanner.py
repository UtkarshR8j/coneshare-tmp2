"""Read-only view of OpenCloud's posix storage. Nothing here may ever write."""
import mimetypes
import os
import posixpath
import re
from datetime import datetime, timezone

from django.conf import settings

from documents.services import _get_doc_type_from_content_type

XATTR_ID = 'user.oc.id'
XATTR_STATUS = 'user.oc.nodestatus'
XATTR_SPACE_NAME = 'user.oc.space.name'
XATTR_DTIME = 'user.oc.dtime'
XATTR_MD5 = 'user.oc.cs.md5'

SPACE_KINDS = ('users', 'projects')
SPACE_ID_RE = re.compile(r'(users|projects):([A-Za-z0-9][A-Za-z0-9._-]*)')
MAX_SCANNED_ENTRIES = 200_000


class AssetError(Exception):
    pass


class AssetsNotConfigured(AssetError):
    pass


class InvalidAssetPath(AssetError):
    pass


class AssetNotFound(AssetError):
    pass


def _getxattr(path, name):
    try:
        return os.getxattr(path, name, follow_symlinks=False)
    except OSError:
        return None


def _root():
    root = settings.ASSETS_RO_ROOT
    if not root or not os.path.isdir(root):
        raise AssetsNotConfigured('Assets browser is not configured.')
    return root


def _is_visible_name(name):
    if name.startswith('.') or name.endswith(('.flock', '.mlock')):
        return False
    try:
        name.encode('utf-8')
    except UnicodeEncodeError:
        return False
    return True


def _is_published(path):
    """Only nodes OpenCloud itself knows about and has finished processing."""
    if _getxattr(path, XATTR_ID) is None:
        return False
    status = _getxattr(path, XATTR_STATUS)
    return not (status and status.startswith(b'processing'))


def _space_dir(space_id):
    match = SPACE_ID_RE.fullmatch(space_id or '')
    if not match:
        raise InvalidAssetPath('Invalid space id.')
    kind, name = match.groups()
    path = os.path.join(_root(), kind, name)
    if os.path.islink(path) or not os.path.isdir(path):
        raise AssetNotFound('Space not found.')
    return path


def _resolve(space_id, rel_path):
    space = _space_dir(space_id)
    rel_path = rel_path or ''
    if '\x00' in rel_path:
        raise InvalidAssetPath('Invalid path.')
    parts = [p for p in rel_path.split('/') if p]
    if any(not _is_visible_name(p) for p in parts):  # also rejects '.' and '..'
        raise InvalidAssetPath('Invalid path.')
    full = os.path.join(space, *parts)
    if os.path.realpath(full) != os.path.join(os.path.realpath(space), *parts):
        raise InvalidAssetPath('Invalid path.')  # a symlink is somewhere on the way
    return full, '/'.join(parts)


def _item(space_id, parent_rel, entry_name, full, st, is_dir):
    rel = posixpath.join(parent_rel, entry_name) if parent_rel else entry_name
    item = {
        'space_id': space_id,
        'path': rel,
        'name': entry_name,
        'type': 'folder' if is_dir else 'file',
        'size': None if is_dir else st.st_size,
        'modified_at': datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        'md5': None,
        'doc_type': None,
    }
    if not is_dir:
        md5 = _getxattr(full, XATTR_MD5)
        item['md5'] = md5.hex() if md5 else None
        content_type = mimetypes.guess_type(entry_name)[0] or 'application/octet-stream'
        item['doc_type'] = _get_doc_type_from_content_type(content_type)
    return item


def _visible_entries(directory):
    """Yields (entry, stat, is_dir) for listable children. Symlinks are never followed."""
    with os.scandir(directory) as it:
        for entry in it:
            if not _is_visible_name(entry.name) or entry.is_symlink():
                continue
            is_dir = entry.is_dir(follow_symlinks=False)
            if not is_dir and not entry.is_file(follow_symlinks=False):
                continue
            if not _is_published(entry.path):
                continue
            yield entry, entry.stat(follow_symlinks=False), is_dir


def list_spaces():
    root = _root()
    labels = settings.ASSETS_SPACE_LABELS
    spaces = []
    for kind in SPACE_KINDS:
        kind_dir = os.path.join(root, kind)
        if not os.path.isdir(kind_dir):
            continue
        with os.scandir(kind_dir) as it:
            for entry in it:
                if not _is_visible_name(entry.name) or entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                    continue
                if _getxattr(entry.path, XATTR_DTIME) is not None:
                    continue  # disabled space
                space_id = f'{kind}:{entry.name}'
                raw_name = _getxattr(entry.path, XATTR_SPACE_NAME)
                name = labels.get(space_id) or (raw_name.decode('utf-8', 'replace') if raw_name else None)
                spaces.append({
                    'id': space_id,
                    'name': name or f'{kind[:-1].title()} {entry.name[:8]}',
                    'kind': 'personal' if kind == 'users' else 'project',
                })
    return sorted(spaces, key=lambda s: (s['kind'], s['name'].lower()))


def list_dir(space_id, rel_path):
    full, rel = _resolve(space_id, rel_path)
    if not os.path.isdir(full):
        raise AssetNotFound('Folder not found.')
    items = [
        _item(space_id, rel, entry.name, entry.path, st, is_dir)
        for entry, st, is_dir in _visible_entries(full)
    ]
    return sorted(items, key=lambda i: (i['type'] != 'folder', i['name'].lower()))


def search(query, space_id=None, limit=200, space_ids=None):
    """space_ids, when given, is the exact list of spaces to walk (callers pass the org binding)."""
    needle = query.lower()
    if space_ids is None:
        space_ids = [space_id] if space_id else [s['id'] for s in list_spaces()]
    results, scanned = [], 0
    for sid in space_ids:
        stack = [(_space_dir(sid), '')]
        while stack:
            directory, rel = stack.pop()
            for entry, st, is_dir in _visible_entries(directory):
                scanned += 1
                if scanned > MAX_SCANNED_ENTRIES:
                    return results, True
                if is_dir:
                    stack.append((entry.path, posixpath.join(rel, entry.name) if rel else entry.name))
                elif needle in entry.name.lower():
                    if len(results) >= limit:
                        return results, True
                    results.append(_item(sid, rel, entry.name, entry.path, st, False))
    return results, False


def stat_file(space_id, rel_path):
    full, rel = _resolve(space_id, rel_path)
    if not rel or not os.path.isfile(full) or not _is_published(full):
        raise AssetNotFound('File not found.')
    parent, name = posixpath.split(rel)
    return _item(space_id, parent, name, full, os.stat(full, follow_symlinks=False), False)


def open_file(space_id, rel_path):
    stat_file(space_id, rel_path)
    full, _ = _resolve(space_id, rel_path)
    fd = os.open(full, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    return os.fdopen(fd, 'rb')


def file_id(space_id, rel_path):
    full, _ = _resolve(space_id, rel_path)
    raw = _getxattr(full, XATTR_ID)
    return raw.decode('utf-8', 'replace') if raw else ''
