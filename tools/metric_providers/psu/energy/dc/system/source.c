


/*******************************************************************************
 *
 *  This is a modfied version of https://github.com/picotech/picosdk-c-examples/blob/master/picohrdl/picohrdlCon/picohrdlCon.c
 *
 * The original code was licensed under ICS (https://github.com/picotech/picosdk-c-examples/blob/master/LICENSE.md)
 *
 ******************************************************************************/

#include <stdio.h>
#include <math.h>

#ifdef WIN32
#include <conio.h>
#include <windows.h>
#include "HRDL.h"

#else
#include <sys/types.h>
#include <string.h>
#include <termios.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdlib.h>
#include <ctype.h>
#include <signal.h>
#include <sys/time.h>


#include "libpicohrdl/HRDL.h"

#ifdef DEBUG_BUILD2
#  define DEBUG(fmt, ...) fprintf(stderr, fmt, ##__VA_ARGS__)
#else
#  define DEBUG(fmt, ...) do {} while (0)
#endif

#define Sleep(a) usleep(1000*a)
#define scanf_s scanf
#define fscanf_s fscanf
#define memcpy_s(a,b,c,d) memcpy(a,c,d)




/* A function to get a single character on Linux */
#define max(a,b) ((a) > (b) ? a : b)
#define min(a,b) ((a) < (b) ? a : b)
#endif

struct structChannelSettings
{
    int16_t enabled;
    HRDL_RANGE range;
    int16_t singleEnded;
} g_channelSettings[HRDL_MAX_ANALOG_CHANNELS + 1];

#define BUFFER_SIZE 1000

int32_t        g_times[BUFFER_SIZE];
int32_t        g_values[BUFFER_SIZE];

int32_t        g_scaleTo_mv;
int16_t        g_device;
int16_t        g_maxNoOfChannels;

static unsigned int msleep_time=1000;


double inputRangeDivider [] = {1, 2, 4, 8, 16, 32, 64}; // Used for different voltage scales

/****************************************************************************
*
* ResetChannels
*
* Switches all the channels to off
* The voltage level to 2500 mV range,
* All to single-ended
*
****************************************************************************/
void ResetChannels()
{
    int32_t i;

    for (i = HRDL_ANALOG_IN_CHANNEL_1; i <= HRDL_MAX_ANALOG_CHANNELS; i++)
    {
        g_channelSettings[i].enabled = 0;
        g_channelSettings[i].range = (HRDL_RANGE) 0;
        g_channelSettings[i].singleEnded = 1;
        DEBUG("Status after disabling channel %d: %d\n",
                i,
                HRDLSetAnalogInChannel(g_device, i, (int16_t) 0, (HRDL_RANGE) 0, (int16_t) 0));
    }
}

/****************************************************************************
*
* AdcTo_mv
*
* If the user selects scaling to millivolts,
* Convert an ADC count into millivolts
*
****************************************************************************/
float AdcToMv (HRDL_INPUTS channel, int32_t raw)
{
    int32_t maxAdc = 0;
    int32_t minAdc = 0;

    if (channel < HRDL_ANALOG_IN_CHANNEL_1 || channel > HRDL_MAX_ANALOG_CHANNELS)
    {
        return 0;
    }

    if (raw == -1)
    {
        return -1;
    }

    HRDLGetMinMaxAdcCounts(g_device, &minAdc, &maxAdc, channel);

    // To convert from adc to V you need to use the following equation
    //            maxV - minV
    //   raw =  ---------------
    //          maxAdc - minAdc
    //
    // if we assume that V and adc counts are bipolar and symmetrical about 0, the
    // equation reduces to the following:
    //            maxV
    //   raw =  --------
    //           maxAdc
    //

    //
    // Note the use of the maxAdc count for the HRDL in the equation below:
    //
    // maxAdc is always 1 adc count short of the advertised full voltage scale
    // minAdc is always exactly the advertised minimum voltage scale.
    //
    // It is this way to ensure that we have an adc value that
    // equates to exactly zero volts.
    //
    // maxAdc     == maxV
    // 0 adc      == 0 V
    // minAdc     == minV
    //

    if (g_scaleTo_mv)
    {
        return (float)  ((double) raw * (2500.0 / pow(2.0, (double) g_channelSettings[channel].range)) / (double)(maxAdc));
    }
    else
    {
        return (float) raw;
    }

}


