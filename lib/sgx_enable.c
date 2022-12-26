/* Copied from https://raw.githubusercontent.com/intel/sgx-software-enable/master/sgx_enable.c
 */
/*
 * Copyright (C) 2011-2019 Intel Corporation. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 *   * Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *   * Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer in
 *     the documentation and/or other materials provided with the
 *     distribution.
 *   * Neither the name of Intel Corporation nor the names of its
 *     contributors may be used to endorse or promote products derived
 *     from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 */

#include <sys/stat.h>
#include <sys/types.h>
#include <inttypes.h>
#include <stdio.h>
#include <memory.h>
#include <unistd.h>
#include <errno.h>
#include <getopt.h>
#include <stdlib.h>

typedef int sgx_status_t; // Needed by sgx_capable.h

#include "sgx_capable.h"

#define SGX_SUCCESS					0x0000
#define SGX_ERROR_UNEXPECTED		0x0001
#define SGX_ERROR_INVALID_PARAMETER	0x0002
#define SGX_ERROR_NO_PRIVILEGE		0x5002

/* __cpuid(unsinged int info[4], unsigned int leaf, unsigned int subleaf); */
#define __cpuid(x,y,z) asm volatile("cpuid":"=a"(x[0]),"=b"(x[1]),"=c"(x[2]),"=d"(x[3]):"a"(y),"c"(z))

#define Genu 0x756e6547
#define ineI 0x49656e69
#define ntel 0x6c65746e

#define EFIFS_PATH		"/sys/firmware/efi/"
#define EFIVARS_PATH 	EFIFS_PATH"efivars/"
#define EFIVAR_EPCBIOS	EFIVARS_PATH"EPCBIOS-c60aa7f6-e8d6-4956-8ba1-fe26298f5e87"
#define EFIVAR_EPCSW	EFIVARS_PATH"EPCSW-d69a279b-58eb-45d1-a148-771bb9eb5251"

int _is_sgx_available();
int _is_cpu_supported();
void usage ();

int main (int argc, char *argv[])
{
	sgx_status_t status;
	sgx_device_status_t result;
	int flag_status= 0;
	static struct option long_opt[]=
	{
		{"help",		no_argument,	0, 'h'},
		{"status",		no_argument,	0, 's'},
		{ 0, 0, 0, 0 }
	};

	while (1) {
		int opt_index= 0;
		int c;

		c= getopt_long(argc, argv, "hs", long_opt, &opt_index);
		if ( c == -1 ) break;

		switch(c) {
			case 's':
				flag_status= 1;
				break;
			case 'h':
			case '?':
			default:
				usage();
		}
	}

	argc-= optind;
	if ( argc ) usage();

	/* Are we SGX capable? */

	status= sgx_cap_get_status(&result);
	if ( status != SGX_SUCCESS ) {
		switch(status) {
		case SGX_ERROR_NO_PRIVILEGE:
			fprintf(stderr, "could not examine the EFI filesystem\n");
			break;
		case SGX_ERROR_INVALID_PARAMETER:
		case SGX_ERROR_UNEXPECTED:
			fprintf(stderr, "could not get SGX status: ");
		default:
			fprintf(stderr, "sgx_cap_get_status returned 0x%04x\n", status);
			break;
		}
		return 1;
	}

	if ( result == SGX_ENABLED ) {
		printf("Intel SGX is already enabled on this system\n");
		return 0;
	} else if ( result == SGX_DISABLED_UNSUPPORTED_CPU ) {
		printf("This CPU does not support Intel SGX\n");
		return 1;
	} else if ( result == SGX_DISABLED_LEGACY_OS ) {
		printf("This processor supports Intel SGX but was booted in legacy mode.\n");
		printf("A UEFI boot is required to determine whether or not your BIOS\n");
		printf("supports Intel SGX, and to attempt the software enable.\n");
		printf("Alternatively, you can check your BIOS to see if it has an\n");
		printf("explicit option to enable SGX.\n");
		return 1;
	} else if ( result == SGX_DISABLED ) {
		printf("Intel SGX is explicitly disabled on your system. It may be\n");
		printf("disabled in the BIOS, or the BIOS may not support Intel SGX.\n");
		return 1;
	} else if ( result == SGX_DISABLED_MANUAL_ENABLE ) {
		printf("Intel SGX is explicitly disabled, and your BIOS does not\n");
		printf("support the \"software enable\" option. Check your BIOS for an\n");
		printf("explicit option to enable Intel SGX.\n");
		return 1;
	} else if ( result == SGX_DISABLED_REBOOT_REQUIRED ) {
		printf("The software enable has been performed on this system and\n");
		printf("Intel SGX will be enabled after the system is rebooted.\n");
		return 0;
	} else if ( result != SGX_DISABLED_SCI_AVAILABLE ) {
		printf("I couldn't make sense of your system.\n");
		fprintf(stderr, "sgx_cap_get_status returned 0x%04x\n", result);
		return 1;
	}

	if ( flag_status ) {
		printf("Intel SGX is disabled and can be enabled using this utility.\n");
		return 0;
	}

	/* Now try to enable Intel SGX */

	status= sgx_cap_enable_device(&result);
	if ( status != SGX_SUCCESS ) {
		switch(status) {
		case SGX_ERROR_NO_PRIVILEGE:
			printf("You may need to rerun this utility as root\n");
			break;
		case SGX_ERROR_INVALID_PARAMETER:
		case SGX_ERROR_UNEXPECTED:
			printf("I could not attempt the software enable: ");
		default:
			printf("sgx_cap_enable_device returned 0x%04x\n", status);
		}
		return 1;
	}

	printf("Software enable has been set. Please reboot your system to finish\n");
	printf("enabling Intel SGX.\n");

	return 0;
}

