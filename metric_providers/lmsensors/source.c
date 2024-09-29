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

#include <errno.h>
#include <getopt.h>
#include <glib.h>
#include <langinfo.h>
#include <locale.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>

#ifndef __UCLIBC__
#include <iconv.h>
#define HAVE_ICONV
#endif

#include "chips.h"
#include "sensors/error.h"
#include "sensors/sensors.h"
#include "source.h"
#include "parse_int.h"

int fahrenheit;
char degstr[5]; /* store the correct string to print degrees */

static unsigned int msleep_time = 1000;
static volatile sig_atomic_t keep_running = 1;

/* As we need to do some cleanup when we get SIGINT we need a signal handler*/
static void sig_handler(int _) {
    (void)_;
    keep_running = 0;
}

static void print_long_help(char *program) {
    printf("Usage: %s -c coretemp -f Core 'Package id' \n", program);
    puts(
        "  -c, --chips            A list of chip labels to look for\n"
        "  -f, --features         A list of features to select. \n"
        "  -s, --config-file      Specify a config file\n"
        "  -h, --help             Display this help text\n"
        "  -t, --fahrenheit       Show temperatures in degrees fahrenheit\n"
        "  -i, --sleep            Milliseconds to sleep between measurements\n"
        "\n"
        "Parameters for -c and and -f basically search strings. Like a regex '*' appended, "
        "the parameters are seen to be coretemp* and such will match anything that starts"
        "with coretemp.\n"
        "If no chips or features is given all values are outputted for debugging!");
}

/* Return 0 on success, and an exit error code otherwise */
static int read_config_file(const char *config_file_name) {
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
        if (config_file) fclose(config_file);
        return 1;
    }

    if (config_file && fclose(config_file) == EOF) perror(config_file_name);

    return 0;
}

static void set_degstr(void) {
    const char *deg_default_text[2] = {" C", " F"};

#ifdef HAVE_ICONV
    /* Size hardcoded for better performance.
       Don't forget to count the trailing \0! */
    size_t deg_latin1_size = 3;
    char deg_latin1_text[2][3] = {"\260C", "\260F"};
    char *deg_latin1_ptr = deg_latin1_text[fahrenheit];
    size_t nconv;
    size_t degstr_size = sizeof(degstr);
    char *degstr_ptr = degstr;

    iconv_t cd = iconv_open(nl_langinfo(CODESET), "ISO-8859-1");
    if (cd != (iconv_t)-1) {
        nconv = iconv(cd, &deg_latin1_ptr, &deg_latin1_size, &degstr_ptr, &degstr_size);
        iconv_close(cd);

        if (nconv != (size_t)-1) return;
    }
#endif /* HAVE_ICONV */

    /* There was an error during the conversion, use the default text */
    snprintf(degstr, sizeof(degstr), "%s", deg_default_text[fahrenheit]);
}

static const char *sprintf_chip_name(const sensors_chip_name *name) {
#define BUF_SIZE 200
    static char buf[BUF_SIZE];

    if (sensors_snprintf_chip_name(buf, BUF_SIZE, name) < 0) return NULL;
    return buf;
}

static void do_a_print(const sensors_chip_name *name) {
    printf("%s\n", sprintf_chip_name(name));
    const char *adap = sensors_get_adapter_name(&name->bus);
    if (adap) {
        printf("Adapter: %s\n", adap);
    } else {
        fprintf(stderr, "Can't get adapter name\n");
    }
    print_chip(name);
    printf("\n");
}

