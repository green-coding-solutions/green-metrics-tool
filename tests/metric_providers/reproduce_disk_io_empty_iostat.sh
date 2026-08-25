#!/usr/bin/env bash
#
# Reproduce: DiskIoCgroupContainerProvider reports a fabricated 0 when io.stat
# stops yielding usable rows. rbytes/wbytes are CUMULATIVE, so that rewinds the
# series to zero, every later interval is negative, and disk_io_parse.py then
# discards an already-finished measurement with
#
#   ValueError: DiskIoCgroupContainerProvider data column read_bytes_intervals
#               had negative values.
#
# Seen in the wild: a container whose own systemd accounting ended at
# "710.7M read from disk, 1.8G written to disk" reported 0 for its last 2373
# samples, having last read 356M. No container restart - the cgroup was never
# recreated. The scenario itself had completed, all checkpoints passed, and the
# run was thrown away in post-processing.
#
# HOW IT REPRODUCES WITHOUT ROOT
#
#   * detect_cgroup_path() probes the rootless user-slice path BEFORE the
#     rootful system.slice one, so a cgroup we create there under a real
#     container's id shadows the real one.
#   * An unprivileged user may create cgroups under their own delegated user
#     slice, put a process in one, and thereby give it real io.stat rows.
#   * Removing and recreating that cgroup leaves the SAME path holding a fresh,
#     EMPTY io.stat - which is what the collector hits transiently in the wild.
#
# So: populated first, empty afterwards, same path. Exactly the observed
# sequence.
#
# Usage:  ./reproduce_disk_io_empty_iostat.sh
# Exit:   1 = bug reproduced (fabricated zero)   0 = provider behaves correctly
#
# Override the binary under test to compare before/after a fix:
#   GMT_DISK_IO_BINARY=/tmp/old-binary ./reproduce_disk_io_empty_iostat.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${GMT_DISK_IO_BINARY:-$HERE/../../metric_providers/disk/io/cgroup/container/metric-provider-binary}"
NAME=gmt-disk-io-repro
UID_N="$(id -u)"
USER_SLICE="/sys/fs/cgroup/user.slice/user-${UID_N}.slice/user@${UID_N}.service/user.slice"
SHADOW=""
OUT=/tmp/gmt-disk-io-repro.out
ERR=/tmp/gmt-disk-io-repro.err
PAYLOAD="${HOME}/.cache/gmt-disk-io-repro.bin"   # must be DISK backed; /tmp is tmpfs on many hosts and produces no io.stat rows at all

cleanup() {
    [ -n "${PROV_PID:-}" ] && kill "$PROV_PID" 2>/dev/null
    docker rm -f "$NAME" >/dev/null 2>&1
    [ -n "$SHADOW" ] && [ -d "$SHADOW" ] && rmdir "$SHADOW" 2>/dev/null
    rm -f "$PAYLOAD"
    return 0
}
trap cleanup EXIT

skip() { echo "SKIP: $1"; exit 0; }

[ -x "$BIN" ]        || skip "provider binary not built at $BIN (run make in its directory)"
[ -d "$USER_SLICE" ] || skip "no delegated cgroup v2 user slice at $USER_SLICE"
command -v docker >/dev/null || skip "docker not available"

echo "binary under test: $BIN"
echo
echo "1. a real container, so the provider can resolve its name"
docker rm -f "$NAME" >/dev/null 2>&1
docker run -d --name "$NAME" alpine sleep 300 >/dev/null 2>&1 || skip "could not start container"
CID="$(docker inspect --format '{{.Id}}' "$NAME")"
echo "   ${CID:0:12}"

echo
echo "2. shadow its cgroup at the rootless path and give it REAL io.stat rows"
SHADOW="$USER_SLICE/docker-${CID}.scope"
rmdir "$SHADOW" 2>/dev/null
mkdir -p "$SHADOW" 2>/dev/null || skip "cannot create a cgroup under the user slice"
mkdir -p "$(dirname "$PAYLOAD")"
case "$(df -T "$(dirname "$PAYLOAD")" | awk 'NR==2{print $2}')" in
    tmpfs|ramfs) skip "$(dirname "$PAYLOAD") is in RAM; no disk I/O would be accounted" ;;
