#!/usr/bin/env bash
# =============================================================================
# setup_windows_rapl.sh
#
# GMT Windows RAPL Setup Script
# Läuft in WSL2 oder nativer Linux VM (Ubuntu 22/24).
#
# Strategie:
#   - Bash:   System-Erkennung, Treiber-Check, CPU-Detection
#   - Python: config.yml parsen, Werte übernehmen, Windows-Block einfügen
#
# Was dieses Script tut:
#   1. System erkennen (WSL2 / native Linux VM)
#   2. Bei WSL2: ScaphandreDrv + rapl_reader.exe prüfen
#   3. Bei WSL2: RAPL_READER_EXE Umgebungsvariable setzen
#   4. CPU + RAPL Domains erkennen
#   5. config.yml spiegeln + Windows-Block einsetzen → config.example.windows
#   6. Diagnose-Report
#
# Usage:
#   chmod +x setup_windows_rapl.sh
#   ./setup_windows_rapl.sh
#   ./setup_windows_rapl.sh --gmt-dir ~/gmt-fresh
#   ./setup_windows_rapl.sh --dry-run
# =============================================================================

set -euo pipefail

RED=$'\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}  [OK]${RESET}  $*"; }
warn() { echo -e "${YELLOW}  [!!]${RESET}  $*"; }
err()  { echo -e "${RED}  [ERR]${RESET} $*"; }
info() { echo -e "${CYAN}  [--]${RESET}  $*"; }
hdr()  { echo -e "\n${BOLD}$*${RESET}"; printf '=%.0s' {1..60}; echo; }

# =============================================================================
# Argumente
# =============================================================================
GMT_DIR=""
DRY_RUN=false

for arg in "$@"; do
    case "$arg" in
        --gmt-dir=*) GMT_DIR="${arg#*=}" ;;
        --gmt-dir)   shift; GMT_DIR="${1:-}" ;;
        --dry-run)   DRY_RUN=true ;;
        --help|-h)   echo "Usage: $0 [--gmt-dir <path>] [--dry-run]"; exit 0 ;;
    esac
done

# GMT-Verzeichnis ermitteln
if [[ -z "$GMT_DIR" ]]; then
    if   [[ -f "./config.yml" ]];               then GMT_DIR="$(pwd)"
    elif [[ -f "$HOME/gmt-fresh/config.yml" ]]; then GMT_DIR="$HOME/gmt-fresh"
    else
        warn "GMT-Verzeichnis nicht gefunden – bitte --gmt-dir angeben."
        GMT_DIR="$(pwd)"
    fi
fi

SOURCE_CONFIG="$GMT_DIR/config.yml"
OUTPUT_CONFIG="$GMT_DIR/config.example.windows"

if [[ ! -f "$SOURCE_CONFIG" ]]; then
    err "config.yml nicht gefunden in: $GMT_DIR"
    err "Bitte --gmt-dir korrekt setzen."
    exit 1
fi

ok "GMT-Verzeichnis: $GMT_DIR"

# Python3 ermitteln (venv bevorzugen)
PYTHON=""
if [[ -f "$GMT_DIR/venv/bin/python3" ]]; then
    PYTHON="$GMT_DIR/venv/bin/python3"
    ok "Python: $PYTHON (venv)"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
    ok "Python: $(command -v python3) (system)"
else
    err "python3 nicht gefunden – kann config.yml nicht parsen."
    exit 1
fi

# =============================================================================
# SCHRITT 1 – System erkennen
# =============================================================================
hdr "Schritt 1: System-Erkennung"

IS_WSL=false
IS_NATIVE_LINUX=false
WSL_VERSION=""

if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
    IS_WSL=true
    grep -qi "WSL2" /proc/version 2>/dev/null && WSL_VERSION="WSL2" || WSL_VERSION="WSL1"
    ok "Erkannt: $WSL_VERSION"
else
    IS_NATIVE_LINUX=true
    ok "Erkannt: native Linux VM"
fi

if [[ "$WSL_VERSION" == "WSL1" ]]; then
    err "WSL1 nicht unterstützt → upgraden: wsl --set-version <distro> 2"
    exit 1
fi

# =============================================================================
# SCHRITT 2 – WSL2: Windows-Seite prüfen
# =============================================================================
RAPL_EXE_PATH=""
DRIVER_RUNNING=false
ENV_VAR_SET=false

