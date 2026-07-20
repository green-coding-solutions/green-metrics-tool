#ifndef __MCP_COM_H
#define __MCP_COM_H

#include <stdbool.h>
#include <stdint.h>

enum mcp_types { f501, f511 };

int f511_init(const char *port, bool enable_energy);
/* Power in raw MCP units for channel 1 and 2 */
int f511_get_power(uint32_t *ch1, uint32_t *ch2, int fd);
/* Import-active energy counter in raw MCP units for channel 1 and 2 */
int f511_get_energy(uint64_t *ch1, uint64_t *ch2, int fd);
int f511_set_energy_counting(int fd, bool enable_energy);

#endif