void usage ()
{
	fprintf(stderr, "usage: sgx-enable [ options ]\n");
	fprintf(stderr, "\nOptions:\n");
	fprintf(stderr, "  -s, --status      Report the enabling status only.\n");
	fprintf(stderr, "  -h, --help        Show this help\n");
	exit(1);
}


sgx_status_t sgx_is_capable (int *sgx_capable)
{
	struct stat sb;
	memset(&sb, 0, sizeof(struct stat));

	if ( sgx_capable == NULL ) return SGX_ERROR_INVALID_PARAMETER;

	if ( ! _is_cpu_supported() ) {
		*sgx_capable= 0;
		return SGX_SUCCESS;
	}

	if ( _is_sgx_available() ) {
		*sgx_capable= 1;
		return SGX_SUCCESS;
	}

	/* Check to see if the Software Control Interface is available */

	if ( stat(EFIVAR_EPCBIOS, &sb) == -1 ) {
		if ( errno == EACCES ) {
			perror(EFIVAR_EPCBIOS);
			return SGX_ERROR_NO_PRIVILEGE;
		}
		*sgx_capable = 0;
		return SGX_SUCCESS;
	}

	*sgx_capable= 1;
	return SGX_SUCCESS;
}

sgx_status_t sgx_cap_get_status (sgx_device_status_t *sgx_device_status)
{
	struct stat sb;
	int has_efifs= 0;
	memset(&sb, 0, sizeof(struct stat));

	if ( sgx_device_status == NULL ) return SGX_ERROR_INVALID_PARAMETER;

	if ( ! _is_cpu_supported() ) {
		*sgx_device_status= SGX_DISABLED_UNSUPPORTED_CPU;
		return SGX_SUCCESS;
	}

	if ( _is_sgx_available() ) {
		*sgx_device_status= SGX_ENABLED;
		return SGX_SUCCESS;
	}

	/*
	 * Intel SGX is supported, but not enabled. Figure out what
	 * it will take to enable it.
	 */

	/* Were we booted in UEFI mode? */

	if ( stat(EFIFS_PATH, &sb) == 0 ) {
		has_efifs= 1;

		if ( stat(EFIVARS_PATH, &sb) == -1 )
		{
			/* We have /sys/firmware/efi but not efivars */

			switch (errno) {
			case EACCES:
				perror(EFIVARS_PATH);
				return SGX_ERROR_NO_PRIVILEGE;
			case ENOENT:
			case ENOTDIR:
				break;
			default:
				perror(EFIVARS_PATH);
				return SGX_ERROR_UNEXPECTED;
			}
		}
	} else {
		switch (errno) {
		case EACCES:
			perror(EFIFS_PATH);
			return SGX_ERROR_NO_PRIVILEGE;
		case ENOENT:
		case ENOTDIR:
			break;
		default:
			perror(EFIFS_PATH);
			return SGX_ERROR_UNEXPECTED;
		}
	}

	if ( ! has_efifs ) {
		/*
		 * We don't have /sys/firmware/efi mounted. It could have been
		 * unmounted by the user, or we might not have UEFI support in
		 * the OS. If /boot/efi exists, then we are probably capable of
		 * UEFI and should report SGX_DISABLED. Otherwise report
		 * SGX_DISABLED_LEGACY_OS.
		 */

		if ( stat("/boot/efi", &sb) == 0 ) *sgx_device_status= SGX_DISABLED;
		else {
			switch(errno) {
			case ENOENT:
			case ENOTDIR:
				*sgx_device_status= SGX_DISABLED_LEGACY_OS;
				break;
			default:
				/*
				 * We don't have enough information to figure this out
				 * so report SGX_DISABLED.
				 */
				*sgx_device_status= SGX_DISABLED;
			}

		}

		return SGX_SUCCESS;
	}

	/*
	 * We have access to efivars. Now examine the EFI variable for the
	 * Software Control Interface.
	 */

	if ( stat(EFIVAR_EPCBIOS, &sb) == -1 ) {
		if ( errno == EACCES ) {
			perror(EFIVAR_EPCBIOS);
			return SGX_ERROR_NO_PRIVILEGE;
		}

		/* No SCI is present so we can't do a s/w enabled */

		*sgx_device_status= SGX_DISABLED_MANUAL_ENABLE;
		return SGX_SUCCESS;
	}

	/*
	 * Check to see if the software enable has already been
	 * performed. If so, then we will be enabled on the next
	 * reboot.
	 */

	if ( stat(EFIVAR_EPCSW, &sb) == -1 ) {
		if ( errno == EACCES ) {
			perror(EFIVAR_EPCSW);
			return SGX_ERROR_NO_PRIVILEGE;
		}

		/* The software enable hasn't been attempted yet. */

		*sgx_device_status= SGX_DISABLED_SCI_AVAILABLE;
		return SGX_SUCCESS;
	}

	/* Software enable has occurred. Need a reboot. */

	*sgx_device_status= SGX_DISABLED_REBOOT_REQUIRED;

	return SGX_SUCCESS;
}