if [[ "$IS_WSL" == "true" ]]; then
    hdr "Schritt 2: Windows-Seite prüfen"

    if ! command -v cmd.exe &>/dev/null; then
        err "cmd.exe nicht gefunden"; exit 1
    fi
    ok "cmd.exe erreichbar"

    # Treiber-Status
    info "Prüfe ScaphandreDrv..."
    DRIVER_STATE=$(cmd.exe /c "cd /d C:\\\\ && sc query ScaphandreDrv 2>nul" 2>/dev/null \
        | grep -vE '^"|UNC|CMD\.EXE|Stattdessen' \
        | grep -i "STATE" | grep -o "RUNNING\|STOPPED" | head -1 \
        || echo "NOT_FOUND")

    case "$DRIVER_STATE" in
        RUNNING) ok "ScaphandreDrv läuft"; DRIVER_RUNNING=true ;;
        STOPPED) warn "ScaphandreDrv gestoppt → sc start ScaphandreDrv  (Admin)" ;;
        *)       err  "ScaphandreDrv nicht gefunden → DriverLoader.exe install  (Admin)" ;;
    esac

    # rapl_reader.exe suchen
    info "Suche rapl_reader.exe..."

    # cmd.exe gibt UNC-Warnungen auf stdout aus – diese herausfiltern.
    # Warnzeilen starten mit '"\\' oder enthalten 'UNC' / 'CMD.EXE' / 'Stattdessen'
    # cmd.exe gibt \r am Zeilenende - tr -d entfernt das sauber

    EXISTING_ENV=$(cmd.exe /c "cd /d C:\\ && echo %RAPL_READER_EXE%" 2>/dev/null \
        | tr -d '\r' | grep -v '^$' | grep -v '^%' | head -1)
    if [[ -n "$EXISTING_ENV" && "$EXISTING_ENV" != "%RAPL_READER_EXE%" ]]; then
        printf "%s
" "  [OK]  RAPL_READER_EXE bereits gesetzt: $EXISTING_ENV"
        RAPL_EXE_PATH="$EXISTING_ENV"
        ENV_VAR_SET=true
    fi

    if [[ -z "$RAPL_EXE_PATH" ]]; then
        WIN_USERPROFILE=$(cmd.exe /c "cd /d C:\\ && echo %USERPROFILE%" 2>/dev/null \
            | tr -d '\r' | grep -v '^$' | head -1)
        SEARCH_PATHS=('C:\rapl\rapl_reader.exe' 'C:\Users\Public\rapl\rapl_reader.exe')
        [[ -n "$WIN_USERPROFILE" && "$WIN_USERPROFILE" != "%USERPROFILE%" ]] \
            && SEARCH_PATHS+=("${WIN_USERPROFILE}\\rapl\\rapl_reader.exe")

        for candidate in "${SEARCH_PATHS[@]}"; do
            EXISTS=$(cmd.exe /c "cd /d C:\\ && if exist ${candidate} echo YES" 2>/dev/null \
                | tr -d '\r' | grep -v '^$' | head -1)
            if [[ "$EXISTS" == "YES" ]]; then
                ok "rapl_reader.exe gefunden: $candidate"
                RAPL_EXE_PATH="$candidate"
                break
            fi
        done
    fi

    [[ -z "$RAPL_EXE_PATH" ]] \
        && err "rapl_reader.exe nicht gefunden → build_and_deploy.bat ausführen"

    # Umgebungsvariable setzen
    if [[ -n "$RAPL_EXE_PATH" && "$ENV_VAR_SET" == "false" ]]; then
        info "Setze RAPL_READER_EXE..."
        if [[ "$DRY_RUN" == "true" ]]; then
            info "[DRY-RUN] würde setzen: RAPL_READER_EXE=$RAPL_EXE_PATH"
        else
            SET_RESULT=$(cmd.exe /c "cd /d C:\\\\ && powershell.exe -NoProfile -Command \
                \"[System.Environment]::SetEnvironmentVariable('RAPL_READER_EXE', \
                '${RAPL_EXE_PATH}', 'Machine'); Write-Host 'OK'\"" \
                2>/dev/null | grep -vE '^"|UNC|CMD.EXE|Stattdessen' | tr -d '\r\n' || echo "FAILED")
            if [[ "$SET_RESULT" == *"OK"* ]]; then
                ok "RAPL_READER_EXE gesetzt: $RAPL_EXE_PATH"
                warn "WSL2 neu starten: wsl --shutdown  (Windows PowerShell)"
                ENV_VAR_SET=true
            else
                warn "Automatisch setzen fehlgeschlagen → manuell (PowerShell als Admin):"
                warn "  [System.Environment]::SetEnvironmentVariable("
                warn "      'RAPL_READER_EXE', '${RAPL_EXE_PATH}', 'Machine')"
            fi
        fi
    fi

    # Funktionstest
    if [[ "$DRIVER_RUNNING" == "true" && -n "$RAPL_EXE_PATH" ]]; then
        info "Teste RAPL Lesezugriff..."
        CHECK_EXIT=0
        cmd.exe /c "cd /d C:\\ && ${RAPL_EXE_PATH} -c" 2>/dev/null || CHECK_EXIT=$?
        if [[ "$CHECK_EXIT" == "0" ]]; then
            ok "RAPL MSR Lesezugriff funktioniert"
        else
            err "Lesezugriff fehlgeschlagen → Testmodus prüfen:"
            err "  bcdedit /enum | findstr testsigning"
        fi
    fi
