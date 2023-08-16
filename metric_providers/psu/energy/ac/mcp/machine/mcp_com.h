#ifndef __MCP_COM_H
#define __MCP_COM_H

enum mcp_types { f501, f511 };

int f511_init(const char *port);
/* Power in 10mW for channel 1 and 2 */
int f511_get_power(int *ch1, int *ch2, int fd);

#endif