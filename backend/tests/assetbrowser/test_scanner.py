import ast
import os
from pathlib import Path

import pytest

from assetbrowser import scanner


def test_lists_all_spaces_across_kinds(assets_root):
    spaces = scanner.list_spaces()
    assert {s['id'] for s in spaces} == {'users:user-1', 'projects:proj-1'}
    assert next(s for s in spaces if s['id'] == 'users:user-1')['name'] == 'Utkarsh'


def test_label_override_wins(assets_root, settings):
    settings.ASSETS_SPACE_LABELS = {'users:user-1': 'Owner'}
    assert next(s for s in scanner.list_spaces() if s['id'] == 'users:user-1')['name'] == 'Owner'


def test_browse_hides_internals_and_unpublished(assets_root):
    names = {i['name'] for i in scanner.list_dir('users:user-1', '')}
    assert names == {'Invoices', 'top.gif'}


def test_folders_sort_first(assets_root):
    assert scanner.list_dir('users:user-1', '')[0]['type'] == 'folder'


def test_search_walks_all_spaces_and_skips_internals(assets_root):
    items, truncated = scanner.search('gif', limit=50)
    assert {i['path'] for i in items} == {'Invoices/inv.gif', 'top.gif'}
    assert truncated is False


def test_search_reports_truncation(assets_root):
    items, truncated = scanner.search('gif', limit=1)
    assert len(items) == 1 and truncated is True


@pytest.mark.parametrize('path', ['../../etc/passwd', '.oc-nodes/secret.gif', 'Invoices/../.Trash', 'a\x00b'])
def test_rejects_bad_paths(assets_root, path):
    with pytest.raises(scanner.InvalidAssetPath):
        scanner.stat_file('users:user-1', path)


@pytest.mark.parametrize('space', ['users:../..', 'idm:x', 'users', '', 'users:a/b', 'users:user-1\n'])
def test_rejects_bad_space_ids(assets_root, space):
    with pytest.raises(scanner.InvalidAssetPath):
        scanner.list_dir(space, '')


def test_rejects_symlink_escape(assets_root, tmp_path):
    outside = tmp_path / 'outside.gif'
    outside.write_bytes(b'x')
    os.symlink(outside, assets_root / 'users' / 'user-1' / 'link.gif')
    with pytest.raises(scanner.InvalidAssetPath):
        scanner.stat_file('users:user-1', 'link.gif')
    assert 'link.gif' not in {i['name'] for i in scanner.list_dir('users:user-1', '')}


def test_unpublished_file_is_not_found(assets_root):
    with pytest.raises(scanner.AssetNotFound):
        scanner.stat_file('users:user-1', 'unknown.gif')


def test_open_file_reads_bytes(assets_root):
    with scanner.open_file('users:user-1', 'top.gif') as f:
        assert f.read() == b'top-bytes'


def test_not_configured(settings):
    settings.ASSETS_RO_ROOT = ''
    with pytest.raises(scanner.AssetsNotConfigured):
        scanner.list_spaces()


def test_real_xattr_read(tmp_path):
    f = tmp_path / 'x'
    f.write_bytes(b'')
    try:
        os.setxattr(f, 'user.oc.id', b'abc')
    except OSError:
        pytest.skip('filesystem has no user xattrs')
    assert scanner._getxattr(str(f), 'user.oc.id') == b'abc'


def test_scanner_source_has_no_write_primitives():
    tree = ast.parse(Path(scanner.__file__).read_text())
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not called & {'remove', 'unlink', 'rename', 'replace', 'mkdir', 'makedirs', 'rmdir', 'setxattr', 'write', 'chmod', 'chown', 'truncate'}
    flags = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not flags & {'O_WRONLY', 'O_RDWR', 'O_CREAT', 'O_TRUNC', 'O_APPEND'}