fi

# =============================================================================
# SCHRITT 3 – CPU Detection
# =============================================================================
hdr "Schritt 3: CPU-Erkennung"

CPU_VENDOR=""; CPU_MODEL=""
DOMAIN_PKG=true; DOMAIN_CORES=true
DOMAIN_GPU=false; DOMAIN_DRAM=false; DOMAIN_PSYS=false

if [[ -f /proc/cpuinfo ]]; then
    CPU_VENDOR=$(grep -m1 "vendor_id"  /proc/cpuinfo | awk '{print $3}'    || echo "unknown")
    CPU_MODEL=$(grep -m1  "model name" /proc/cpuinfo | cut -d: -f2 | xargs || echo "unknown")
    ok "CPU:    $CPU_MODEL"
    ok "Vendor: $CPU_VENDOR"
fi

if [[ "$CPU_VENDOR" == "GenuineIntel" ]]; then
    info "Intel CPU – prüfe RAPL Domains..."

    if [[ "$IS_WSL" == "true" && -n "$RAPL_EXE_PATH" && "$DRIVER_RUNNING" == "true" ]]; then
        info "Live-Test via rapl_reader.exe (3 Sekunden)..."
        RAPL_OUTPUT=$(timeout 4 bash -c \
            "cmd.exe /c '${RAPL_EXE_PATH} -i 500' 2>/dev/null" || true)
        echo "$RAPL_OUTPUT" | grep -q "cpu_package" && { DOMAIN_PKG=true;   ok "cpu_package: aktiv"; }
        echo "$RAPL_OUTPUT" | grep -q "cpu_cores"   && { DOMAIN_CORES=true;  ok "cpu_cores:   aktiv"; }
        echo "$RAPL_OUTPUT" | grep -q "cpu_gpu"     && { DOMAIN_GPU=true;    ok "cpu_gpu:     aktiv"; }
        echo "$RAPL_OUTPUT" | grep -q "dram"        && { DOMAIN_DRAM=true;   ok "dram:        aktiv"; }
        echo "$RAPL_OUTPUT" | grep -q "psys"        && { DOMAIN_PSYS=true;   ok "psys:        aktiv"; }
        [[ "$DOMAIN_GPU"  == "false" ]] && info "cpu_gpu:  nicht erkannt → deaktiviert"
        [[ "$DOMAIN_DRAM" == "false" ]] && info "dram:     nicht erkannt → deaktiviert"
        [[ "$DOMAIN_PSYS" == "false" ]] && info "psys:     nicht erkannt → deaktiviert"
    else
        # Heuristik via CPU-Generation
        CPU_FAMILY=$(grep -m1 "cpu family" /proc/cpuinfo | awk '{print $NF}' || echo "0")
        CPU_MODEL_NUM=$(grep -m1 "^model\s" /proc/cpuinfo | awk '{print $NF}' || echo "0")
        if [[ "$CPU_FAMILY" == "6" && "$CPU_MODEL_NUM" -ge 78 ]]; then
            DOMAIN_PSYS=true
            info "PSYS: heuristisch aktiviert (Skylake+, Model $CPU_MODEL_NUM)"
        fi
        info "DRAM/GPU: kein Live-Test möglich → deaktiviert"
    fi

elif [[ "$CPU_VENDOR" == "AuthenticAMD" ]]; then
    warn "AMD: cpu_gpu, dram und psys nicht unterstützt"
