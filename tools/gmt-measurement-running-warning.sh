# Green Metrics Tool - login warning
# Installed to /etc/profile.d/ by install_linux.sh. Must stay POSIX sh compatible as it is sourced by login shells.
# Warns only if a measurement is actually running (ScenarioRunner.run() is active), not if just client.py is idling.
# The marker files are created by lib/scenario_runner.py and contain the PID of the measuring process in the first line.

for _gmt_marker in /tmp/gmt-measurement-running.*; do
    [ -f "$_gmt_marker" ] || continue
    _gmt_pid=$(head -n 1 "$_gmt_marker" 2>/dev/null)
    case "$_gmt_pid" in
        ''|*[!0-9]*) continue ;;
    esac
    # skip stale markers from killed runs (PID gone or reused by a non python process)
    if [ -r "/proc/$_gmt_pid/cmdline" ] && tr '\0' ' ' < "/proc/$_gmt_pid/cmdline" 2>/dev/null | grep -q python; then
        _gmt_start=$(sed -n 2p "$_gmt_marker" 2>/dev/null)
        _gmt_since=''
        case "$_gmt_start" in
            ''|*[!0-9]*) ;;
            *) _gmt_since=" since $(date -d "@$_gmt_start" '+%Y-%m-%d %H:%M:%S' 2>/dev/null) ($(( ($(date +%s) - _gmt_start) / 60 )) min)" ;;
        esac
        printf '\n\033[41m\033[1m  WARNING: A Green Metrics Tool measurement is currently running on this machine!  \033[0m\n'
        printf '\033[93m  PID %s%s\n  Any activity on this machine (including this SSH session) will influence the measurement.\033[0m\n\n' "$_gmt_pid" "$_gmt_since"
    fi
done
unset _gmt_marker _gmt_pid _gmt_start _gmt_since