/****************************************************************************
*
* SetAnalogChannels
*  This function demonstrates how to detect available input range and set it.
*  We will first check to see if a channel is available, then check what ranges
*  are available and then check to see if differential mode is supported for thet
*  channel.
*
****************************************************************************/
void SetAnalogChannels(void)
{

    ResetChannels();
    /*
    for(int channel = HRDL_ANALOG_IN_CHANNEL_1; channel <= HRDL_MAX_ANALOG_CHANNELS; channel+=2) {
        int status = HRDLSetAnalogInChannel(g_device, channel, (int16_t) 1, HRDL_625_MV, (int16_t) 0);
        printf("Status after enabling channel %d: %d\n", channel, status);

        g_channelSettings[channel].enabled = 1;
        g_channelSettings[channel].range = HRDL_625_MV;
        g_channelSettings[channel].singleEnded = 0;
    }
    */
     g_channelSettings[HRDL_ANALOG_IN_CHANNEL_1].enabled = 1;
     g_channelSettings[HRDL_ANALOG_IN_CHANNEL_1].range = HRDL_156_MV;
     g_channelSettings[HRDL_ANALOG_IN_CHANNEL_1].singleEnded = 0;


}


/****************************************************************************
*
* OpenDevice
*  this function demonstrates how to open the next available unit
*
****************************************************************************/
int16_t OpenDevice(int16_t async)
{
    int16_t device = 0;

    if (async)
    {
        //
        // Start the Asynchronous opening routine
        //
        if (HRDLOpenUnitAsync())
        {
            //
            // You can now go and do other things while the unit is opening
            //
            while (HRDLOpenUnitProgress(&device, NULL) == HRDL_OPEN_PROGRESS_PENDING)
            {
                DEBUG(".");
                Sleep(500);
            }

            DEBUG("\n");
        }
    }
    else
    {
        //
        // Start the opening routine, this will block until the
        // device open routine completes
        //
        device = HRDLOpenUnit();
    }

    return device;
}

/****************************************************************************
*
* SelectUnit
*    This function demonstrates how to open all available units and
*    select the required one.
*
****************************************************************************/
int16_t SelectUnit(void)
{
    int16_t devices[HRDL_MAX_PICO_UNITS];
    int8_t line[80];

    int16_t async;
    int16_t i;

    int16_t deviceToUse = 0;
    int16_t ndevicesFound = 0;

    DEBUG("\n\nOpen devices Asynchronously (Y/N)?");
    async = 1;

    DEBUG ("\n\nOpening devices.\n");

    for (i = 0; i < HRDL_MAX_UNITS; i++)
    {
        devices[i] = OpenDevice(async);

        //
        // If the device is available give the user the option of using it
        //
        if (devices[i] > 0)
        {
            HRDLGetUnitInfo(devices[i], line, sizeof (line), HRDL_BATCH_AND_SERIAL);
            DEBUG("%d: %s\n", i + 1, line);
            ndevicesFound++;
        }
        else
        {
            HRDLGetUnitInfo(devices[i], line, sizeof (line), HRDL_ERROR);

            if (atoi((char*)line ) == HRDL_NOT_FOUND)
            {
                DEBUG("%d: No Unit Found\n", i + 1);
            }
            else
            {
                DEBUG("%d: %s\n", i+1, line);
            }
        }
    }

    //
    // If there is more than one device available, let the user choose now
    //
    if (ndevicesFound > 1)
    {
        //
        // Now let the user choose a device to use
        //
        DEBUG("Choose the unit from selection above\n");

        do
        {
            deviceToUse = 0;

        } while( (deviceToUse < 0 || deviceToUse > HRDL_MAX_PICO_UNITS ) && devices[deviceToUse] > 0);

        //
        // Finally, close all the units that we didnt want
        //
        for (i = 0; i < HRDL_MAX_PICO_UNITS; i++)
        {
            if ( (i != deviceToUse) && (devices[i] > 0))
            {
                HRDLCloseUnit(devices[i]);
            }
        }
    }
    else if (ndevicesFound == 1)
    {
        //
        // Select the only device found
        //
        for (i = 0; i < HRDL_MAX_PICO_UNITS; i++)
        {
            if (devices[i] > 0)
            {
                deviceToUse = i;
                break;
            }
        }
    }

    return ndevicesFound > 0 ? devices[deviceToUse] : 0;

}