else
    warn "Unbekannter Vendor: $CPU_VENDOR – Defaults verwendet"
fi

if [[ "$IS_NATIVE_LINUX" == "true" ]]; then
    if [[ -d /sys/class/powercap/intel-rapl ]]; then
        ok "Linux RAPL: /sys/class/powercap/intel-rapl gefunden"
        info "Für native Linux VM: Linux MSR Provider empfohlen"
    else
        warn "/sys/class/powercap/intel-rapl nicht gefunden"
        warn "  → sudo modprobe intel_rapl_common"
    fi
fi

# =============================================================================
# SCHRITT 4 – config.example.windows via Python generieren
# =============================================================================
hdr "Schritt 4: config.example.windows generieren"

# Alle erkannten Werte als Env-Variablen an Python übergeben
export GMT_CPU_VENDOR="$CPU_VENDOR"
export GMT_CPU_MODEL="$CPU_MODEL"
export GMT_WSL_VERSION="${WSL_VERSION:-native}"
export GMT_DOMAIN_PKG="$DOMAIN_PKG"
export GMT_DOMAIN_CORES="$DOMAIN_CORES"
export GMT_DOMAIN_GPU="$DOMAIN_GPU"
export GMT_DOMAIN_DRAM="$DOMAIN_DRAM"
export GMT_DOMAIN_PSYS="$DOMAIN_PSYS"
export GMT_SOURCE_CONFIG="$SOURCE_CONFIG"
export GMT_OUTPUT_CONFIG="$OUTPUT_CONFIG"
export GMT_DRY_RUN="$DRY_RUN"

# Python-Script inline – liest config.yml, baut config.example.windows
$PYTHON << 'PYEOF'
import os, sys, yaml, datetime

# Env-Variablen lesen
cpu_vendor    = os.environ.get("GMT_CPU_VENDOR",   "unknown")
cpu_model     = os.environ.get("GMT_CPU_MODEL",    "unknown")
wsl_version   = os.environ.get("GMT_WSL_VERSION",  "native")
domain_pkg    = os.environ.get("GMT_DOMAIN_PKG",   "true")  == "true"
domain_cores  = os.environ.get("GMT_DOMAIN_CORES", "true")  == "true"
domain_gpu    = os.environ.get("GMT_DOMAIN_GPU",   "false") == "true"
domain_dram   = os.environ.get("GMT_DOMAIN_DRAM",  "false") == "true"
domain_psys   = os.environ.get("GMT_DOMAIN_PSYS",  "false") == "true"
source_config = os.environ.get("GMT_SOURCE_CONFIG", "config.yml")
output_config = os.environ.get("GMT_OUTPUT_CONFIG", "config.example.windows")
dry_run       = os.environ.get("GMT_DRY_RUN",      "false") == "true"

yn = lambda v: "true" if v else "false"
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# -----------------------------------------------------------------------
# config.yml parsen und alle Werte extrahieren
# -----------------------------------------------------------------------
with open(source_config, "r") as f:
    cfg = yaml.safe_load(f)

# Alle Top-Level-Blöcke die wir 1:1 übernehmen (nicht metric_providers)
def get(key, default=None):
    return cfg.get(key, default)

# Postgres
pg = get("postgresql", {})
pg_host      = pg.get("host",          "green-coding-postgres-container")
pg_user      = pg.get("user",          "postgres")
pg_dbname    = pg.get("dbname",        "green-coding")
pg_password  = pg.get("password",      "test1234")
pg_port      = pg.get("port",          9573)
pg_retry     = pg.get("retry_timeout", 300)

# Redis
rd = get("redis", {})
rd_host = rd.get("host", "green-coding-redis-container")
rd_port = rd.get("port", 6379)

# SMTP
sm = get("smtp", {})
sm_server   = sm.get("server",   "SMTP_SERVER")
sm_sender   = sm.get("sender",   "SMTP_SENDER")
sm_port     = sm.get("port",     "SMTP_PORT")
sm_password = sm.get("password", "SMTP_AUTH_PW")
sm_user     = sm.get("user",     "SMTP_AUTH_USER")

# Admin
ad = get("admin", {})
ad_notif  = ad.get("notification_email", False)
ad_efile  = ad.get("error_file",         False)
ad_email  = ad.get("error_email",        False)
ad_bcc    = ad.get("email_bcc",          False)

