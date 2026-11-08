import pytest

from assetbrowser import scanner


@pytest.fixture
def assets_root(settings, tmp_path, monkeypatch):
    """A fake OpenCloud tree. Xattrs are faked so tests do not depend on the test filesystem."""
    root = tmp_path / 'assets-ro'
    space = root / 'users' / 'user-1'
    (space / 'Invoices').mkdir(parents=True)
    (space / '.oc-nodes').mkdir()
    (space / '.Trash').mkdir()
    (space / '.oc-tmp').mkdir()
    (root / 'projects' / 'proj-1').mkdir(parents=True)
    (space / 'Invoices' / 'inv.gif').write_bytes(b'GIF89a-bytes')
    (space / 'top.gif').write_bytes(b'top-bytes')
    (space / '.oc-nodes' / 'secret.gif').write_bytes(b'x')
    (space / 'lock.flock').write_bytes(b'')
    (space / 'unknown.gif').write_bytes(b'dropped by hand')
    (space / 'uploading.gif').write_bytes(b'')

    def fake_getxattr(path, name):
        path = str(path)
        if path.endswith('unknown.gif'):
            return None
        if name == scanner.XATTR_ID:
            return b'node-id'
        if name == scanner.XATTR_STATUS and path.endswith('uploading.gif'):
            return b'processing:abc'
        if name == scanner.XATTR_SPACE_NAME and path.endswith('user-1'):
            return b'Utkarsh'
        return None

    monkeypatch.setattr(scanner, '_getxattr', fake_getxattr)
    settings.ASSETS_RO_ROOT = str(root)
    settings.ASSETS_SPACE_LABELS = {}
    return root
