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
