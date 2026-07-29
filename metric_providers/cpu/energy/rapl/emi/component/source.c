/*
 * source.c  —  CPU/DRAM energy via Windows Energy Meter Interface (EMI)
 *
 * Reads energy from all EMI devices (GUID_DEVICE_ENERGY_METER) and emits
 * delta energy in µJ per interval to stdout in GMT format.
 *
 * On Windows 11, the inbox PPM driver bridges RAPL MSRs to EMI automatically
 * — no custom kernel driver or test-mode required.
 * On Windows 10, output requires dedicated hardware energy meters.
 *
 * Output format (GMT standard):
 *   <timestamp_µs> <delta_µJ> <channel_name>
 *   1774007770584099 3614000 rapl_package0_pkg
 *
 * With multiple EMI devices, channel names are prefixed with dev{N}_:
 *   1774007770584099 3614000 dev0_rapl_package0_pkg
 *   1774007770584256  124000 dev1_gpu_power
 *
 * Usage:
 *   metric-provider-binary.exe -i <interval_ms>   (default: 99 ms)
 *   metric-provider-binary.exe -c                 (check: exit 0 if EMI is available)
 *
 * Compile (x64 Native Tools Command Prompt for VS 2022):
 *   cl source.c /Fe:metric-provider-binary /O2 /W3 /nologo /link setupapi.lib winmm.lib
 *
 * Energy unit from the driver : picowatt-hours (pWh)
 * Conversion to GMT unit (µJ) : 1 pWh = 0.0036 µJ
 * Time unit from the driver   : 100-nanosecond intervals (same as FILETIME)
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winioctl.h>   /* CTL_CODE, METHOD_BUFFERED, FILE_DEVICE_UNKNOWN   */
#include <initguid.h>   /* DEFINE_GUID instantiation — must come before emi.h */
#include <setupapi.h>
#include <emi.h>
#include <timeapi.h>    /* timeBeginPeriod / timeEndPeriod                   */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>

#pragma comment(lib, "setupapi.lib")
#pragma comment(lib, "winmm.lib")

/* ── Constants ──────────────────────────────────────────────────────────── */

#define MAX_DEVICES    8
#define MAX_CHANNELS   16
#define MAX_NAME_LEN   128

/* 1 pWh = 0.0036 µJ  (= 3.6e-12 Wh × 3.6e6 µJ/Wh × 1e12 pWh/Wh ... = 3.6e-3) */
#define PWH_TO_UJ      0.0036

/* ── Types ──────────────────────────────────────────────────────────────── */

typedef struct {
    LARGE_INTEGER qpc_start;
    uint64_t      wall_start_us;
    double        qpc_freq_us;
} clock_state_t;

/*
 * One named, measurable channel within an EMI device.
 * buf_index is the channel's original position in the measurement buffer,
 * which may differ from our array index when unnamed channels are skipped.
 */
typedef struct {
    char     name[MAX_NAME_LEN];
    USHORT   buf_index;
    uint64_t prev_energy;   /* last AbsoluteEnergy reading in pWh */
    int      has_prev;
} emi_channel_t;

typedef struct {
    HANDLE        handle;
    USHORT        version;
    USHORT        channel_count;     /* named channels only              */
    ULONG         measure_buf_size;  /* buffer for ALL channels (incl. unnamed) */
    emi_channel_t channels[MAX_CHANNELS];
} emi_device_t;

/* ── Clock ──────────────────────────────────────────────────────────────── */

