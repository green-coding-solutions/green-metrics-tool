#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>
#include <stdlib.h>
#include <sys/time.h>

#include "parse_int.h"
#include "mcp_com.h"

/*
    This file is mostly copied from https://github.com/osmhpi/pinpoint/blob/master/src/data_sources/mcp_com.c
    Credits to Sven Köhler and the OSM group from the HPI

    In case the file is not original work: Possible prior origins of the file are unknown. However it is an implementation
    of the protocol defined here:
    - https://www.microchip.com/en-us/development-tool/ADM00706
    - https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/20005473B.pdf
*/

// we read both channels in one frame here, so 8 byte
const unsigned char f511_read_active_power[] = { 0x41, 0x0, 0x16, 0x4E, 8 };

// least significant bit first. So 0x01 0x00 will set to 0x0001
// the accumulation interval is 2^N*(1/f). f is typically 50 Hz. So N=1 would equal to 40ms max resolution
// although 2^0 can be technically set we see that the powerfactor then gets calculated wrongly and
// sometimes even a negative active power will be reported. This seems to be an undersampling issue.
// setting N = 1 should be the smallest value
// factory default is N = 4. It is unclear if this has any accuracy benefit since it was used in factory calibration.

const unsigned char f511_set_accumulation_interval[] = { 0x41, 0x00, 0xA8, 0x4D, 2, 0x01, 0x00 };  // N = 1
// const unsigned char f511_set_accumulation_interval[] = { 0x41, 0x00, 0xA8, 0x4D, 2, 0x02, 0x00 };  // N = 2
// const unsigned char f511_set_accumulation_interval[] = { 0x41, 0x00, 0xA8, 0x4D, 2, 0x03, 0x00 };  // N = 3
// const unsigned char f511_set_accumulation_interval[] = { 0x41, 0x00, 0xA8, 0x4D, 2, 0x04, 0x00 };  // N = 4 (factory default)

/* This variable ist just global for consitency with our other metric_provider source files */
static unsigned int msleep_time=1000;

enum mcp_states { init, wait_ack, get_len, get_data, validate_checksum };

enum mcp_states mcp_state = wait_ack;

int init_serial(const char *port, int baud)
{
    struct termios tty;
    int fd;

    fd = open(port, O_RDWR | O_NOCTTY | O_SYNC);
    if (fd < 0) {
        return -1;
    }

    if (tcgetattr(fd, &tty) < 0) {
        return -1;
    }

    cfsetospeed(&tty, (speed_t) baud);
    cfsetispeed(&tty, (speed_t) baud);

    tty.c_cflag |= (CLOCAL | CREAD);    /* ignore modem controls */
    tty.c_cflag &= ~CSIZE;
    tty.c_cflag |= CS8;    /* 8-bit characters */
    tty.c_cflag &= ~PARENB;    /* no parity bit */
    tty.c_cflag &= ~CSTOPB;    /* only need 1 stop bit */
    tty.c_cflag &= ~CRTSCTS;    /* no hardware flowcontrol */

    /* setup for non-canonical mode */
    tty.c_iflag &=
        ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL | IXON);
    tty.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    tty.c_oflag &= ~OPOST;

    /* fetch bytes as they become available */
    tty.c_cc[VMIN] = 1;
    tty.c_cc[VTIME] = 1;

    if (tcsetattr(fd, TCSANOW, &tty) != 0) {
        return -1;
    }
    return fd;
}

