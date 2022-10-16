/****************************************************************************
*
* Filename:    HRDL.h
* Author:			 MAS
* Description:
*
* This header defines the interface to driver routines for the PicoLog
*	High Resolution Data Logger Series.
*
* Copyright © 2004-2018 Pico Technology Ltd. All rights reserved.
*
****************************************************************************/
#pragma once

#include <stdint.h>

#ifdef PREF0
  #undef PREF0
#endif
#ifdef PREF1
  #undef PREF1
#endif
#ifdef PREF2
  #undef PREF2
#endif
#ifdef PREF3
  #undef PREF3
#endif

#ifdef __cplusplus
  #define PREF0 extern "C"
#else
  #define PREF0
	#define TYPE_ENUM enum
#endif

#ifdef WIN32
	//	If you are dynamically linking hrdl.dll into your project #define DYNLINK
	//  somewhere in your project before here.
	#ifdef DYNLINK
		#define PREF1 typedef
		#define PREF2
		#define PREF3(x) (__stdcall *x)
	#else
		#define PREF1
		#ifdef _USRDLL
			#define PREF2 __declspec(dllexport) __stdcall
		#else
			#define PREF2 __declspec(dllimport) __stdcall
		#endif
		#define PREF3(x) x
	#endif
#else
	/* Define a 64-bit integer type */
	#ifdef DYNLINK
		#define PREF1 typedef
		#define PREF2
		#define PREF3(x) (*x)
	#else
		#ifdef _USRDLL
			#define PREF1 __attribute__((visibility("default")))
		#else
			#define PREF1
		#endif
		#define PREF2
		#define PREF3(x) x
	#endif
  #define __stdcall
#endif

#define HRDL_MAX_PICO_UNITS 64
#define HRDL_MAX_UNITS 20

typedef enum enHRDLInputs
{
  HRDL_DIGITAL_CHANNELS,
  HRDL_ANALOG_IN_CHANNEL_1,
  HRDL_ANALOG_IN_CHANNEL_2,
  HRDL_ANALOG_IN_CHANNEL_3,
  HRDL_ANALOG_IN_CHANNEL_4,
  HRDL_ANALOG_IN_CHANNEL_5,
  HRDL_ANALOG_IN_CHANNEL_6,
  HRDL_ANALOG_IN_CHANNEL_7,
  HRDL_ANALOG_IN_CHANNEL_8,
  HRDL_ANALOG_IN_CHANNEL_9,
  HRDL_ANALOG_IN_CHANNEL_10,
  HRDL_ANALOG_IN_CHANNEL_11,
  HRDL_ANALOG_IN_CHANNEL_12,
  HRDL_ANALOG_IN_CHANNEL_13,
  HRDL_ANALOG_IN_CHANNEL_14,
  HRDL_ANALOG_IN_CHANNEL_15,
  HRDL_ANALOG_IN_CHANNEL_16,
  HRDL_MAX_ANALOG_CHANNELS = HRDL_ANALOG_IN_CHANNEL_16,
} HRDL_INPUTS;

typedef enum enHRDLDigitalIoChannel
{   
  HRDL_DIGITAL_IO_CHANNEL_1 = 0x01,
  HRDL_DIGITAL_IO_CHANNEL_2 = 0x02,
  HRDL_DIGITAL_IO_CHANNEL_3 = 0x04,
  HRDL_DIGITAL_IO_CHANNEL_4 = 0x08,
  HRDL_MAX_DIGITAL_CHANNELS = 4
} HRDL_DIGITAL_IO_CHANNEL;

typedef enum enHRDLRange
{
  HRDL_2500_MV,
  HRDL_1250_MV,
  HRDL_625_MV,
  HRDL_313_MV,
  HRDL_156_MV,
  HRDL_78_MV,
  HRDL_39_MV,  
  HRDL_MAX_RANGES
}	HRDL_RANGE;

typedef enum enHRDLConversionTime
{
  HRDL_60MS,
  HRDL_100MS,
  HRDL_180MS,
  HRDL_340MS,
  HRDL_660MS,
  HRDL_MAX_CONVERSION_TIMES

}	HRDL_CONVERSION_TIME;

typedef enum enHRDLInfo
{
  HRDL_DRIVER_VERSION,
  HRDL_USB_VERSION,
  HRDL_HARDWARE_VERSION,
  HRDL_VARIANT_INFO,
  HRDL_BATCH_AND_SERIAL,
  HRDL_CAL_DATE,	
  HRDL_KERNEL_DRIVER_VERSION, 
  HRDL_ERROR,
	HRDL_SETTINGS,
} HRDL_INFO;