static uint64_t get_wall_time_us(void)
{
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    uint64_t t = ((uint64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
    /* Convert 100-ns FILETIME ticks to µs, shifting epoch from 1601 to 1970 */
    return (t - 116444736000000000ULL) / 10;
}

static clock_state_t clock_init(void)
{
    clock_state_t cs;
    LARGE_INTEGER freq;
    QueryPerformanceFrequency(&freq);
    cs.qpc_freq_us   = (double)freq.QuadPart / 1000000.0;
    cs.wall_start_us = get_wall_time_us();
    QueryPerformanceCounter(&cs.qpc_start);
    return cs;
}

static uint64_t now_us(const clock_state_t *cs)
{
    LARGE_INTEGER qpc_now;
    QueryPerformanceCounter(&qpc_now);
    double elapsed = (double)(qpc_now.QuadPart - cs->qpc_start.QuadPart)
                     / cs->qpc_freq_us;
    return cs->wall_start_us + (uint64_t)elapsed;
}

/* ── Argument parsing ───────────────────────────────────────────────────── */

static unsigned int parse_uint(const char *s)
{
    char *end;
    errno = 0;
    unsigned long n = strtoul(s, &end, 10);
    if (errno != 0 || end == s || *end != '\0' || n == 0) {
        fprintf(stderr, "Error: invalid interval '%s' — expected positive integer\n", s);
        exit(1);
    }
    return (unsigned int)n;
}

/* ── Channel name normalization ─────────────────────────────────────────── */

/*
 * Converts a wide channel name to a lowercase ASCII identifier:
 *   A-Z         → a-z
 *   a-z, 0-9, _ → unchanged
 *   space, -    → _
 *   other chars → skipped
 *
 * Returns 1 if at least one character was written, 0 for empty results.
 */
static int normalize_name(const WCHAR *wname, char *out, size_t out_size)
{
    size_t i = 0;
    for (const WCHAR *p = wname; *p && i < out_size - 1; p++) {
        char c;
        if      (*p >= L'A' && *p <= L'Z') c = (char)(*p - L'A' + 'a');
        else if (*p >= L'a' && *p <= L'z') c = (char)*p;
        else if (*p >= L'0' && *p <= L'9') c = (char)*p;
        else if (*p == L'_')               c = '_';
        else if (*p == L' ' || *p == L'-') c = '_';
        else continue;
        out[i++] = c;
    }
    out[i] = '\0';
    return (i > 0) ? 1 : 0;
}

/* ── EMI device enumeration ─────────────────────────────────────────────── */

/*
 * Opens all available EMI devices, reads their metadata, and fills devs[].
 * Channels with empty names are skipped. Returns the number of usable devices.
 */
static int open_emi_devices(emi_device_t *devs, int max_devs)
{
    int count = 0;
    HDEVINFO di = SetupDiGetClassDevs(
        &GUID_DEVICE_ENERGY_METER, NULL, NULL,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);

    if (di == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "Error: SetupDiGetClassDevs failed (%lu)\n", GetLastError());
        return 0;
    }

    SP_DEVICE_INTERFACE_DATA iface = { .cbSize = sizeof(iface) };

    for (DWORD idx = 0;
         count < max_devs &&
         SetupDiEnumDeviceInterfaces(di, NULL, &GUID_DEVICE_ENERGY_METER, idx, &iface);
         ++idx)
    {
        /* Determine required buffer size, then fetch the device path */
        DWORD needed = 0;
        SetupDiGetDeviceInterfaceDetail(di, &iface, NULL, 0, &needed, NULL);
        SP_DEVICE_INTERFACE_DETAIL_DATA *detail = malloc(needed);
        if (!detail) continue;
        detail->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA);

        if (!SetupDiGetDeviceInterfaceDetail(di, &iface, detail, needed, NULL, NULL)) {
            free(detail);
            continue;
        }

        HANDLE h = CreateFile(detail->DevicePath, GENERIC_READ,
                              FILE_SHARE_READ | FILE_SHARE_WRITE,
                              NULL, OPEN_EXISTING, 0, NULL);
        free(detail);

        if (h == INVALID_HANDLE_VALUE) {
            fprintf(stderr, "Warning: cannot open EMI device %lu (%lu) — skipping\n",
                    idx, GetLastError());
            continue;
        }

        emi_device_t *dev = &devs[count];
        memset(dev, 0, sizeof(*dev));
        dev->handle = h;

        DWORD ret = 0;

        /* Query version */
        EMI_VERSION ver = {0};
        if (!DeviceIoControl(h, IOCTL_EMI_GET_VERSION,
                             NULL, 0, &ver, sizeof(ver), &ret, NULL)) {
            fprintf(stderr, "Warning: IOCTL_EMI_GET_VERSION failed for device %lu (%lu) — skipping\n",
                    idx, GetLastError());
            CloseHandle(h);
            continue;
        }
        dev->version = ver.EmiVersion;

        if (dev->version != EMI_VERSION_V1 && dev->version != EMI_VERSION_V2) {
            fprintf(stderr, "Warning: unknown EMI version %u on device %lu — skipping\n",
                    dev->version, idx);
            CloseHandle(h);
            continue;
        }

        /* Fetch metadata */
        EMI_METADATA_SIZE msize = {0};
        if (!DeviceIoControl(h, IOCTL_EMI_GET_METADATA_SIZE,
                             NULL, 0, &msize, sizeof(msize), &ret, NULL)) {
            fprintf(stderr, "Warning: IOCTL_EMI_GET_METADATA_SIZE failed for device %lu (%lu) — skipping\n",
                    idx, GetLastError());
            CloseHandle(h);
            continue;
        }

        BYTE *meta = malloc(msize.MetadataSize);
        if (!meta) { CloseHandle(h); continue; }

        if (!DeviceIoControl(h, IOCTL_EMI_GET_METADATA,
                             NULL, 0, meta, msize.MetadataSize, &ret, NULL)) {
            fprintf(stderr, "Warning: IOCTL_EMI_GET_METADATA failed for device %lu (%lu) — skipping\n",
                    idx, GetLastError());
            free(meta);
            CloseHandle(h);
            continue;
        }

        /* Extract channel names, skipping unnamed channels */
        if (dev->version == EMI_VERSION_V1) {
            const EMI_METADATA_V1 *m = (const EMI_METADATA_V1 *)meta;
            if (normalize_name(m->MeteredHardwareName,
                               dev->channels[0].name, MAX_NAME_LEN)) {
                dev->channels[0].buf_index = 0;
                dev->channel_count         = 1;
            }
            dev->measure_buf_size = sizeof(EMI_CHANNEL_MEASUREMENT_DATA);

        } else { /* V2 */
            const EMI_METADATA_V2 *m  = (const EMI_METADATA_V2 *)meta;
            const EMI_CHANNEL_V2  *ch = m->Channels;
            USHORT valid = 0;

            for (USHORT c = 0; c < m->ChannelCount; c++) {
                if (valid < MAX_CHANNELS &&
                    normalize_name(ch->ChannelName,
                                   dev->channels[valid].name, MAX_NAME_LEN)) {
                    dev->channels[valid].buf_index = c;
                    valid++;
                }
                /*
                 * Advance to the next EMI_CHANNEL_V2 entry.
                 * ChannelNameSize includes the null terminator, in bytes.
                 * The SDK requires 8-byte alignment between entries.
                 */
                size_t stride = offsetof(EMI_CHANNEL_V2, ChannelName) + ch->ChannelNameSize;
                stride = (stride + 7) & ~(size_t)7;
                ch = (const EMI_CHANNEL_V2 *)((const BYTE *)ch + stride);
            }
            dev->channel_count = valid;
            /*
             * Measurement buffer must cover ALL original channels (including
             * unnamed ones), as the driver indexes by original channel position.
             */
            dev->measure_buf_size = (ULONG)(m->ChannelCount
                                            * sizeof(EMI_CHANNEL_MEASUREMENT_DATA));
        }

        free(meta);

        if (dev->channel_count == 0) {
            fprintf(stderr, "Warning: EMI device %lu has no named channels — skipping\n", idx);
            CloseHandle(h);
            continue;
        }

        count++;
    }

    SetupDiDestroyDeviceInfoList(di);
    return count;
}

