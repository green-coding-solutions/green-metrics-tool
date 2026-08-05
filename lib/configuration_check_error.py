from enum import Enum

Status = Enum('Status', ['INFO', 'WARN', 'ERROR'])

class ConfigurationCheckError(Exception):
    def __init__(self, message, status=Status.INFO):
        super().__init__(message)
        self.status = status

class TemperatureException(ConfigurationCheckError):
    def __init__(self, message, direction, temperature):
        super().__init__(message, Status.WARN)
        self.direction = direction  # 'hot' or 'cold'
        self.temperature = temperature