int mcp_cmd(unsigned char *cmd, unsigned int cmd_length, unsigned char *reply, int fd)
{
    int CMD_MAX_PACKET_LEN = 80;
    unsigned char buf[80];
    unsigned char command_packet[CMD_MAX_PACKET_LEN];
    int rdlen;
    uint8_t len;
    uint8_t i;
    uint8_t checksum = 0;
    uint8_t datap = 0;

    // the cmd has a length. Now we create a command_packet with an initializer (0xa5 + length + cmd + checksum), which
    // makes it in the end cmd_length + 3
    command_packet[0] = 0xa5;
    command_packet[1] = cmd_length + 3; // cmd_length gets extended by 3 byte for the command packet

    if (cmd_length > CMD_MAX_PACKET_LEN - 3) {
        fprintf(stderr, "Error: cmd_length was %d but should be < %d\n", cmd_length, CMD_MAX_PACKET_LEN);
        return -1;
    }

    // only write here cmd_length lenght as this is the actual length we have
    // copy it in starting from the 2nd position in the char array, since first two are taken for initialize and length
    memcpy(command_packet + 2, cmd, cmd_length);
    for (i = 0; i < cmd_length + 2; i++) { // here we do not need to iterate to cmd_length+3 since we are just bulding the last element
        checksum += command_packet[i];
    }
    command_packet[i] = checksum;
    tcflush(fd, TCIOFLUSH);
    // here we still have to write the +3 lenght, as this is how we now sized the command_packet
    len = write(fd, command_packet, cmd_length + 3);
    if (len != cmd_length + 3) {
        return -1;
    }
    tcdrain(fd);
    while (1) {
        rdlen = read(fd, buf, 1);
        if (rdlen == 0) {
            return -1;
        }
        switch (mcp_state) {
        case wait_ack:
            if (buf[0] == 0x06) {
                /* Only read commands will return more than an ACK */
                if ((command_packet[5] == 0x44)
                    || (command_packet[5] == 0x52)
                    || (command_packet[5] == 0x4e)) {
                    mcp_state = get_len;
                } else {
                    return 0;
                }
            }
            break;
        case get_len:
            len = buf[0];
            /* Workaround for sporadically broken packets, fix me! */
            if(len != 11){
                mcp_state = wait_ack;
                return -1;
            }
            mcp_state = get_data;
            break;
        case get_data:
            reply[datap++] = buf[0];
            if ((datap + 2) == (len - 1)) {
                mcp_state = validate_checksum;
            }
            break;
        case validate_checksum:
            mcp_state = wait_ack;
            checksum = 0x06 + len;
            for (i = 0; i < (len - 3); i++) {
                checksum += reply[i];
            }
            if (checksum == buf[0]) {
                return len - 3;
            } else {
                return -1;
            }
            break;
        default:
            mcp_state = wait_ack;
        }

    }
}



int f511_get_power(int *ch1, int *ch2, int fd)
{
    int res;
    unsigned char reply[40];
    res = mcp_cmd((unsigned char *)&f511_read_active_power,
            sizeof(f511_read_active_power), (unsigned char *)&reply, fd);
    if (res > 0) {
        *ch1 = (reply[3] << 24) + (reply[2] << 16)
            + (reply[1] << 8) + reply[0]; // change from LSB to MSB
        *ch2 = (reply[7] << 24) + (reply[6] << 16)
            + (reply[5] << 8) + reply[4];  // change from LSB to MSB
        return 0;
    } else {
        return -1;
    }
}

int f511_init(const char *port)
{
    unsigned char reply[80];
    int res;
    int fd;

    fd = init_serial(port, B115200);

    if (fd < 0) {
        fprintf(stderr, "Error. init_serial was not 0 but %d\n", fd);
        return -1;
    }
    res = mcp_cmd((unsigned char *)f511_set_accumulation_interval,
            sizeof(f511_set_accumulation_interval),
            (unsigned char *)&reply, fd);
    if(res < 0) {
        fprintf(stderr, "Error. res was not 0 but %d\n", res);
        return -1;
    }
    return fd;
}

int main(int argc, char **argv) {

    int c;
    int check_system_flag = 0;
    struct timeval now;
    int fd;
    int result;
    int data[2]; // The MCP has two outlets where you can measure.


    while ((c = getopt (argc, argv, "hi:dc")) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-h] [-m]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-c      : check system and exit\n\n");
            exit(0);
        case 'i':
            msleep_time = parse_int(optarg);
            break;
        case 'c':
            check_system_flag = 1;
            break;
        default:
            fprintf(stderr,"Unknown option %c\n",c);
            exit(-1);
        }
    }

    setvbuf(stdout, NULL, _IONBF, 0);

    fd = f511_init("/dev/ttyACM0");

    if(fd < 0) {
        fprintf(stderr, "Error. Connection could not be opened\n");
        return -1;
    }
    else if(check_system_flag) {
        exit(0);
    }

    while (1) {
        result = f511_get_power(&data[0], &data[1], fd);
        if(result != 0) {
            fprintf(stderr, "Error. Result was not 0 but %d\n", result);
            break;
        }
        // The MCP returns the current power consumption in 10mW steps.
        gettimeofday(&now, NULL);
        printf("%ld%06ld %d\n", now.tv_sec, now.tv_usec, data[0]);
        usleep(msleep_time*1000);
    }
    close(fd);

    return 0;
}