/****************************************************************************
* Main work functions
*
****************************************************************************/

void StreamChannels (void)
{
    struct timeval now;
    struct timeval before;

    int32_t        i;
    int32_t        nValues;
    int16_t        channel;
    int16_t        numberOfActiveChannels;
    int8_t         strError[80];
    int16_t        status = 1;

    DEBUG("Collect streaming...\n");
    DEBUG("Data is written to disk file (test.csv)\n");
    DEBUG("Press a key to start\n");

    DEBUG("MAX analog channels are: %d \n", HRDL_MAX_ANALOG_CHANNELS);

    for (i = HRDL_ANALOG_IN_CHANNEL_1; i <= g_maxNoOfChannels; i++) {
        DEBUG("Checking channels at start: %d \n", i);
        status = HRDLSetAnalogInChannel(g_device,
                                     (int16_t)i,
                                        g_channelSettings[i].enabled,
                                        (int16_t) g_channelSettings[i].range,
                                        g_channelSettings[i].singleEnded);
        if (status == 0) {
            HRDLGetUnitInfo(g_device, strError, (int16_t) 80, HRDL_SETTINGS);
            fprintf(stderr, "Error occurred: %s\n\n", strError);
            return;
        }
    }

    HRDLGetNumberOfEnabledChannels(g_device, &numberOfActiveChannels);
    numberOfActiveChannels = numberOfActiveChannels;


    HRDLSetInterval(g_device, msleep_time, HRDL_60MS);     // Collect data at 1 second intervals, with maximum resolution

    DEBUG("Starting data collection...\n");
    status = HRDLRun(g_device, BUFFER_SIZE, (int16_t) HRDL_BM_STREAM);

    if (status == 0) {
        HRDLGetUnitInfo(g_device, strError, (int16_t) 80, HRDL_SETTINGS);
        fprintf(stderr, "Error occurred: %s\n\n", strError);
        return;
    }
    HRDLGetUnitInfo(g_device, strError, (int16_t) 80, HRDL_ERROR);
    DEBUG("Get Error Info: %s\n\n", strError);
    HRDLGetUnitInfo(g_device, strError, (int16_t) 80, HRDL_SETTINGS);
    DEBUG("Get Settings Info: %s\n\n", strError);


    while (!HRDLReady(g_device))
    {
        Sleep (1000);
    }

    gettimeofday(&before, NULL);


    while (1) {



        nValues = HRDLGetTimesAndValues(g_device, g_times, g_values, NULL, BUFFER_SIZE/numberOfActiveChannels);
        //printf ("%d values\n", nValues);

        if(nValues > 0) {
            gettimeofday(&now, NULL); // at least one nValues is available
            for (i = 0; i < nValues * 1;)
            {
                for (channel = HRDL_DIGITAL_CHANNELS; channel <= HRDL_MAX_ANALOG_CHANNELS; channel++) {
                    if (nValues && g_channelSettings[channel].enabled)
                    {
                        DEBUG("Timestamp: %ld%06ld - Diff: %ld - ", now.tv_sec, now.tv_usec, (now.tv_sec - before.tv_sec) + (now.tv_usec - before.tv_usec));
                        DEBUG("g_times: %ld and %ld\t", g_times[0], g_times[1]);
                        DEBUG("Channel %d: ", channel);
                        DEBUG("%f \n", ((AdcToMv((HRDL_INPUTS) channel, g_values [i]) / 1000) / 0.005) * 12 * msleep_time * 1000);
                        printf("%ld%06ld %d\n", now.tv_sec, now.tv_usec, (int)(((AdcToMv((HRDL_INPUTS) channel, g_values [i]) / 1000) / 0.005) * 12 * msleep_time));
                        i++;
                    }
                }
            }
            before.tv_usec = now.tv_usec;
            before.tv_sec = now.tv_sec;
        }
        usleep(1000*msleep_time); // sleep no longer than maximum buffer size allows. We will not loose values though as results are buffered
	fflush(stdout);
   }

}