/* Determine if the CPU supports Intel SGX */

int _is_cpu_supported()
{
	unsigned int info[4] = {0, 0, 0, 0};
	unsigned int *ebx, *ecx, *edx;

	ebx= &info[1];
	ecx= &info[2];
	edx= &info[3];

	/* Is this an Intel CPU? */

	__cpuid (info, 0x00, 0);
	if ( *ebx != Genu || *ecx != ntel || *edx != ineI )
		return 0;

	/* Does the CPU support Intel SGX? */

	__cpuid (info, 0x07, 0);

	return ( *ebx & (0x1<<2) );
}

/* Are SGX instructions available for use? */

int _is_sgx_available ()
{
	unsigned int info[4] = {0, 0, 0, 0};
	unsigned int *eax, *ebx, *ecx, *edx;
	unsigned int subleaf= 2;
	unsigned int flag;

	eax= &info[0];
	ebx= &info[1];
	ecx= &info[2];
	edx= &info[3];

	/* Are Intel SGX instructions available for use? */

	__cpuid(info, 0x12, 0);

	flag= *eax&0x3;
	if ( flag == 0 ) return 0;

	/* Do we have non-zero, max enclave sizes? */

	if ( (*edx & 0xFFFF) == 0 ) return 0;

	/*
	 * Enumerate the subleafs for the EPC. At least one must be a valid
	 * subleaf that describes a page.
	 */

	while (1) {
		__cpuid(info, 0x12, subleaf);

		/*
		 * Is this an invalid subleaf? If we've hit an invalid subleaf
		 * before finding a valid subleaf with a non-zero page size,
		 * then we have no EPC memory allocated, and thus no Intel SGX
		 * capability.
		 */

		if ( ! (*eax & 0x1) ) return 0;

		/*
		 * Is there a non-zero size for this EPC subleaf? If so, we
		 * have memory allocated to the EPC for Intel SGX, and are
		 * enabled.
		 */

		if (
			(*eax&0xFFFFF000 || *ebx&0xFFFFF) &&
			(*ecx&0xFFFFF000 || *edx&0xFFFFF)
		) return 1;

		++subleaf;
	}

	/* We'll never get here, but we need to keep the compiler happy */

	return 0;
}