# Cluster
cl = get("cluster", {})
cl_api     = cl.get("api_url",     "http://api.green-coding.internal:9142")
cl_metrics = cl.get("metrics_url", "http://metrics.green-coding.internal:9142")
cl_cors    = cl.get("cors_allowed_origins", [
    "http://api.green-coding.internal:9142",
    "http://metrics.green-coding.internal:9142",
    "http://localhost:9142",
])
cl_client  = cl.get("client", {})
cl_sleep     = cl_client.get("sleep_time_no_job",  300)
cl_jobs      = cl_client.get("jobs_processing",    "random")
cl_update_os = cl_client.get("update_os_packages", True)
cl_shutdown  = cl_client.get("shutdown_on_job_no", "suspend")
cl_prune     = cl_client.get("docker_prune",       False)
cl_fprune    = cl_client.get("full_docker_prune",  True)
cl_tbcwv     = cl_client.get("time_between_control_workload_validations", 21600)
cl_scwsm     = cl_client.get("send_control_workload_status_mail",         False)

# Machine
mc = get("machine", {})
mc_id    = mc.get("id",          1)
mc_desc  = mc.get("description", "Development machine")
mc_bval  = mc.get("base_temperature_value",   False)
mc_bchip = mc.get("base_temperature_chip",    False)
mc_bfeat = mc.get("base_temperature_feature", False)
mc_cpus  = mc.get("host_reserved_cpus",   1)
mc_mem   = mc.get("host_reserved_memory", 0)

# Measurement extras
ms = get("measurement", {})
ms_prune_whitelist = ms.get("full_docker_prune_whitelist",
                            ["gcr.io/kaniko-project/executor"])

# SCI
sc = get("sci", {})
sc_el = sc.get("EL", 4)
sc_rs = sc.get("RS", 1)
sc_te = sc.get("TE", 181000)
sc_i  = sc.get("I",  334)
sc_n  = sc.get("N",  0.04106063)

# Feature Flags
act_runner  = get("activate_scenario_runner", True)
act_eco     = get("activate_eco_ci",          True)
act_hog     = get("activate_power_hog",       True)
act_carbon  = get("activate_carbon_db",       True)
act_ai      = get("activate_ai",              False)
ee_token    = get("ee_token",                 False)

# CORS als YAML-Block
cors_lines = "\n".join(f"      - {u}" for u in cl_cors)

# Prune whitelist
prune_lines = "\n".join(f"    - {e}" for e in ms_prune_whitelist)

# Bool → Python YAML Stil
def yb(v):
    if v is True:  return "True"
    if v is False: return "False"
    return str(v)