/*
 * When multiple EMI devices are present, prefix every channel name with
 * dev{N}_ to guarantee uniqueness in GMT's metric database.
 * Single-device setups are unaffected (names stay clean).
 */
static void apply_device_prefix_if_needed(emi_device_t *devs, int count)
{
    if (count <= 1) return;

    fprintf(stderr, "Info: %d EMI devices found — channel names prefixed with dev{N}_\n",
            count);

    for (int i = 0; i < count; i++) {
        for (USHORT c = 0; c < devs[i].channel_count; c++) {
            char prefixed[MAX_NAME_LEN];
            snprintf(prefixed, sizeof(prefixed), "dev%d_%s", i, devs[i].channels[c].name);
            strncpy_s(devs[i].channels[c].name, MAX_NAME_LEN, prefixed, _TRUNCATE);
            fprintf(stderr, "  dev%d channel %u → %s\n", i, c, devs[i].channels[c].name);
        }
    }
}

/* ── Sampling ───────────────────────────────────────────────────────────── */

/*
 * Reads the current energy from all devices and channels, computes the delta
 * since the previous call, converts pWh → µJ, and prints to stdout.
 * The first call only establishes the baseline; no output is produced then.
 */
static void sample_devices(emi_device_t *devs, int count, const clock_state_t *cs)
{
    for (int i = 0; i < count; i++) {
        emi_device_t *dev = &devs[i];

        BYTE *buf = malloc(dev->measure_buf_size);
        if (!buf) continue;

        DWORD ret = 0;
        if (!DeviceIoControl(dev->handle, IOCTL_EMI_GET_MEASUREMENT,
                             NULL, 0, buf, dev->measure_buf_size, &ret, NULL)) {
            fprintf(stderr, "Warning: IOCTL_EMI_GET_MEASUREMENT failed for device %d (%lu)\n",
                    i, GetLastError());
            free(buf);
            continue;
        }

        const EMI_CHANNEL_MEASUREMENT_DATA *data =
            (const EMI_CHANNEL_MEASUREMENT_DATA *)buf;

        for (USHORT c = 0; c < dev->channel_count; c++) {
            emi_channel_t *ch     = &dev->channels[c];
            uint64_t       energy = data[ch->buf_index].AbsoluteEnergy;

            if (ch->has_prev && energy >= ch->prev_energy) {
                uint64_t  delta_pwh = energy - ch->prev_energy;
                long long delta_uj  = (long long)((double)delta_pwh * PWH_TO_UJ);

                /*
                 * Skip zero values: either the channel is inactive (driver
                 * exposes it but does not update the counter, e.g. DRAM on
                 * some systems) or the delta is below µJ resolution (~278 pWh).
                 * Outputting zeros would trigger GMT's resolution-underflow check.
                 */
                if (delta_uj > 0) {
                    /* Each channel gets its own timestamp so all lines are unique */
                    printf("%llu %lld %s\n",
                           (unsigned long long)now_us(cs),
                           delta_uj,
                           ch->name);
                }
            }

            ch->prev_energy = energy;
            ch->has_prev    = 1;
        }

        free(buf);
    }
}

