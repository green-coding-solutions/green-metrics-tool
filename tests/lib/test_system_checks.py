from collections import namedtuple
from pathlib import Path

from lib import system_checks

Partition = namedtuple('Partition', ['device', 'mountpoint', 'fstype', 'opts'])

def _patch(monkeypatch, tmp_root, partitions):
    monkeypatch.setattr(system_checks.host_platform, 'is_windows', lambda: False)
    monkeypatch.setattr(system_checks.host_platform, 'get_repo_tmp_root', lambda: Path(tmp_root))
    monkeypatch.setattr(system_checks.psutil, 'disk_partitions', lambda all=False: partitions) # pylint: disable=redefined-builtin

def test_repo_tmp_folder_on_tmpfs_fails(monkeypatch):
    _patch(monkeypatch, '/var/tmp', [
        Partition('/dev/sda1', '/', 'ext4', 'rw'),
        Partition('tmpfs', '/var/tmp', 'tmpfs', 'rw'),
    ])
    assert system_checks.check_repo_tmp_folder_not_tmpfs() == '/var/tmp is on tmpfs'

def test_repo_tmp_folder_on_disk_passes(monkeypatch):
    # /tmp is a tmpfs, which is fine. Only /var/tmp matters
    _patch(monkeypatch, '/var/tmp', [
        Partition('/dev/sda1', '/', 'ext4', 'rw'),
        Partition('tmpfs', '/tmp', 'tmpfs', 'rw'),
    ])
    assert system_checks.check_repo_tmp_folder_not_tmpfs() is True

def test_repo_tmp_folder_uses_most_specific_mount(monkeypatch):
    # A disk mounted inside a tmpfs must win over the tmpfs it is mounted in
    _patch(monkeypatch, '/tmp/disk/gmt', [
        Partition('/dev/sda1', '/', 'ext4', 'rw'),
        Partition('tmpfs', '/tmp', 'tmpfs', 'rw'),
        Partition('/dev/sdb1', '/tmp/disk', 'xfs', 'rw'),
    ])
    assert system_checks.check_repo_tmp_folder_not_tmpfs() is True

def test_repo_tmp_folder_prefix_is_not_a_mount_match(monkeypatch):
    # /tmpfoo is not inside /tmp although the string starts with it
    _patch(monkeypatch, '/tmpfoo', [
        Partition('/dev/sda1', '/', 'ext4', 'rw'),
        Partition('tmpfs', '/tmp', 'tmpfs', 'rw'),
    ])
    assert system_checks.check_repo_tmp_folder_not_tmpfs() is True