# -----------------------------------------------------------------------
# Config zusammenbauen
# -----------------------------------------------------------------------
output = f"""# =============================================================================
# config.example.windows
#
# GMT Konfiguration optimiert für Windows + WSL2 mit RAPL Energiemessung.
# Gespiegelt von config.yml + Windows-spezifische Anpassungen.
# Generiert von setup_windows_rapl.sh am {now}
#
# Quell-Config: {source_config}
# CPU:          {cpu_model}
# Vendor:       {cpu_vendor}
# System:       {wsl_version}
#
# Verwendung:
#   cp config.yml config.yml.backup
#   cp config.example.windows config.yml
# =============================================================================

postgresql:
  host: {pg_host}
  #host: 127.0.0.1
  user: {pg_user}
  dbname: {pg_dbname}
  password: {pg_password}
  port: {pg_port}
  retry_timeout: {pg_retry}

redis:
  host: {rd_host}
  port: {rd_port}

smtp:
  server: {sm_server}
  sender: {sm_sender}
  port: {sm_port}
  password: {sm_password}
  user: {sm_user}

admin:
  notification_email: {yb(ad_notif)}
  error_file: {yb(ad_efile)}
  error_email: {yb(ad_email)}
  email_bcc: {yb(ad_bcc)}

cluster:
  api_url: {cl_api}
  metrics_url: {cl_metrics}
  cors_allowed_origins:
{cors_lines}
  client:
    sleep_time_no_job: {cl_sleep}
    jobs_processing: "{cl_jobs}"
    update_os_packages: {yb(cl_update_os)}
    shutdown_on_job_no: {cl_shutdown}
    docker_prune: {yb(cl_prune)}
    full_docker_prune: {yb(cl_fprune)}
    time_between_control_workload_validations: {cl_tbcwv}
    send_control_workload_status_mail: {yb(cl_scwsm)}
    control_workload:
      name: "Measurement control Workload"
      uri: "https://github.com/green-coding-solutions/measurement-control-workload"
      filename: "usage_scenario.yml"
      branch: "event-bound"
      comparison_window: 5
      phase: "004_[RUNTIME]"
      metrics:
        psu_energy_ac_mcp_machine:
          threshold: 0.01
          type: stddev_rel
        psu_power_ac_mcp_machine:
          threshold: 0.01
          type: stddev_rel
        cpu_power_rapl_msr_component:
          threshold: 0.01
          type: stddev_rel
        cpu_energy_rapl_msr_component:
          threshold: 0.01
          type: stddev_rel
        psu_carbon_ac_mcp_machine:
          threshold: 0.01
          type: stddev_rel
        network_total_cgroup_container:
          threshold: 10000
          type: stddev
        phase_time_syscall_system:
          threshold: 0.01
          type: stddev_rel

machine:
  id: {mc_id}
  description: "{mc_desc} (Windows WSL2)"
  base_temperature_value: {yb(mc_bval)}
  base_temperature_chip: {yb(mc_bchip)}
  base_temperature_feature: {yb(mc_bfeat)}
  host_reserved_cpus: {mc_cpus}
  host_reserved_memory: {mc_mem}

measurement:
  full_docker_prune_whitelist:
{prune_lines}
  metric_providers:

    #--- Architecture - Linux Only
    linux:
    #--- Systemauslastung – läuft auch in WSL2
      cpu.utilization.procfs.system.provider.CpuUtilizationProcfsSystemProvider:
        sampling_rate: 99

    #--- CGroupV2 – läuft in WSL2 wenn cgroup v2 aktiv
    #   Prüfen: cat /proc/filesystems | grep cgroup2
      cpu.utilization.cgroup.container.provider.CpuUtilizationCgroupContainerProvider:
        sampling_rate: 99
      memory.used.cgroup.container.provider.MemoryUsedCgroupContainerProvider:
        sampling_rate: 99
      network.io.cgroup.container.provider.NetworkIoCgroupContainerProvider:
        sampling_rate: 99
      disk.io.cgroup.container.provider.DiskIoCgroupContainerProvider:
        sampling_rate: 99

    #--- Linux RAPL – NUR für native Linux VM, NICHT für WSL2!
    #   Für WSL2 → Windows RAPL Provider weiter unten unter common: verwenden
#      cpu.energy.rapl.msr.component.provider.CpuEnergyRaplMsrComponentProvider:
#        sampling_rate: 99
#      memory.energy.rapl.msr.component.provider.MemoryEnergyRaplMsrComponentProvider:
#        sampling_rate: 99

    #--- Machine Energy – Spezielle Hardware / Lab-Equipment nötig
#      psu.energy.ac.gude.machine.provider.PsuEnergyAcGudeMachineProvider:
#        sampling_rate: 99
#      psu.energy.ac.powerspy2.machine.provider.PsuEnergyAcPowerspy2MachineProvider:
#        sampling_rate: 250
#      psu.energy.ac.mcp.machine.provider.PsuEnergyAcMcpMachineProvider:
#        sampling_rate: 99
#      psu.energy.ac.ipmi.machine.provider.PsuEnergyAcIpmiMachineProvider:
#        sampling_rate: 99
#      psu.energy.dc.rapl.msr.machine.provider.PsuEnergyDcRaplMsrMachineProvider:
#        sampling_rate: 99

    #--- GPU – Nur wenn NVIDIA GPU mit Power Measurement vorhanden
#      gpu.energy.nvidia.nvml.component.provider.GpuEnergyNvidiaNvmlComponentProvider:
#        sampling_rate: 99

    #--- Sensoren – lm-sensors nötig: sudo apt install lm-sensors && sensors-detect
#      lmsensors.temperature.component.provider.LmsensorsTemperatureComponentProvider:
#        sampling_rate: 99
#        chips: ['coretemp-isa-0000']
#        features: ['Package id 0', 'Core 0', 'Core 1']
#      lmsensors.fan.component.provider.LmsensorsFanComponentProvider:
#        sampling_rate: 99
#        chips: ['thinkpad-isa-0000']
#        features: ['fan1', 'fan2']

    #--- Debug – nur für Fehlersuche
#      cpu.throttling.msr.component.provider.CpuThrottlingMsrComponentProvider:
#        sampling_rate: 99
#      cpu.frequency.sysfs.core.provider.CpuFrequencySysfsCoreProvider:
#        sampling_rate: 99
#      cpu.time.cgroup.container.provider.CpuTimeCgroupContainerProvider:
#        sampling_rate: 99
#      disk.io.procfs.system.provider.DiskIoProcfsSystemProvider:
#        sampling_rate: 99
#      network.io.procfs.system.provider.NetworkIoProcfsSystemProvider:
#        sampling_rate: 99
#        remove_virtual_interfaces: True
#      memory.used.procfs.system.provider.MemoryUsedProcfsSystemProvider:
#        sampling_rate: 99

    #--- Architecture - MacOS
    macos:
#      powermetrics.provider.PowermetricsProvider:
#        sampling_rate: 499
#      cpu.utilization.mach.system.provider.CpuUtilizationMachSystemProvider:
#        sampling_rate: 99

    #--- Architecture - Common
    common:
      # -----------------------------------------------------------------------
      # Windows RAPL Provider (WSL2 → ScaphandreDrv → rapl_reader.exe)
      #
      # Voraussetzungen (einmalig auf Windows, als Admin):
      #   1. Testmodus + Neustart:
      #        bcdedit -set TESTSIGNING ON
      #        bcdedit -set nointegritychecks on
      #   2. Treiber installieren + starten:
      #        DriverLoader.exe install
      #        sc.exe start ScaphandreDrv
      #   3. rapl_reader.exe kompilieren (VS 2022 x64 Native Tools Prompt):
      #        build_and_deploy.bat
      #   4. Umgebungsvariable (setup_windows_rapl.sh erledigt das automatisch):
      #        [System.Environment]::SetEnvironmentVariable(
      #            'RAPL_READER_EXE', 'C:\\rapl\\rapl_reader.exe', 'Machine')
      #        danach: wsl --shutdown
      #
      # CPU erkannt:     {cpu_model}
      # Domains erkannt: {now}
      # -----------------------------------------------------------------------
      cpu.energy.rapl.scaphandre.component.provider.CpuEnergyRaplScaphandreComponentProvider:
        sampling_rate: 99
        # Pfad wird automatisch aus Windows-Umgebungsvariable RAPL_READER_EXE gelesen.
        # Nur manuell eintragen falls die Env-Var nicht gesetzt werden kann:
        # rapl_reader_exe: 'C:\\\\rapl\\\\rapl_reader.exe'
        domains:
          cpu_package: {yn(domain_pkg)}    # Gesamtverbrauch CPU-Package
          cpu_cores:   {yn(domain_cores)}  # Rechenkerne (PP0)
          cpu_gpu:     {yn(domain_gpu)}    # Integrierte GPU (PP1) – Beta
          dram:        {yn(domain_dram)}   # Arbeitsspeicher – nur wenn CPU unterstützt
          psys:        {yn(domain_psys)}   # Platform Energy – Skylake (6. Gen)+

#      network.connections.proxy.container.provider.NetworkConnectionsProxyContainerProvider:
##        host_ip: 192.168.1.2

    #--- Modellbasierte Provider – schätzen statt messen
#      psu.energy.ac.sdia.machine.provider.PsuEnergyAcSdiaMachineProvider:
#        CPUChips: 1
#        TDP: 65
#      psu.energy.ac.xgboost.machine.provider.PsuEnergyAcXgboostMachineProvider:
#        CPUChips: 1
#        HW_CPUFreq: 3200
#        CPUCores: 4
#        CPUThreads: 4
#        TDP: 65
#        HW_MemAmountGB: 16
#        Hardware_Availability_Year: 2011
#        VHost_Ratio: 1

sci:
  EL: {sc_el}
  RS: {sc_rs}
  # TE: Embodied Emissions in gCO2eq
  # Wert für Entwickler-Laptop: https://dataviz.boavizta.org/terminalimpact
  TE: {sc_te}
  # I: Carbon Intensity am Standort in gCO2e/kWh
  # Deutschland 2024: 334  https://app.electricitymaps.com/zone/DE/all/yearly
  # Weltweit 2024:    473  https://ember-climate.org
  I: {sc_i}
  N: {sc_n}

#electricity_maps_token: '123'

activate_scenario_runner: {yb(act_runner)}
activate_eco_ci: {yb(act_eco)}
activate_power_hog: {yb(act_hog)}
activate_carbon_db: {yb(act_carbon)}
activate_ai: {yb(act_ai)}

ee_token: {yb(ee_token)}
"""

