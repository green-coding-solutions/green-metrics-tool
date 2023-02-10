#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2022 Volker Krause <vkrause@kde.org>
# SPDX-License-Identifier: LGPL-2.0-or-later

# pylint: skip-file

import argparse
import datetime
import math
import serial
import struct
import sys
import time
import signal


class PowerSpy2:
    uscale = 1.0
    iscale = 1.0
    debug = False

    def term_handler(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, term_handler)

    def __init__(self, device):
        self.s = serial.Serial(device, timeout=1.0)
        if self.debug:
            print(f"Connected to {self.s.name}", file=sys.stderr)
        self.stopRealtimeMeasure()

    def mseconds_to_period(self, milli_seconds):
        # PowerSpy v2 (assuming all other versions) supports 65535 averaging periods.
        max_avg_period = 65535
        frequency = self.getFrequency()
        periods_seconds = 1382400.0 / frequency

        avg_period = int(round(periods_seconds * (milli_seconds / 1000)))

        if avg_period > max_avg_period:
            print('PowerSpy capacity exceeded: it will be average of averaged values for one second.')
            avg_period = int(round(periods_seconds))

        return avg_period

    def sendRequest(self, req):
        if self.debug:
            print(f"> {req}", file=sys.stderr)
        self.s.write(req)

    def readResponse(self):
        res = bytearray()
        while True:
            b = self.s.read()
            if b == b'\r' or b == b'\n' or b == b'':
                continue
            res.append(b[0])
            if b == b'>':
                break
        if self.debug:
            print(f"< {bytes(res)}", file=sys.stderr)
        return bytes(res)

    def readBinaryResponse(self, size):
        res = self.s.read(size)
        if self.debug:
            print(f"< [BINARY]{bytes(res).hex()}", file=sys.stderr)
        return bytes(res)

    def readEeprom(self, start, end):
        res = bytearray()
        for i in range(start, end):
            self.sendRequest('<V{:02X}>'.format(i).encode())
            res.append(int(self.readResponse()[1:3], 16))
        return bytes(res)

    def readEepromFloat(self, offset):
        b = self.readEeprom(offset, offset + 4)
        return struct.unpack('f', b)[0]

    def initCallibration(self):
        self.uscale = self.readEepromFloat(0x0E)
        self.iscale = self.readEepromFloat(0x12)

    def identityRequest(self):
        self.sendRequest(b'<?>')
        res = self.readResponse()
        print(res[1:9].decode())
        print(f"System status: {res[9:10].decode()}")
        print(f"PLL locked: {int(res[10:12], 16)}")
        print(f"Trigger status: {int(res[12:14], 16)}")
        print(f"SW version: {int(res[14:16], 16)}")
        print(f"HW version: {int(res[16:18], 16)}")
        print(f"HW serial number: {int(res[18:22], 16)}")

    def dumpEeprom(self):
        print("EEPROM content:")
        for i in range(0, 16):
            line = self.readEeprom(i * 16, i * 16 + 16)
            print(f"{i*16:02X}: {line.hex(' ')}")

    def showCalibration(self):
        # TODO callibration times
        print(f"Factory correction voltage coefficient: {self.readEepromFloat(0x02)}")
        print(f"Factory correction current coefficient: {self.readEepromFloat(0x06)}")
        print(f"Actual correction voltage coefficient: {self.readEepromFloat(0x0E)}")
        print(f"Actual correction current coefficient: {self.readEepromFloat(0x12)}")

    def measureRealtime(self, periods):
        self.initCallibration()
        self.sendRequest(f"<J{periods:04X}>".encode())
        self.readResponse()  # TODO check for errors
        sys.stdout.buffer.write(b'RMS Voltage [V];RMS Current [A];RMS Power [W];Peak Voltage [V];Peak Current [A]\n')
        while True:
            try:
                res = self.readResponse()
                # We need to check if this is correct! Take with a grain of salt till then
                rmsVoltage = math.sqrt(int(res[1:9], 16) * math.pow(self.uscale, 2))
                rmsCurrent = math.sqrt(int(res[10:18], 16) * math.pow(self.iscale, 2))

                # This seems to be fine
                rmsPower = int(res[19:27], 16) * self.uscale * self.iscale
                peakVoltage = int(res[28:32], 16) * self.uscale
                peakCurrent = int(res[33:37], 16) * self.iscale
                sys.stdout.buffer.write(
                    f"{rmsVoltage:.3f};{rmsCurrent:.3f};{rmsPower:.3f};{peakVoltage:.3f};{peakCurrent:.3f}\n".encode())
                sys.stdout.buffer.flush()
            except KeyboardInterrupt:
                break
        self.stopRealtimeMeasure()

    def measurePowerRealtime(self, milliseconds, unit='mW', use_package_time=False):

        self.initCallibration()
        periods = self.mseconds_to_period(milliseconds)
        self.sendRequest(f"<J{periods:04X}>".encode())
        self.readResponse()  # TODO check for errors
        while True:
            timestamp_before = time.time_ns()

            try:
                res = self.readResponse()
                if res[19:25] == b'FFFFFF':
                    # This is a little hacky but if nothing is plugged into the powerspy it returns
                    # b'FFFFFFF' so we set it to 0 to avoid confusion
                    rmsPower = 0
                else:
                    # The return value seems to be watt
                    rmsPower = int(res[19:27], 16) * self.uscale * self.iscale

                    if use_package_time:
                        # We need to calculate the time for joule output
                        timestamp_after = time.time_ns()
                        effective_sleep_time = timestamp_after - timestamp_before
                        # we want microjoule. Therefore / 10**9 to get seconds and then * 10**3 to get mJ
                        conversion_factor = effective_sleep_time / 1_000_000

                    if unit == 'mW':
                        rmsPower = rmsPower * 1_000
                    elif unit == 'W':
                        pass
                    elif unit == 'J':
                        if use_package_time:
                            rmsPower = rmsPower / 1_000 * conversion_factor
                        else:
                            rmsPower = rmsPower / 1_000 * milliseconds
                        rmsPower = rmsPower
                    elif unit == 'mJ':
                        if use_package_time:
                            rmsPower = rmsPower * conversion_factor
                        else:
                            rmsPower = rmsPower * milliseconds
                    else:
                        raise ValueError("Unit needs to be mW, W, J or mJ")

                # We have no real way of showing which unit the output is. The user will need to take care of this!
                sys.stdout.buffer.write(f"{int(time.time_ns()/ 1000)} {int(rmsPower)}\n".encode())
            except KeyboardInterrupt:
                sys.stdout.buffer.flush()
                break

        self.stopRealtimeMeasure()

    def stopRealtimeMeasure(self):
        self.sendRequest(b'<Q>')
        self.readResponse()  # TODO check for errors

    def frequencyRequest(self):
        print(f"Frequncy: {self.getFrequency()*0.01}Hz")

    def getFrequency(self):
        self.sendRequest(b'<F>')
        res = self.readResponse()
        return int(res[2:6], 16)

    def getRealTimeClock(self):
        self.sendRequest(b'<G>')
        res = self.readResponse()
        dt = datetime.datetime(2000 + int(res[1:3], 16), int(res[3:5], 16),
                               int(res[5:7], 16), int(res[7:9], 16), int(res[9:11], 16), int(res[11:13], 16))
        print(dt)

    def startLog(self):
        self.sendRequest(b'<O>')
        res = self.readResponse()  # TODO error handling

    def stopLog(self):
        self.sendRequest(b'<P>')
        res = self.readResponse()  # TODO error handling
        print(res)

    def setLogPeriod(self, periods):
        self.sendRequest(f"<M{periods:02X}>".encode())
        res = self.readResponse()  # TODO error handling

    def listFiles(self):
        self.sendRequest(b'<U>')
        files = self.readResponse()[1:-2].split(b'/')
        result = []
        for file in files:
            f = file.split(b':')
            result.append((f[0].decode(), int(f[1], 16)))
        return result

    def transferFile(self, fileName):
        # self.stop() # in case of transfering the current file, that must not change size while we do this
        fileSize = -1
        for f in self.listFiles():
            if f[0] == fileName:
                fileSize = f[1]
                break
        if fileSize < 0:
            print(f"No such file: {fileName}", file=sys.stderr)
            return

        fileSize += 2  # for the enclosing angle brackets, which is even there in case of block reads
        for block in range(0, (fileSize // 2048) + 1):
            self.sendRequest(f"<X{fileName[0:6]} {block:04X}>".encode())
            if block < fileSize // 2048:
                res = self.readBinaryResponse(2048)
            else:
                res = self.readBinaryResponse(fileSize % 2048)
            # strip encloding angle brackets
            if block == 0:
                res = res[1:]
            if block == fileSize // 2048:
                res = res[:-1]
            sys.stdout.buffer.write(res)

    def setCaptureLength(self, periods):
        self.sendRequest(f"<L{periods:02X}>".encode())
        res = self.readResponse()  # TODO error handling

    def startCapture(self):
        self.sendRequest(b'<S>')
        res = self.readResponse()  # TODO error handling

    def cancelCapture(self):
        self.sendRequest(b'<P>')
        res = self.readResponse()  # TODO error handling
        print(res)

    def readDataBufferA(self):
        self.sendRequest(b'<A>')
        header = self.readBinaryResponse(3)
        size = struct.unpack('>H', header[1:3])[0]
        res = self.readBinaryResponse(size * 8)
        print(res, len(res), size)  # TODO - decode

    def readDataBufferB(self):
        self.sendRequest(b'<B>')
        res = self.readBinaryResponse(65536)  # TODO seems to be 1024 * number of capture periods?
        print(res, len(res))  # TODO - decode


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='PowerSpy2 power analyzer tool.')
    parser.add_argument(
        'command',
        type=str,
        nargs=1,
        help='Command: identify, dump-eeprom, show-calibration, show-clock, frequency, measure, ls, get, start-log, stop-log, read, start-capture, cancel-capture')
    parser.add_argument('--debug', action='store_true', help='Print device communication')
    parser.add_argument('--device', default='/dev/rfcomm0', help='RFCOMM device to connect to')
    parser.add_argument('--period', '-p', type=int, default=50, help='Measurement interval in number of periods')
    args, extraargs = parser.parse_known_args()

    p = PowerSpy2(args.device)
    if args.debug:
        p.debug = True

    if args.command[0] == 'identify':
        p.identityRequest()
    elif args.command[0] == 'dump-eeprom':
        p.dumpEeprom()
    elif args.command[0] == 'show-calibration':
        p.showCalibration()
    elif args.command[0] == 'show-clock':
        p.getRealTimeClock()
    elif args.command[0] == 'frequency':
        p.frequencyRequest()
    elif args.command[0] == 'measure':
        p.measureRealtime(args.period)
    elif args.command[0] == 'start-log':
        p.startLog()
    elif args.command[0] == 'stop-log':
        p.stopLog()
    elif args.command[0] == 'ls':
        files = p.listFiles()
        for f in files:
            print(f"{f[0]} ({f[1]} bytes)")
    elif args.command[0] == 'get':
        p.transferFile(extraargs[0])
    elif args.command[0] == 'read':
        p.readDataBufferA()
        p.readDataBufferB()
    elif args.command[0] == 'start-capture':
        p.setCaptureLength(args.period)
        p.startCapture()
    elif args.command[0] == 'cancel-capture':
        p.cancelCapture()
    elif args.command[0] == 'set-log':
        p.setLogPeriod(args.period)
    else:
        parser.print_help()