/* ── main ───────────────────────────────────────────────────────────────── */

int main(int argc, char *argv[])
{
    unsigned int interval_ms = 99;
    int          check_mode  = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i") && i + 1 < argc)
            interval_ms = parse_uint(argv[++i]);
        else if (!strcmp(argv[i], "-c"))
            check_mode = 1;
    }

    emi_device_t devs[MAX_DEVICES];
    int device_count = open_emi_devices(devs, MAX_DEVICES);

    if (device_count == 0) {
        fprintf(stderr,
            "No usable EMI energy-meter devices found.\n"
            "  Windows 11 with an Intel/AMD CPU should have the inbox RAPL driver.\n"
            "  Windows 10 requires dedicated hardware energy meters.\n");
        return 1;
    }

    if (check_mode) {
        for (int i = 0; i < device_count; i++)
            CloseHandle(devs[i].handle);
        return 0;
    }

    apply_device_prefix_if_needed(devs, device_count);

    setvbuf(stdout, NULL, _IONBF, 0);
    clock_state_t cs = clock_init();

    /*
     * Request 1ms timer resolution so Sleep(99) actually sleeps ~99ms.
     * Without this, Windows' default ~15.6ms granularity causes intervals
     * of 104–160ms, which would fail GMT's ±20% sampling-rate check.
     */
    timeBeginPeriod(1);

    while (1) {
        sample_devices(devs, device_count, &cs);
        Sleep(interval_ms);
    }

    /* Not reached in normal operation; shown for completeness */
    timeEndPeriod(1);
    for (int i = 0; i < device_count; i++)
        CloseHandle(devs[i].handle);
    return 0;
}
