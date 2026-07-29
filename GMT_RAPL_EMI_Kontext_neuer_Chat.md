# Kontext: RAPL-Energiemessung via Windows Energy Meter Interface (EMI)

**Zweck:** Einstiegskontext für einen neuen Chat/Cowork-Sitzung im Ordner `C:\Users\jahns\Documents\CASO\gmt-windows-2.1`. Ziel: den bestehenden RAPL-Provider (aktuell via ScaphandreDrv-Kerneltreiber, Test-Mode-Anforderung) durch eine Lösung auf Basis der offiziellen Windows Energy Meter Interface (EMI) ersetzen bzw. ergänzen — ohne Custom-Kerneltreiber, ohne Test-Mode.

---

## 1. Ausgangslage

**Aktuelle Lösung:** `metric_providers/cpu/energy/rapl/scaphandre/component/` — nutzt den ScaphandreDrv-Kerneltreiber, um RAPL-MSRs auszulesen. Nachteil: benötigt einen signierten oder im Test-Mode laufenden Kerneltreiber, was Installation/Vertrauenswürdigkeit erschwert (Test-Mode-Warnhinweis bei jedem Windows-Start, Signierungsanforderungen für Produktivsysteme).

**Bereits vorhandene Teillösung:** GMT-PR [#1648](https://github.com/green-coding-solutions/green-metrics-tool/pull/1648) — löst das Problem teilweise, aber nicht vollständig (Details dort nachzulesen, nicht Teil dieser Übergabe).

**Ziel-Ansatz:** Weg von Scaphandre, hin zur **Windows Energy Meter Interface (EMI)** — offizielle Microsoft-Dokumentation: https://learn.microsoft.com/en-us/windows-hardware/drivers/powermeter/energy-meter-interface

**Warum EMI attraktiv ist:**
- Windows 11 liefert einen **inbox driver** mit, der RAPL-MSRs bereits an die EMI-Geräteschnittstelle bridged — kein eigener Kerneltreiber nötig, kein Test-Mode.
- Laut Kommentar im Referenzcode: **Administrator-Rechte nicht erforderlich** (im Gegensatz zum bisherigen MSR-Zugriff, der i. d. R. erhöhte Rechte braucht).
- **Wichtige Einschränkung:** Auf Windows 10 liefert das nur Daten, wenn dedizierte Hardware-Energiemeter vorhanden sind (z. B. Surface Book 1) — für die meisten Systeme ist das **Windows-11-only**. Vorab klären, ob das Zielsystem/die Zielsysteme (dein Entwicklungsrechner, potenzielle spätere Nutzer) Windows 11 haben.

## 2. Vorarbeit des Kollegen — wichtige Einordnung

Der Kollege hat einen ersten Entwurf (`emi_rapl.c`) gepostet, **explizit als "meine ChatGPT-Lösung gerade"** gekennzeichnet. Das heißt für den neuen Chat:

- **Der Code ist ein Ausgangspunkt, kein verifizierter, funktionierender Stand.** Er wurde nach unserem heutigen Kenntnisstand **nicht kompiliert oder getestet**.
- Sollte vor jeder Weiterverwendung sorgfältig geprüft werden — insbesondere:
  - Ob `emi.h` (referenziert als "Windows SDK >= 10.0.14393") auf dem tatsächlichen Build-System vorhanden ist
  - Ob die IOCTL-Calls (`IOCTL_EMI_GET_VERSION`, `IOCTL_EMI_GET_METADATA_SIZE`, `IOCTL_EMI_GET_METADATA`, `IOCTL_EMI_GET_MEASUREMENT`) und Strukturen (`EMI_METADATA_V1`/`V2`, `EMI_MEASUREMENT_DATA_V1`, `EMI_CHANNEL_MEASUREMENT_DATA`) exakt der SDK-Definition entsprechen — KI-generierter Code neigt dazu, bei wenig dokumentierten/seltenen APIs plausibel aussehende, aber nicht exakt korrekte Struct-Layouts oder Konstanten zu erzeugen
  - Ob `GUID_DEVICE_ENERGY_METER` korrekt referenziert ist und ob dafür ein zusätzlicher Header/Lib eingebunden werden muss
- **Empfehlung für den neuen Chat:** Vor dem Weiterbauen erst einen **minimalen Kompilier- und Ausführungstest** des vorhandenen Entwurfs machen (analog zu unserem heutigen Vorgehen bei den CPU-Providern: erst `-c`/Diagnose-Test, dann Loop-Test, mit Task-Manager/Referenzwerten gegenprüfen), um zu sehen, ob der Ansatz auf dem konkreten Windows-11-System überhaupt Daten liefert, bevor Zeit in Feinschliff investiert wird.

Der vollständige Code liegt als Referenz vor (siehe Anhang unten oder separat mitgegebene Datei) — im neuen Chat direkt einfügen/hochladen.

## 3. Technische Umgebung

- **Neuer Arbeitsordner:** `C:\Users\jahns\Documents\CASO\gmt-windows-2.1` (Kopie von `gmt-windows-2.0\gmt-windows-native`, per `robocopy` erstellt)
- **Zugriff:** Cowork/Claude Desktop mit diesem Ordner als Projektordner
- **Bekannter Stolperstein, sofort zu beheben:** `config.yml` und `docker\compose.yml` enthalten nach dem Kopieren weiterhin **absolute Pfade zum alten Ordner** (`gmt-windows-2.0`). Docker-Mounts würden sonst falsch zeigen (identisches Problem wie heute mit dem alten `GMT-09.06.2026`-Checkout). **Vor dem ersten Docker-Start entweder:**
  - `install_windows.ps1` im neuen Ordner erneut ausführen (baut `config.yml`/`docker\compose.yml` mit korrektem, neuem Pfad neu auf), oder
  - Pfade manuell in beiden Dateien von `gmt-windows-2.0` auf `gmt-windows-2.1` anpassen
- **Git:** Beide Ordner (`2.0` und `2.1`) sind unabhängige Klones desselben Repos mit denselben Remotes (`origin`, `fork`). Für diese Arbeit empfiehlt sich ein **neuer, eigener Branch** im `2.1`-Ordner (z. B. `rapl-emi-windows`), um Überschneidungen mit den bereits offenen PRs (`cpu-utilization-windows-native`, `sbom-windows-native`) zu vermeiden.

## 4. Etablierte GMT-Windows-Provider-Konventionen (aus heutiger Arbeit)

Diese Muster hatten sich beim Bau der CPU-Utilization-Provider bewährt und sollten für den EMI-Provider übernommen werden:

- **Zeitgeber:** `QueryPerformanceCounter`/`GetSystemTimeAsFileTime` für monotone, hochauflösende Timestamps mit einmaligem Wanduhr-Ankerpunkt (verhindert doppelte/nicht-monotone Timestamps bei Windows' ~15ms-Wanduhr-Auflösung). Der EMI-Entwurf nutzt aktuell nur `GetLocalTime()` für die Konsolen-Ausgabe — für die GMT-Integration muss das durch das etablierte `clock_state_t`-Pattern ersetzt werden.
- **Sampling-Loop:** **Fester** `Sleep(interval_ms)` zwischen Snapshots — **keine** QPC-Deadline-Kompensation (das hatten wir heute nach Review-Feedback bewusst wieder rausgenommen, da bei reinen Syscall-Messungen unnötig und potenziell fehleranfällig).
- **Prozesssteuerung (`provider.py`):** `start_profiling()`/`stop_profiling()`/`check_system()` selbst überschreiben, `lib/host_platform.py`-Funktionen nutzen (`popen_process_group_kwargs()`, `set_nonblocking()`), da `BaseMetricProvider`s generischer Pfad POSIX-only ist.
- **Output-Format:** `TIMESTAMP VALUE\n` (system-weit) oder `TIMESTAMP VALUE DETAIL_NAME\n` (mehrere Kanäle/Domains) — beim EMI-Provider vermutlich mehrere Kanäle (CPU-Package, DRAM, ggf. weitere je nach Hardware), also das `DETAIL_NAME`-Muster wie beim bestehenden RAPL-Scaphandre-Provider (`cpu_cores`, `cpu_gpu`, `cpu_package`, `psys`).
- **Unbuffered Output:** `setvbuf(stdout, NULL, _IONBF, 0)` am Anfang von `main()`.
- **Registrierung für Energie-Metriken:** Wichtiger Unterschied zu den Utilization-Providern von heute — `lib/phase_stats.py` hat für Energie-Metriken bereits eine **generische** Regel (`elif "_energy_" in metric and unit == 'uJ':`), die automatisch greift, **ohne** dass der Metric-Name explizit in eine Allowlist eingetragen werden muss (anders als bei `cpu_utilization_*`). Das bedeutet vermutlich **weniger Registrierungsaufwand** als beim CPU-Utilization-Provider — sollte aber am Code verifiziert werden, nicht nur angenommen.
- **Build:** `build.bat` nach demselben Muster (`cl.exe /O2 /W3 /nologo /link <benötigte .lib-Dateien>`), plus Ergänzung in `install_windows.ps1` (`Invoke-<Name>ProviderBuild`-Funktion, analog zu den drei bestehenden).

## 5. Referenzcode des Kollegen (EMI-Ansatz, ungetestet)

```c
/*
 * emi_rapl.c  –  Read CPU/DRAM energy via the Windows Energy Meter Interface
 *
 * On Windows 11, Microsoft ships an inbox driver that bridges RAPL MSRs to
 * the EMI device interface, so no custom kernel driver or test-mode is needed.
 * On Windows 10, output is only produced if the machine has hardware energy
 * meters (e.g. Surface Book 1).
 *
 * Compile (MSVC, x64 Native Tools Command Prompt):
 *   cl /W4 /O2 emi_rapl.c /link setupapi.lib
 *
 * Compile (MinGW-w64):
 *   gcc -O2 -Wall -o emi_rapl.exe emi_rapl.c -lsetupapi
 *
 * Run: emi_rapl.exe [interval_ms]   (default: 1000 ms)
 * Administrator rights are NOT required.
 *
 * Energy unit from the driver : picowatt-hours  (pWh)
 * Time  unit from the driver  : 100-nanosecond intervals (same as FILETIME)
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <setupapi.h>
#include <emi.h>          /* Windows SDK >= 10.0.14393  */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#pragma comment(lib, "setupapi.lib")

#define MAX_DEVICES     32
#define MAX_CHANNELS    32
#define COL_NAME        36

typedef struct {
    HANDLE  hDevice;
    USHORT  version;
    USHORT  channelCount;
    WCHAR  *channelNames[MAX_CHANNELS];
    ULONG   measureBufSize;
    ULONG64 prevEnergy[MAX_CHANNELS];
    ULONG64 prevTime  [MAX_CHANNELS];
    BOOL    hasPrev;
} EmiDevice;

static void print_timestamp(void)
{
    SYSTEMTIME st;
    GetLocalTime(&st);
    printf("[%04u-%02u-%02u %02u:%02u:%02u.%03u] ",
           st.wYear, st.wMonth,  st.wDay,
           st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
}

static const EMI_CHANNEL_V2 *next_channel_v2(const EMI_CHANNEL_V2 *ch)
{
    size_t nameBytes = (wcslen(ch->ChannelName) + 1) * sizeof(WCHAR);
    size_t stride    = FIELD_OFFSET(EMI_CHANNEL_V2, ChannelName) + nameBytes;
    stride = (stride + 7) & ~(size_t)7;
    return (const EMI_CHANNEL_V2 *)((const BYTE *)ch + stride);
}

static int open_emi_devices(EmiDevice *devs)
{
    int count = 0;
    HDEVINFO di = SetupDiGetClassDevs(
        &GUID_DEVICE_ENERGY_METER, NULL, NULL,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);

    if (di == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "SetupDiGetClassDevs failed (%lu)\n", GetLastError());
        return 0;
    }

    SP_DEVICE_INTERFACE_DATA iface;
    iface.cbSize = sizeof(iface);

    for (DWORD idx = 0;
         count < MAX_DEVICES &&
         SetupDiEnumDeviceInterfaces(di, NULL, &GUID_DEVICE_ENERGY_METER, idx, &iface);
         ++idx)
    {
        DWORD needed = 0;
        SetupDiGetDeviceInterfaceDetail(di, &iface, NULL, 0, &needed, NULL);

        SP_DEVICE_INTERFACE_DETAIL_DATA *detail =
            (SP_DEVICE_INTERFACE_DETAIL_DATA *)malloc(needed);
        if (!detail) continue;
        detail->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA);

        if (!SetupDiGetDeviceInterfaceDetail(di, &iface, detail, needed, NULL, NULL)) {
            free(detail);
            continue;
        }

        HANDLE h = CreateFile(
            detail->DevicePath,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            NULL, OPEN_EXISTING, 0, NULL);
        free(detail);

        if (h == INVALID_HANDLE_VALUE) {
            fprintf(stderr, "Warning: cannot open EMI device %d (%lu) – skipping\n",
                    count, GetLastError());
            continue;
        }

        EmiDevice *dev = &devs[count];
        memset(dev, 0, sizeof(*dev));
        dev->hDevice = h;

        DWORD ret;

        EMI_VERSION ver = {0};
        if (!DeviceIoControl(h, IOCTL_EMI_GET_VERSION,
                             NULL, 0, &ver, sizeof(ver), &ret, NULL)) {
            fprintf(stderr, "IOCTL_EMI_GET_VERSION failed (%lu)\n", GetLastError());
            CloseHandle(h);
            continue;
        }
        dev->version = ver.EmiVersion;
        if (dev->version != EMI_VERSION_V1 && dev->version != EMI_VERSION_V2) {
            fprintf(stderr, "Unsupported EMI version %u – skipping\n", dev->version);
            CloseHandle(h);
            continue;
        }

        EMI_METADATA_SIZE msize = {0};
        if (!DeviceIoControl(h, IOCTL_EMI_GET_METADATA_SIZE,
                             NULL, 0, &msize, sizeof(msize), &ret, NULL)) {
            fprintf(stderr, "IOCTL_EMI_GET_METADATA_SIZE failed (%lu)\n", GetLastError());
            CloseHandle(h);
            continue;
        }

        BYTE *meta = (BYTE *)malloc(msize.MetadataSize);
        if (!meta) { CloseHandle(h); continue; }

        if (!DeviceIoControl(h, IOCTL_EMI_GET_METADATA,
                             NULL, 0, meta, msize.MetadataSize, &ret, NULL)) {
            fprintf(stderr, "IOCTL_EMI_GET_METADATA failed (%lu)\n", GetLastError());
            free(meta); CloseHandle(h);
            continue;
        }

        if (dev->version == EMI_VERSION_V1) {
            const EMI_METADATA_V1 *m = (const EMI_METADATA_V1 *)meta;
            dev->channelCount    = 1;
            dev->channelNames[0] = _wcsdup(m->MeteredHardwareName);
            dev->measureBufSize  = sizeof(EMI_MEASUREMENT_DATA_V1);
        } else {
            const EMI_METADATA_V2   *m  = (const EMI_METADATA_V2 *)meta;
            USHORT nc = m->ChannelCount;
            if (nc > MAX_CHANNELS) nc = MAX_CHANNELS;
            dev->channelCount   = nc;
            dev->measureBufSize = nc * sizeof(EMI_CHANNEL_MEASUREMENT_DATA);

            const EMI_CHANNEL_V2 *ch = m->Channels;
            for (USHORT c = 0; c < nc; c++) {
                dev->channelNames[c] = _wcsdup(ch->ChannelName);
                ch = next_channel_v2(ch);
            }
        }

        free(meta);
        ++count;
    }

    SetupDiDestroyDeviceInfoList(di);
    return count;
}

static void sample_all(EmiDevice *devs, int count)
{
    for (int i = 0; i < count; i++) {
        EmiDevice *dev = &devs[i];

        BYTE *buf = (BYTE *)malloc(dev->measureBufSize);
        if (!buf) continue;

        DWORD ret;
        BOOL ok = DeviceIoControl(dev->hDevice, IOCTL_EMI_GET_MEASUREMENT,
                                  NULL, 0, buf, dev->measureBufSize, &ret, NULL);
        if (!ok) {
            fprintf(stderr, "IOCTL_EMI_GET_MEASUREMENT failed for device %d (%lu)\n",
                    i, GetLastError());
            free(buf);
            continue;
        }

        for (USHORT c = 0; c < dev->channelCount; c++) {
            ULONG64 energy, time100ns;

            if (dev->version == EMI_VERSION_V1) {
                const EMI_MEASUREMENT_DATA_V1 *m = (const EMI_MEASUREMENT_DATA_V1 *)buf;
                energy    = m->AbsoluteEnergy;
                time100ns = m->AbsoluteTime;
            } else {
                const EMI_CHANNEL_MEASUREMENT_DATA *m =
                    (const EMI_CHANNEL_MEASUREMENT_DATA *)buf + c;
                energy    = m->AbsoluteEnergy;
                time100ns = m->AbsoluteTime;
            }

            print_timestamp();
            double energy_mWh = (double)energy * 1e-9;
            printf("%-*ls  abs=%14.6f mWh", COL_NAME, dev->channelNames[c], energy_mWh);

            if (dev->hasPrev && time100ns > dev->prevTime[c]) {
                ULONG64 dE = energy    - dev->prevEnergy[c];
                ULONG64 dT = time100ns - dev->prevTime[c];
                double  pw = (double)dE * 0.036 / (double)dT;
                printf("  avg_power=%8.3f W", pw);
            }

            printf("\n");
            dev->prevEnergy[c] = energy;
            dev->prevTime[c]   = time100ns;
        }
        dev->hasPrev = TRUE;
        free(buf);
    }
    printf("\n");
}

int main(int argc, char *argv[])
{
    DWORD intervalMs = 1000;
    if (argc > 1) {
        int v = atoi(argv[1]);
        if (v > 0) intervalMs = (DWORD)v;
    }

    EmiDevice devs[MAX_DEVICES];
    int count = open_emi_devices(devs);

    if (count == 0) {
        fprintf(stderr,
            "\nNo EMI energy-meter devices found.\n"
            "  • Windows 11  → should work on any Intel/AMD system (inbox driver)\n"
            "  • Windows 10  → only works with dedicated hardware energy meters\n"
            "Ensure you are running a 64-bit OS and have not disabled the driver.\n");
        return 1;
    }

    printf("Found %d EMI device(s).  Sampling every %lu ms.  Ctrl+C to stop.\n\n",
           count, intervalMs);

    sample_all(devs, count);

    while (1) {
        Sleep(intervalMs);
        sample_all(devs, count);
    }

    for (int i = 0; i < count; i++) {
        CloseHandle(devs[i].hDevice);
        for (USHORT c = 0; c < devs[i].channelCount; c++)
            free(devs[i].channelNames[c]);
    }
    return 0;
}
```

## 6. Vorgeschlagene erste Schritte für den neuen Chat

1. **Windows-Version des Zielsystems prüfen** (`winver` oder `[System.Environment]::OSVersion.Version`) — Windows 11 zwingend für sinnvollen Test.
2. **Minimal-Kompiliertest** des vorhandenen Entwurfs (`cl /W4 /O2 emi_rapl.c /link setupapi.lib`), isoliert außerhalb der GMT-Provider-Struktur — prüfen, ob `emi.h` überhaupt gefunden wird, ob es kompiliert, ob `open_emi_devices()` tatsächlich Geräte findet.
3. **Bei Erfolg:** Werte gegen eine Referenz gegenprüfen (z. B. Task-Manager-Energieanzeige, falls vorhanden, oder den bereits funktionierenden Scaphandre-Provider parallel laufen lassen und Größenordnung vergleichen).
4. **Erst danach:** in die GMT-Provider-Struktur überführen (`metric_providers/cpu/energy/emi/component/` o. ä.), nach den in Abschnitt 4 beschriebenen Konventionen — Timing-Pattern austauschen, `provider.py` nach RAPL-Scaphandre-Vorbild bauen, `build.bat` + `install_windows.ps1`-Eintrag ergänzen.
5. **Vor Docker-Arbeit im neuen Ordner:** Pfad-Fix durchführen (Abschnitt 3).
