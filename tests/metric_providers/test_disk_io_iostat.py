import os
import shutil
import subprocess
import time

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
LIB_C_DIR = os.path.join(REPO_DIR, 'lib', 'c')
PROVIDER_DIR = os.path.join(REPO_DIR, 'metric_providers', 'disk', 'io', 'cgroup', 'container')

# Major 900 is used for the "this row counts" cases on purpose: it is not on the
# provider's skip list and /sys/dev/block/900:* exists nowhere, so
# is_partition_sysfs() stays false and the expectations do not depend on which
# block devices the test machine happens to have. Major 252 is device-mapper and
# is dropped before any sysfs lookup happens.
COMPLETE_ROW = '900:0 rbytes=1000 wbytes=2000 rios=1 wios=2 dbytes=0 dios=0\n'


@pytest.fixture(name='harness', scope='module')
def harness_fixture(tmp_path_factory):
    if shutil.which('gcc') is None:
        pytest.skip('gcc not available')

    subprocess.run(['make'], cwd=LIB_C_DIR, check=True, capture_output=True)

    binary = str(tmp_path_factory.mktemp('disk_io') / 'harness')
    subprocess.run(
        [
            'gcc',
            os.path.join(LIB_C_DIR, 'gmt-lib.o'),
            os.path.join(LIB_C_DIR, 'gmt-container-lib.o'),
            os.path.join(CURRENT_DIR, 'disk_io_iostat_harness.c'),
            '-O1', '-Wall', '-Wno-unused-function',
            f"-I{LIB_C_DIR}", f"-I{PROVIDER_DIR}",
            '-lcurl', '-o', binary,
        ],
        check=True, capture_output=True,
    )
    return binary


def parse(harness, content):
    result = subprocess.run([harness], input=content, capture_output=True, text=True, check=True)
    rbytes, wbytes, torn = result.stdout.split()
    return int(rbytes), int(wbytes), torn == '1'


def test_complete_row_is_summed(harness):
    assert parse(harness, COMPLETE_ROW) == (1000, 2000, False)


def test_rows_are_summed_across_devices(harness):
    content = COMPLETE_ROW + '901:0 rbytes=7 wbytes=8 rios=1 wios=1 dbytes=0 dios=0\n'
    assert parse(harness, content) == (1007, 2008, False)


def test_skipped_majors_contribute_nothing(harness):
    content = '252:0 rbytes=99 wbytes=99 rios=1 wios=1 dbytes=0 dios=0\n'
    assert parse(harness, content) == (0, 0, False)


def test_empty_file_is_a_real_zero_not_a_torn_read(harness):
    # A container that has not touched a disk yet has an empty io.stat. Zero is
    # the correct answer and must not be flagged as unusable.
    assert parse(harness, '') == (0, 0, False)


def test_rows_without_discard_counters_are_still_read(harness):
    # The discard counters were added to io.stat later than the rest of the row.
    # The previous fscanf format required them, matched the head of the first
    # row, left the stream mid-row and silently dropped every device after it.
    content = (
        '900:0 rbytes=1000 wbytes=2000 rios=1 wios=2\n'
        '901:0 rbytes=30 wbytes=40 rios=1 wios=1\n'
    )
    assert parse(harness, content) == (1030, 2040, False)


def test_unknown_trailing_fields_do_not_drop_later_rows(harness):
    content = (
        '900:0 rbytes=1000 wbytes=2000 rios=1 wios=2 dbytes=0 dios=0 somethingnew=5\n'
        '901:0 rbytes=30 wbytes=40 rios=1 wios=1 dbytes=0 dios=0\n'
    )
    assert parse(harness, content) == (1030, 2040, False)


def test_torn_row_is_flagged(harness):
    # The kernel emits a bare device prefix while a cgroup is being set up.
    # Reading that as zero is what rewound the cumulative series.
    assert parse(harness, '252:0 \n')[2] is True


def test_torn_row_does_not_hide_the_other_rows(harness):
    content = COMPLETE_ROW + '901:0 \n'
    rbytes, wbytes, torn = parse(harness, content)
    assert (rbytes, wbytes) == (1000, 2000)
    assert torn is True


@pytest.fixture(name='provider_binary', scope='module')
def provider_binary_fixture():
    if shutil.which('gcc') is None:
        pytest.skip('gcc not available')
    subprocess.run(['make'], cwd=PROVIDER_DIR, check=True, capture_output=True)
    return os.path.join(PROVIDER_DIR, 'metric-provider-binary')


def test_series_stays_monotonic_when_the_cgroup_is_recreated(provider_binary):
    # Restarting a container destroys its scope and recreates it at the same
    # path with io.stat counters starting again at zero. The provider resolves
    # that path once at startup and reads straight through the swap, so it used
    # to publish the rewound counters and disk_io_parse.py then rejected the
    # whole measurement for having negative intervals.
    if shutil.which('docker') is None:
        pytest.skip('docker not available')

    name = 'gmt-disk-io-recreate-test'
    workload = 'while true; do dd if=/dev/urandom of=/tmp/f bs=1M count=8 oflag=direct 2>/dev/null; sleep 0.5; done'
    subprocess.run(['docker', 'rm', '-f', name], capture_output=True, check=False)

    started = subprocess.run(
        ['docker', 'run', '-d', '--name', name, 'alpine', 'sh', '-c', workload],
        capture_output=True, text=True, check=False,
    )
    if started.returncode != 0:
        pytest.skip(f"could not start container: {started.stderr.strip()}")

    try:
        container_id = subprocess.run(
            ['docker', 'inspect', '--format', '{{.Id}}', name],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        time.sleep(2)

        with subprocess.Popen(
            [provider_binary, '-s', container_id, '-i', '500'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ) as provider:
            try:
                time.sleep(4)
                subprocess.run(['docker', 'restart', '-t', '0', name], capture_output=True, check=True)
                time.sleep(6)
            finally:
                # The provider samples forever, so it has to be stopped before
                # __exit__ waits on it - including when the block above raised.
                provider.terminate()
            stdout, stderr = provider.communicate(timeout=10)
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, check=False)

    samples = [line.split() for line in stdout.strip().splitlines() if line.strip()]
    if len(samples) < 4:
        pytest.skip(f"provider produced too few samples to judge: {stderr}")

    reads = [int(sample[1]) for sample in samples]
    writes = [int(sample[2]) for sample in samples]

    assert reads == sorted(reads), f"read_bytes went backwards: {reads}\n{stderr}"
    assert writes == sorted(writes), f"written_bytes went backwards: {writes}\n{stderr}"
    assert 'was recreated' in stderr, f"the cgroup swap was not detected: {stderr}"
    assert writes[-1] > writes[0], 'no I/O was accounted at all'
