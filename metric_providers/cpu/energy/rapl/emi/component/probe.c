/*
 * probe.c - EMI device discovery diagnostic
 *
 * Enumerates all Windows Energy Meter Interface (EMI) devices,
 * prints their hardware info and channel names, then exits.
 * Used to verify EMI availability and learn the exact channel
 * names before building the full metric provider.
 *
 * Compile (x64 Native Tools Command Prompt):
 *   cl probe.c /Fe:probe /nologo /link setupapi.lib
 *
 * Run:
 *   probe.exe
 *
 * Delete this file once channel names are confirmed.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winioctl.h>   /* CTL_CODE, FILE_DEVICE_UNKNOWN, METHOD_BUFFERED etc. */
#include <initguid.h>   /* DEFINE_GUID instantiation - must come before emi.h  */
#include <setupapi.h>
#include <emi.h>
#include <stdio.h>
#include <stdlib.h>

#pragma comment(lib, "setupapi.lib")

static const EMI_CHANNEL_V2 *next_channel(const EMI_CHANNEL_V2 *ch)
{
    /* ChannelNameSize includes the null terminator, in bytes */
    size_t stride = offsetof(EMI_CHANNEL_V2, ChannelName) + ch->ChannelNameSize;
    stride = (stride + 7) & ~(size_t)7;   /* align to 8 bytes */
    return (const EMI_CHANNEL_V2 *)((const BYTE *)ch + stride);
}

int main(void)
{
    HDEVINFO di = SetupDiGetClassDevs(
        &GUID_DEVICE_ENERGY_METER, NULL, NULL,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);

    if (di == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "SetupDiGetClassDevs failed: %lu\n", GetLastError());
        return 1;
    }

    SP_DEVICE_INTERFACE_DATA iface = { .cbSize = sizeof(iface) };
    int device_count = 0;

    for (DWORD idx = 0;
         SetupDiEnumDeviceInterfaces(di, NULL, &GUID_DEVICE_ENERGY_METER, idx, &iface);
         ++idx)
    {
        /* Get device path */
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
            printf("Device %d: cannot open (error %lu) - skipping\n\n",
                   idx, GetLastError());
            continue;
        }

        device_count++;
        printf("=== Device %d ===\n", idx);

        /* Query EMI version */
        EMI_VERSION ver = {0};
        DWORD ret = 0;
        if (!DeviceIoControl(h, IOCTL_EMI_GET_VERSION,
                             NULL, 0, &ver, sizeof(ver), &ret, NULL)) {
            printf("  IOCTL_EMI_GET_VERSION failed: %lu\n\n", GetLastError());
            CloseHandle(h);
            continue;
        }
        printf("  EMI version : %u\n", ver.EmiVersion);

        /* Query metadata size and fetch metadata */
        EMI_METADATA_SIZE msize = {0};
        if (!DeviceIoControl(h, IOCTL_EMI_GET_METADATA_SIZE,
                             NULL, 0, &msize, sizeof(msize), &ret, NULL)) {
            printf("  IOCTL_EMI_GET_METADATA_SIZE failed: %lu\n\n", GetLastError());
            CloseHandle(h);
            continue;
        }

        BYTE *meta = malloc(msize.MetadataSize);
        if (!meta) { CloseHandle(h); continue; }

        if (!DeviceIoControl(h, IOCTL_EMI_GET_METADATA,
                             NULL, 0, meta, msize.MetadataSize, &ret, NULL)) {
            printf("  IOCTL_EMI_GET_METADATA failed: %lu\n\n", GetLastError());
            free(meta);
            CloseHandle(h);
            continue;
        }

        if (ver.EmiVersion == EMI_VERSION_V1) {
            const EMI_METADATA_V1 *m = (const EMI_METADATA_V1 *)meta;
            printf("  OEM         : %ls\n", m->HardwareOEM);
            printf("  Model       : %ls\n", m->HardwareModel);
            printf("  Unit        : picowatt-hours (V1 only unit)\n");
            printf("  Channel 0   : \"%ls\"\n", m->MeteredHardwareName);
        } else if (ver.EmiVersion == EMI_VERSION_V2) {
            const EMI_METADATA_V2 *m = (const EMI_METADATA_V2 *)meta;
            printf("  OEM         : %ls\n", m->HardwareOEM);
            printf("  Model       : %ls\n", m->HardwareModel);
            printf("  Channels    : %u\n", m->ChannelCount);
            const EMI_CHANNEL_V2 *ch = m->Channels;
            for (USHORT c = 0; c < m->ChannelCount; c++) {
                printf("  Channel %u   : \"%ls\"\n", c, ch->ChannelName);
                ch = next_channel(ch);
            }
        } else {
            printf("  Unknown EMI version %u\n", ver.EmiVersion);
        }

        printf("\n");
        free(meta);
        CloseHandle(h);
    }

    SetupDiDestroyDeviceInfoList(di);

    if (device_count == 0) {
        printf("No EMI devices found.\n");
        printf("  Windows 11 should have the inbox RAPL driver active.\n");
        printf("  Check: Device Manager -> Energy Meter\n");
        return 1;
    }

    printf("Total devices found: %d\n", device_count);
    return 0;
}