/* returns number of chips found */
static int do_the_real_work(const sensors_chip_name *match, int *err) {
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

static void output_value(int value, char *container_id) {
    struct timeval now;

    gettimeofday(&now, NULL);
    printf("%ld%06ld %i %s\n", now.tv_sec, now.tv_usec, value, container_id);
}

int main(int argc, char *argv[]) {
    int c, err;
    int measurement_amount = -1;
    const char *config_file_name = NULL;

    // These are the lists that we pass in through the command line
    GList *chips_name_filter = NULL;
    GList *features_to_filter = NULL;

    // General iterators we use throughout the code.
    GList *chip_iterator = NULL;
    GList *feature_iterator = NULL;
    GList *output_iterator = NULL;

    struct option long_opts[] = {{"chips", required_argument, NULL, 'c'},
                                 {"features", required_argument, NULL, 'f'},
                                 {"help", no_argument, NULL, 'h'},
                                 {"fahrenheit", no_argument, NULL, 't'},
                                 {"config-file", required_argument, NULL, 's'},
                                 {"sleep", required_argument, NULL, 'i'},
                                 {0, 0, 0, 0}};

    /* Catch both signals and exit gracefully */
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);

    setlocale(LC_CTYPE, "");

    while (1) {
        c = getopt_long(argc, argv, "c:f:hts:i:n:", long_opts, NULL);
        if (c == EOF) break;
        switch (c) {
            case ':':
            case 'c':
                optind--;
                while (optind < argc) {
                    if (strncmp(argv[optind], "-", 1) == 0) {
                        break;
                    }
                    chips_name_filter = g_list_append(chips_name_filter, argv[optind++]);
                }
                break;
            case 'f':
                optind--;
                while (optind < argc) {
                    if (strncmp(argv[optind], "-", 1) == 0) {
                        break;
                    }
                    features_to_filter = g_list_append(features_to_filter, argv[optind++]);
                }
                break;
            case 'h':
                print_long_help(argv[0]);
                exit(0);
            case 's':
                config_file_name = optarg;
                break;
            case 't':
                fahrenheit = 1;
                break;
            case 'i':
                msleep_time = parse_int(optarg);
                break;
            case 'n':
                measurement_amount = parse_int(optarg);
                break;
            default:
                exit(1);
        }
    }

    err = read_config_file(config_file_name);
    if (err) exit(err);

    /*
    When talking about a feature we mean an actual reading from a chip.
    The sensors library retuns a list of chips which have 0..n features.
    */

    if (g_list_length(chips_name_filter) == 0 || g_list_length(features_to_filter) == 0) {
        /* No feature on command line. This is for debugging */

        /* Build the degrees string to make it more readable*/
        set_degstr();

        do_the_real_work(NULL, &err);
    } else {
        int chip_nr = 0;

        const sensors_chip_name *chip_name;
        const sensors_feature *feature;

        /* The structure that holds the values that are then outputted */
        typedef struct {
            const sensors_chip_name *chip_name;
            const sensors_feature *feature;
        } Output_Mapping;

        /* The list of Output_Mappings that we then iterate when we output */
        GList *chip_feature_output = NULL;

        /* Find the chips and features depending on the filters supplied on the command line */
        while ((chip_name = sensors_get_detected_chips(NULL, &chip_nr))) {
            for (chip_iterator = chips_name_filter; chip_iterator; chip_iterator = chip_iterator->next) {
                if (g_ascii_strncasecmp(chip_iterator->data, sprintf_chip_name(chip_name),
                                        strlen(chip_iterator->data)) == 0) {
                    int j = 0;

                    /* Now we start searching for the features */
                    while ((feature = sensors_get_features(chip_name, &j))) {
                        char *label;

                        if (!(label = sensors_get_label(chip_name, feature))) {
                            //  Only for manual debug purposes
                            //  fprintf(stderr, "ERROR: Can't get label of feature %s ignoring!\n", feature->name);
                            free(label);
                            continue;
                        }

                        for (feature_iterator = features_to_filter; feature_iterator;
                             feature_iterator = feature_iterator->next) {
                            if (g_ascii_strncasecmp(feature_iterator->data, label, strlen(feature_iterator->data)) ==
                                0) {
                                Output_Mapping *to_add_to_list = malloc(sizeof(Output_Mapping));
                                if (!to_add_to_list) {
                                    fprintf(stderr, "Could not allocate memory\n");
                                    exit(1);
                                }
                                to_add_to_list->chip_name = chip_name;
                                to_add_to_list->feature = feature;

                                chip_feature_output = g_list_append(chip_feature_output, to_add_to_list);
                                features_to_filter = g_list_remove_link(features_to_filter, feature_iterator);
                            }
                        }
                        free(label);
                    }
                }
            }
        }

        if (g_list_length(features_to_filter) > 0) {
            for (feature_iterator = features_to_filter; feature_iterator; feature_iterator = feature_iterator->next) {
                fprintf(stderr, "Feature '%s' specified but can not be found!\n", ((char *) feature_iterator->data));
            }
            exit(1);
        }

        /* The main loop */
        while (keep_running) {
            for (output_iterator = chip_feature_output; output_iterator; output_iterator = output_iterator->next) {
                const sensors_chip_name *tmp_chip_name = ((Output_Mapping *)output_iterator->data)->chip_name;
                const sensors_feature *temp_feature = ((Output_Mapping *)output_iterator->data)->feature;

                char *tmp_label = sensors_get_label(tmp_chip_name, temp_feature);

                GString *chip_feature_str = g_string_new(tmp_label);
                g_string_replace(chip_feature_str, " ", "-", 0);
                chip_feature_str = g_string_prepend(chip_feature_str, "_");
                chip_feature_str = g_string_prepend(chip_feature_str, sprintf_chip_name(tmp_chip_name));

                switch (temp_feature->type) {
                    case SENSORS_FEATURE_TEMP:
                        output_value(chip_temp_raw(tmp_chip_name, temp_feature), chip_feature_str->str);
                        break;
                    case SENSORS_FEATURE_FAN:
                        output_value(chip_fan_raw(tmp_chip_name, temp_feature), chip_feature_str->str);
                        break;
                    default:
                        fprintf(stderr, "We currently only support SENSORS_FEATURE_TEMP & SENSORS_FEATURE_FAN!\n");
                        err = 1;
                        break;
                }
                 g_string_free(chip_feature_str, 1);
                 free(tmp_label);
            }

            if (measurement_amount != -1) measurement_amount--; // only decrement if switch was given to not overflow.
            if (!measurement_amount) break;
            usleep(msleep_time * 1000);
        }
        g_list_free_full(chip_feature_output, free);
    }

    fflush(stdout);
    sensors_cleanup();
    exit(err);
}
