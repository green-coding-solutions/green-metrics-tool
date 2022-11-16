/*
    Modified by:
        Copyright (C) 2022  Didi Hoffmann <didi@green-coding.org>

    source.c - Reads values from libsensors and displays them continuously according to the
               GCB metrics standard

    Copied from: https://github.com/lm-sensors/lm-sensors/tree/master/prog/sensors
    main.c - Part of sensors, a user-space program for hardware monitoring

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
    MA 02110-1301 USA.
*/

#include <stdio.h>
#include <stdlib.h>
#include <getopt.h>
#include <string.h>
#include <errno.h>
#include <locale.h>
#include <langinfo.h>
#include <unistd.h>
#include <sys/time.h>
#include <signal.h>


#ifndef __UCLIBC__
#include <iconv.h>
#define HAVE_ICONV
#endif

#include "sensors/sensors.h"
#include "sensors/error.h"
#include "source.h"
#include "chips.h"


int fahrenheit;
char degstr[5]; /* store the correct string to print degrees */

static unsigned int msleep_time=1000;
static volatile sig_atomic_t keep_running = 1;

/* As we need to do some cleanup when we get SIGINT we need a signal handler*/
static void sig_handler(int _)
{
    (void)_;
    keep_running = 0;
}


static void print_long_help(char *program)
{
	printf("Usage: %s FEATURE?......\n", program);
	puts("  -c, --config-file      Specify a config file\n"
	     "  -h, --help             Display this help text\n"
	     "  -f, --fahrenheit       Show temperatures in degrees fahrenheit\n"
         "  -i, --sleep            Milliseconds to sleep between measurements\n"
         ""
	     "If no feature is given all values are outputted for debugging!");
}


/* Return 0 on success, and an exit error code otherwise */
static int read_config_file(const char *config_file_name)
{
	FILE *config_file;
	int err;

	if (config_file_name) {
		if (!strcmp(config_file_name, "-"))
			config_file = stdin;
		else
			config_file = fopen(config_file_name, "r");

		if (!config_file) {
			fprintf(stderr, "Could not open config file\n");
			perror(config_file_name);
			return 1;
		}
	} else {
		/* Use libsensors default */
		config_file = NULL;
	}

	err = sensors_init(config_file);
	if (err) {
		fprintf(stderr, "sensors_init: %s\n", sensors_strerror(err));
		if (config_file)
			fclose(config_file);
		return 1;
	}

	if (config_file && fclose(config_file) == EOF)
		perror(config_file_name);

	return 0;
}

static void set_degstr(void)
{
	const char *deg_default_text[2] = { " C", " F" };

#ifdef HAVE_ICONV
	/* Size hardcoded for better performance.
	   Don't forget to count the trailing \0! */
	size_t deg_latin1_size = 3;
	char deg_latin1_text[2][3] = { "\260C", "\260F" };
	char *deg_latin1_ptr = deg_latin1_text[fahrenheit];
	size_t nconv;
	size_t degstr_size = sizeof(degstr);
	char *degstr_ptr = degstr;

	iconv_t cd = iconv_open(nl_langinfo(CODESET), "ISO-8859-1");
	if (cd != (iconv_t) -1) {
		nconv = iconv(cd, &deg_latin1_ptr, &deg_latin1_size,
			      &degstr_ptr, &degstr_size);
		iconv_close(cd);

		if (nconv != (size_t) -1)
			return;
	}
#endif /* HAVE_ICONV */

	/* There was an error during the conversion, use the default text */
	strcpy(degstr, deg_default_text[fahrenheit]);
}

static const char *sprintf_chip_name(const sensors_chip_name *name)
{
#define BUF_SIZE 200
	static char buf[BUF_SIZE];

	if (sensors_snprintf_chip_name(buf, BUF_SIZE, name) < 0)
		return NULL;
	return buf;
}

static void do_a_print(const sensors_chip_name *name)
{
	printf("%s\n", sprintf_chip_name(name));
    const char *adap = sensors_get_adapter_name(&name->bus);
    if (adap){
        printf("Adapter: %s\n", adap);
    }else{
        fprintf(stderr, "Can't get adapter name\n");
    }
	print_chip(name);
	printf("\n");
}

