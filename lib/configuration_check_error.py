from enum import Enum

Status = Enum('Status', ['INFO', 'WARN', 'ERROR'])

class ConfigurationCheckError(Exception):
    def __init__(self, message, status=Status.INFO):
        super().__init__(message)
        self.status = status
