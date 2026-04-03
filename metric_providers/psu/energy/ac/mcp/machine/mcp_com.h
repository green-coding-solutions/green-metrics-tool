#ifndef __MCP_COM_H
#define __MCP_COM_H

#include <stdbool.h>
#include <stdint.h>

enum mcp_types { f501, f511 };

int f511_init(const char *port, bool enable_energy);
/* Power in 1.25 mW for channel 1 and 2 with the default range settings in source.c */
int f511_get_power(int *ch1, int *ch2, int fd);
/* Import-active energy counter for channel 1 and 2 */
int f511_get_energy(uint64_t *ch1, uint64_t *ch2, int fd);
int f511_set_energy_counting(int fd, bool enable_energy);

#endif