if dry_run:
    print(f"  [DRY-RUN] würde schreiben: {output_config}")
    print(f"  [DRY-RUN] Postgres: {pg_host}:{pg_port}/{pg_dbname} user={pg_user}")
    print(f"  [DRY-RUN] Redis:    {rd_host}:{rd_port}")
    print(f"  [DRY-RUN] SCI:      EL={sc_el} TE={sc_te} I={sc_i}")
else:
    with open(output_config, "w") as f:
        f.write(output)
    print(f"  [OK]  Geschrieben: {output_config}")
    # Kurze Zusammenfassung übernommener Werte
    print(f"  [OK]  Postgres:   {pg_host}:{pg_port}/{pg_dbname}")
    print(f"  [OK]  Redis:      {rd_host}:{rd_port}")
    print(f"  [OK]  SCI:        EL={sc_el} / TE={sc_te} / I={sc_i}")

PYEOF

# =============================================================================
# SCHRITT 5 – Diagnose-Report
# =============================================================================
hdr "Diagnose-Report"

ISSUES=0

if [[ "$IS_WSL" == "true" ]]; then
    echo -e "\n${BOLD}Windows / Treiber:${RESET}"
    if [[ "$DRIVER_RUNNING" == "true" ]]; then
        ok "ScaphandreDrv läuft"
    else
        err "ScaphandreDrv nicht aktiv"
        echo "       → cmd.exe /c 'sc start ScaphandreDrv'  (als Admin)"
        ISSUES=$((ISSUES + 1))
    fi

    if [[ -n "$RAPL_EXE_PATH" ]]; then
        ok "rapl_reader.exe: $(echo "$RAPL_EXE_PATH" | tr -d "\r")"
    else
        err "rapl_reader.exe nicht gefunden"
        echo "       → build_and_deploy.bat  (VS 2022 x64 Native Tools Prompt)"
        ISSUES=$((ISSUES + 1))
    fi

    if [[ "$ENV_VAR_SET" == "true" ]]; then
        ok "RAPL_READER_EXE gesetzt"
        warn "Nicht vergessen: wsl --shutdown  (Windows PowerShell)"
    else
        err "RAPL_READER_EXE nicht gesetzt"
        echo "       → Script erneut ausführen wenn rapl_reader.exe vorhanden"
        ISSUES=$((ISSUES + 1))
    fi