typedef enum enHRDLErrorCode
{
	HRDL_OK,
	HRDL_KERNEL_DRIVER,
	HRDL_NOT_FOUND,
	HRDL_CONFIG_FAIL,
	HRDL_ERROR_OS_NOT_SUPPORTED,
	HRDL_MAX_DEVICES
} HRDL_ERROR_CODES;


typedef enum enSettingsError
{
	SE_CONVERSION_TIME_OUT_OF_RANGE,
	SE_SAMPLEINTERVAL_OUT_OF_RANGE,
	SE_CONVERSION_TIME_TOO_SLOW,
	SE_CHANNEL_NOT_AVAILABLE,
	SE_INVALID_CHANNEL,
	SE_INVALID_VOLTAGE_RANGE,
	SE_INVALID_PARAMETER,
	SE_CONVERSION_IN_PROGRESS,
	SE_COMMUNICATION_FAILED,
	SE_OK,
	SE_MAX = SE_OK
} SettingsError;

typedef enum enHRDLOpenProgress
{
  HRDL_OPEN_PROGRESS_FAIL     = -1,
  HRDL_OPEN_PROGRESS_PENDING  = 0,
  HRDL_OPEN_PROGRESS_COMPLETE = 1
} HRDL_OPEN_PROGRESS;

typedef enum enBlockMethod
{
  HRDL_BM_BLOCK,
  HRDL_BM_WINDOW,
  HRDL_BM_STREAM
} HRDL_BLOCK_METHOD;


#define INVALID_HRDL_VALUE 0xF0000000

PREF0 PREF1 int16_t PREF2 PREF3(HRDLOpenUnit)	 ( void );

PREF0 PREF1 int16_t PREF2 PREF3(HRDLOpenUnitAsync) (void);

PREF0 PREF1 int16_t PREF2 PREF3(HRDLOpenUnitProgress) (int16_t * handle, int16_t * progress);

PREF0 PREF1 int16_t PREF2 PREF3(HRDLGetUnitInfo) (
															int16_t handle,
															int8_t * string,
															int16_t stringLength,
															int16_t info);


PREF0 PREF1 int16_t PREF2 PREF3(HRDLCloseUnit) ( int16_t handle );

PREF0 PREF1 int16_t PREF2 PREF3(HRDLGetMinMaxAdcCounts)(int16_t handle, int32_t * minAdc, int32_t * maxAdc, int16_t channel);

PREF0 PREF1 int16_t PREF2 PREF3(HRDLSetAnalogInChannel) (int16_t handle, int16_t channel, int16_t enabled, int16_t	range, int16_t singleEnded);

PREF0 PREF1 int16_t PREF2 PREF3(HRDLSetDigitalIOChannel) (int16_t handle, int16_t directionOut, int16_t digitalOutPinState, int16_t enabledDigitalIn);

PREF0 PREF1 int16_t PREF2 PREF3(HRDLSetInterval)(int16_t handle, int32_t sampleInterval_ms, int16_t conversionTime);

PREF0 PREF1 int16_t PREF2 PREF3(HRDLRun) (int16_t handle, int32_t	nValues, int16_t	method);

PREF0 PREF1 int16_t PREF2 PREF3(HRDLReady) (int16_t handle);

PREF0 PREF1 void PREF2  PREF3(HRDLStop)(int16_t handle);

PREF0 PREF1 int32_t PREF2 PREF3(HRDLGetValues) (
  int16_t handle,
  int32_t * values,
  int16_t * overflow,
  int32_t no_of_values);

PREF0 PREF1 int32_t PREF2 PREF3(HRDLGetTimesAndValues) (
  int16_t handle,
  int32_t  * times,
  int32_t * values,
  int16_t * overflow,
  int32_t noOfValues);


// this routine blocks other functions until it returns
PREF0 PREF1 int16_t PREF2 PREF3(HRDLGetSingleValue) (
  int16_t handle,
  int16_t channel,
	int16_t	range,
	int16_t conversionTime,
	int16_t singleEnded,
	int16_t *overflow,
	int32_t *value); 

PREF0 PREF1 int16_t PREF2 PREF3(HRDLCollectSingleValueAsync) (
  int16_t handle,
  int16_t channel,
	int16_t	range,
	int16_t conversionTime,
	int16_t singleEnded
	); 

PREF0 PREF1 int16_t PREF2 PREF3(HRDLGetSingleValueAsync) (
  int16_t handle,
	int32_t *value,
	int16_t *overflow); 

PREF0 PREF1 int16_t PREF2 PREF3(HRDLSetMains)(int16_t handle, int16_t sixtyHertz);

PREF0 PREF1 int16_t PREF2 PREF3(HRDLGetNumberOfEnabledChannels)(int16_t handle, int16_t * nEnabledChannels);

PREF0 PREF1 int16_t PREF2 HRDLAcknowledge(int16_t handle);
