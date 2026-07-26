class DocumentNotFoundException(Exception):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message


class TenantNotFoundException(Exception):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message


class UserNotFoundException(Exception):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message

class StorageOperationError(Exception):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message


class PostgreSQLOperationError(Exception):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message


class TenantServiceError(Exception):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message


class UserServiceError(Exception):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message


class DocumentServiceError(Exception):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message