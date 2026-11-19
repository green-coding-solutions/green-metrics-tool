from enum import Enum

Status = Enum('Status', ['INFO', 'WARN', 'ERROR'])

class ConfigurationCheckError(Exception):
    def __init__(self, message, status=Status.INFO, error_key=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.error_key = error_key

    # Must be picklable with all attributes, as exceptions are transferred from isolated child processes
    # back to the parent (see lib/process_isolation.py). The default reduce only passes self.args (= message).
    def __reduce__(self):
        return (self.__class__, (self.message, self.status, self.error_key), self.__dict__)

    def __str__(self):
        error = f"[{self.status.name}] {self.message}"
        if self.error_key:
            return f"{error} - Disable this system check with --dev-no-system-checks={self.error_key} if running on CLI. Multiple checks can be disabled by comma separating them"
        else:
            return error

class TemperatureException(ConfigurationCheckError):
    def __init__(self, message, direction, temperature):
        super().__init__(message, Status.WARN)
        self.direction = direction  # 'hot' or 'cold'
        self.temperature = temperature

    def __reduce__(self):
        return (self.__class__, (self.message, self.direction, self.temperature), self.__dict__)