/****************************************************************************
* Handler functions
*
****************************************************************************/

void sig_term_handler(int signum, siginfo_t *info, void *ptr)
{
    DEBUG("SIGTERM RECEIVED");
    HRDLStop(g_device);
    HRDLCloseUnit(g_device);        // Close the device so that it is available for other apps
    exit(0);

}

void register_sig_handlers()
{
    static struct sigaction _sigact;

    memset(&_sigact, 0, sizeof(_sigact));
    _sigact.sa_sigaction = sig_term_handler;
    _sigact.sa_flags = SA_SIGINFO;

    sigaction(SIGTERM, &_sigact, NULL);
    sigaction(SIGINT, &_sigact, NULL);
    DEBUG("SIGINT/SIGTERM Handler registered \n");
}


/****************************************************************************
*
*
****************************************************************************/
int main (int argc, char** argv)
{
    register_sig_handlers();
    setvbuf(stdout, NULL, _IONBF, 0);

    int32_t        ok = 0;
    int8_t         line [80];
    int16_t        lineNo;


    int c;

    while ((c = getopt (argc, argv, "hi:d")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-h] [-m]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n\n");
            exit(0);
        case 'i':
            msleep_time = atoi(optarg);
            break;
        default:
            fprintf(stderr,"Unknown option %c\n",c);
            exit(-1);
        }
    }

    setvbuf(stdout, NULL, _IONBF, 0);

    DEBUG("PicoLog High Resolution Data Logger (picohrdl) driver example program for ADC-20/24 data loggers\n");
    DEBUG("Version 1.4\n");
    DEBUG("Copyright (c) 2004-2018 Pico Technology Ltd.\n");

    memset(g_channelSettings, 0, sizeof(g_channelSettings));

    g_device = SelectUnit();

    ok = g_device > 0;

    if (!ok)
    {
        fprintf(stderr, "Unable to open device\n");
        HRDLGetUnitInfo(g_device, line, sizeof (line), HRDL_ERROR);
        fprintf(stderr, "%s\n", line);
        exit(-1);
    }
    else
    {
        DEBUG("Device opened successfully.\n\n");
        DEBUG("Device Information\n");
        DEBUG("==================\n\n");

        //
        // Get all the information related to the device
        //

        for (lineNo = 0; lineNo < HRDL_ERROR; lineNo++)
        {
            HRDLGetUnitInfo(g_device, line, sizeof (line), lineNo);

            if (lineNo == HRDL_VARIANT_INFO)
            {
                switch(atoi((char*)line))
                {
                    case 20:
                        g_maxNoOfChannels = 8;
                        break;

                    case 24:
                        g_maxNoOfChannels = 16;
                        break;

                    default:
                        fprintf(stderr, "Invalid unit type returned from driver\n");
                        exit(-1);
                        return -1;
                }
            }
            #ifdef DEBUG_BUILD2
            int8_t description[7][25] = { "Driver Version    :",
                                            "USB Version       :",
                                            "Hardware Version  :",
                                            "Variant Info      :",
                                            "Batch and Serial  :",
                                            "Calibration Date  :",
                                            "Kernel Driver Ver.:"};
            #endif
            DEBUG("%s %s\n", description[lineNo], line);
        }


        DEBUG("Convert ADC counts to mV? (Y/N): \n");
        g_scaleTo_mv = 1;

        DEBUG("Reject 50Hz or 60Hz mains noise?: \n");
        HRDLSetMains(g_device, 1); // 1 is 60 Hz

        SetAnalogChannels();

        // CollectSingleBlocked();
        StreamChannels();
        // CollectBlockImmediate();

        HRDLStop(g_device);
        HRDLCloseUnit(g_device);        // Close the device so that it is available for other apps

    }
    return 0;
}