sgx_status_t sgx_cap_enable_device (sgx_device_status_t *sgx_device_status)
{
	sgx_status_t status;
	struct epcbios_stuct {
		uint32_t attrs;
		uint32_t sprmbins;
		uint32_t maxepcsz;
		/* There's more, but this is all we need */
	} epcbios;
	struct epcsw_struct {
		uint32_t attrs;
		uint32_t maxepcsz;
	} epcsw;
	FILE *fefivar;

	if ( sgx_device_status == NULL ) return SGX_ERROR_INVALID_PARAMETER;

	status= sgx_cap_get_status(sgx_device_status);
	if ( status != SGX_SUCCESS ) return status;

	/*
	 * If we get back anything other than SGX_DISABLED_SCI_AVAILABLE
	 * then return, because there is nothing to do.
	 */

	if ( *sgx_device_status != SGX_DISABLED_SCI_AVAILABLE )
		return SGX_SUCCESS;

	/* Attempt the software enable */

	/* First, read the EPCBIOS EFI variable to get the max EPC size */

	fefivar= fopen(EFIVAR_EPCBIOS, "r");
	if ( fefivar == NULL ) {
		perror(EFIVAR_EPCBIOS);
		if ( errno == EACCES ) return SGX_ERROR_NO_PRIVILEGE;

		return SGX_ERROR_UNEXPECTED;
	}

	/*
	 * The first 4 bytes are the EFI variable attributes. Data starts
	 * at offset 0x4, and the value we want is a UINT32 at offset 0x8.
	 */

	if ( fread(&epcbios, sizeof(epcbios), 1, fefivar) != 1 ) {
		fclose(fefivar);
		return SGX_ERROR_UNEXPECTED;
	}

	if ( fclose(fefivar)) {
		return SGX_ERROR_UNEXPECTED;
	}

	/*
	 * Now create the EPCSW EFI variable. The variable data is a
	 * single UINT32 specifying the requested EPC size.
	 */

	epcsw.attrs= epcbios.attrs;
	epcsw.maxepcsz= epcbios.maxepcsz;

	fefivar= fopen(EFIVAR_EPCSW, "w");
	if ( fefivar == NULL ) {
		perror(EFIVAR_EPCSW);
		if ( errno == EACCES ) return SGX_ERROR_NO_PRIVILEGE;

		return SGX_ERROR_UNEXPECTED;
	}

	/* Write out the EPCSW structure */

	if ( fwrite(&epcsw, sizeof(epcsw), 1, fefivar) != 1 ) {
		unlink(EFIVAR_EPCSW);
		fclose(fefivar);
		return SGX_ERROR_UNEXPECTED;
	}

	if ( fclose(fefivar)) {
		return SGX_ERROR_UNEXPECTED;
	}

	*sgx_device_status= SGX_DISABLED_REBOOT_REQUIRED;

	return SGX_SUCCESS;
}