/* returns number of chips found */
static int do_the_real_work(const sensors_chip_name *match, int *err)
{
	const sensors_chip_name *chip;
	int chip_nr;
	int cnt = 0;

	chip_nr = 0;
	while ((chip = sensors_get_detected_chips(match, &chip_nr))) {
        do_a_print(chip);
        cnt++;
    }
	return cnt;
}

static void output_value(int value) {

    struct timeval now;

    gettimeofday(&now, NULL);
    printf("%ld%06ld %i\n", now.tv_sec, now.tv_usec, value);

    usleep(msleep_time*1000);
}


int main(int argc, char *argv[])
{
	int c, err;
	const char *config_file_name = NULL;

	struct option long_opts[] =  {
		{ "help", no_argument, NULL, 'h' },
		{ "fahrenheit", no_argument, NULL, 'f' },
		{ "config-file", required_argument, NULL, 'c' },
        { "sleep", required_argument, NULL, 'i' },
		{ 0, 0, 0, 0 }
	};

    /* Catch both signals and exit gracefully */
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

	setlocale(LC_CTYPE, "");

	while (1) {
		c = getopt_long(argc, argv, "hfc:i:", long_opts, NULL);
		if (c == EOF)
			break;
		switch(c) {
            case ':':
            case 'h':
                print_long_help(argv[0]);
                exit(0);
            case 'c':
                config_file_name = optarg;
                break;
            case 'f':
                fahrenheit = 1;
                break;
            case 'i':
                msleep_time = atoi(optarg);
                break;
            default:
                exit(1);
		}
	}

	err = read_config_file(config_file_name);
	if (err)
		exit(err);

    int cnt = 0;

    /*
    When talking about a feature we mean an actual reading from a chip.
    The sensors library retuns a list of chips which have 0..n features.
    */

    if (optind == argc) { /* No feature on command line. This is for debugging */
    	/* Build the degrees string to make it more readable*/
    	set_degstr();

		if (do_the_real_work(NULL, &err)) {
            cnt = 1; // Set to something not 0 so we know it worked ok
		}
	} else if(argv[optind] ) { /* We currently only process one feature */

        const sensors_chip_name *name;
        const sensors_feature *feature;

	    int chip_nr;
        int break_loops = 0;

	    chip_nr = 0;

        /* Need to find the required value in all the chips */
        while ((name = sensors_get_detected_chips(NULL, &chip_nr))) {
            int j = 0;
            while ((feature = sensors_get_features(name, &j))) {
                char *label;

                if (!(label = sensors_get_label(name, feature))) {
                    fprintf(stderr, "ERROR: Can't get label of feature %s ignoring!\n", feature->name);
                }
                if(!strcmp(label, argv[optind])){
                    /* Currently we exit on the first occurrence of a feature! */
                    break_loops = 1;
                }
                free(label);

                if (break_loops){
                    break;
                }
            }
            cnt++;
            if (break_loops){
                break;
            }
        }

        if(cnt == 0){
            fprintf(stderr,
				"No sensors found!\n"
				"Make sure you loaded all the kernel drivers you need.\n"
				"Try sensors-detect to find out which these are.\n");
                err = 1;
        } else if(break_loops){
            /* This is the main program loop */
            while(keep_running) {
                switch (feature->type) {
                    case SENSORS_FEATURE_TEMP:
                        output_value(chip_temp_raw(name, feature));
                        break;
                    case SENSORS_FEATURE_FAN:
			            output_value(chip_fan_raw(name, feature));
			            break;
                    default:
                        fprintf(stderr, "We currently only support SENSORS_FEATURE_TEMP & SENSORS_FEATURE_FAN!\n");
                        err = 1;
                        break;
                }
                usleep(msleep_time*1000);
            }


        }else{
            fprintf(stderr, "No sensor feature found!\n");
            err = 1;
        }

    } else {
		fprintf(stderr, "We currently only support one sensor feature!\n");
		err = 1;
    }

    fflush(stdout);
	sensors_cleanup();
	exit(err);
}