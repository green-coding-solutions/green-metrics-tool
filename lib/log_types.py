from enum import Enum


class LogType(Enum):
    CONTAINER_EXECUTION = 'container_execution'
    SETUP_COMMAND = 'setup_command'
    FLOW_COMMAND = 'flow_command'
    NETWORK_STATS = 'network_stats'
    EXCEPTION = 'exception'