esac
# oflag=direct on purpose: buffered writes are flushed by kernel threads
# OUTSIDE this cgroup, so almost nothing would be attributed to it.
( echo $BASHPID > "$SHADOW/cgroup.procs" 2>/dev/null &&
  dd if=/dev/urandom of="$PAYLOAD" bs=1M count=32 oflag=direct 2>/dev/null ) || skip "could not attribute I/O to the cgroup"
# NB: cgroupfs files always stat() as size 0, so `test -s` is useless on them.
# The content has to be read.
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -n "$(cat "$SHADOW/io.stat" 2>/dev/null)" ] && break; sleep 0.3; done
[ -n "$(cat "$SHADOW/io.stat" 2>/dev/null)" ] || skip "cgroup io.stat stayed empty; cannot set up the 'before' state"
sed 's/^/     /' "$SHADOW/io.stat"

echo
echo "3. sample the provider while io.stat is populated"
: > "$OUT"; : > "$ERR"
"$BIN" -s "$CID" -i 2000 >"$OUT" 2>"$ERR" &
PROV_PID=$!
sleep 5
BEFORE_R="$(awk 'END{print $2}' "$OUT")"
BEFORE_W="$(awk 'END{print $3}' "$OUT")"
echo "     last sample before: rbytes=$BEFORE_R wbytes=$BEFORE_W"
# A direct WRITE populates wbytes; rbytes can legitimately stay 0 here, so the
# write counter is the one we assert on.
if [ -z "$BEFORE_W" ] || [ "$BEFORE_W" = "0" ]; then
    kill "$PROV_PID" 2>/dev/null
    skip "provider did not read non-zero values to begin with"
fi

echo
echo "4. empty io.stat at the SAME path, provider keeps running"
# Recreating the cgroup gives the same path a fresh, EMPTY io.stat. There is a
# sub-millisecond window where the path does not exist, and the collector treats
# a missing path as fatal - so do the swap immediately after a sample lands, to
# put that window inside the provider's 2 s sleep.
n0="$(wc -l < "$OUT")"
for _ in $(seq 1 60); do [ "$(wc -l < "$OUT")" -gt "$n0" ] && break; sleep 0.05; done
rmdir "$SHADOW" 2>/dev/null && mkdir -p "$SHADOW" 2>/dev/null
[ -d "$SHADOW" ] || { kill "$PROV_PID" 2>/dev/null; skip "could not recreate the cgroup"; }
echo "     io.stat is now $([ -n "$(cat "$SHADOW/io.stat" 2>/dev/null)" ] && echo 'NOT empty' || echo 'EMPTY')"
sleep 7
kill "$PROV_PID" 2>/dev/null; wait "$PROV_PID" 2>/dev/null
PROV_PID=""

AFTER_R="$(awk 'END{print $2}' "$OUT")"
AFTER_W="$(awk 'END{print $3}' "$OUT")"
echo "     last sample after : rbytes=$AFTER_R wbytes=$AFTER_W"
WARN="$(grep -m1 'io.stat' "$ERR" 2>/dev/null)"
[ -n "$WARN" ] && echo "     stderr: $WARN"

echo
NEG=0
# either cumulative column going backwards is the defect
awk 'NR>1 && (($2+0) < (pr+0) || ($3+0) < (pw+0)) {found=1} {pr=$2; pw=$3} END{exit !found}' "$OUT" && NEG=1

if [ "$NEG" = "1" ]; then
    cat <<MSG
BUG REPRODUCED
  A cumulative counter went BACKWARDS: wbytes $BEFORE_W -> $AFTER_W.
  Nothing marks this reading as unusable, so downstream every interval after it
  is negative and disk_io_parse.py aborts the whole measurement - after the
  scenario has already run to completion.
MSG
    exit 1
fi

cat <<MSG
OK
  Both cumulative counters stayed monotonic across the empty io.stat
  (wbytes $BEFORE_W -> $AFTER_W). The collector kept its last known values instead of
  fabricating a zero, and said so on stderr.
MSG
exit 0