fi

echo -e "\n${BOLD}CPU / RAPL Domains:${RESET}"
ok   "cpu_package: $DOMAIN_PKG"
ok   "cpu_cores:   $DOMAIN_CORES"
[[ "$DOMAIN_GPU"  == "true" ]] && ok "cpu_gpu:     true" || info "cpu_gpu:     false"
[[ "$DOMAIN_DRAM" == "true" ]] && ok "dram:        true" || info "dram:        false"
[[ "$DOMAIN_PSYS" == "true" ]] && ok "psys:        true" || info "psys:        false"

echo -e "\n${BOLD}Nächste Schritte:${RESET}"
if [[ "$DRY_RUN" == "false" ]]; then
    echo "  1. Config prüfen:  cat $OUTPUT_CONFIG"
    if [[ "$IS_WSL" == "true" ]]; then
        echo "  2. wsl --shutdown  (Windows PowerShell)"
        echo "  3. WSL2 neu öffnen"
        echo "  4. Config übernehmen:"
    else
        echo "  2. Config übernehmen:"
    fi
    echo "       cp $GMT_DIR/config.yml $GMT_DIR/config.yml.backup"
    echo "       cp $OUTPUT_CONFIG $GMT_DIR/config.yml"
    echo "  5. GMT testen:"
    echo "       cd $GMT_DIR && source venv/bin/activate"
    echo "       python3 runner.py --uri $GMT_DIR \\"
    echo "         --filename tests/usage_the_test.yml \\"
    echo "         --variable __GMT_VAR_CPU_DURATION__=10s \\"
    echo "         --variable __GMT_VAR_RAM_MB__=512 \\"
    echo "         --variable __GMT_VAR_RAM_DURATION__=10s"
fi

echo ""
if [[ "$ISSUES" -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}Alles bereit!${RESET}"
else
    echo -e "${YELLOW}${BOLD}$ISSUES Problem(e) offen – siehe Report oben.${RESET}"
fi
