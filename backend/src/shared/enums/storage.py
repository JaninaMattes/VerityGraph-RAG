from enum import StrEnum


class StorageType(StrEnum):
    MINIO = "minio"
    AWS = "aws"
    AZURE = "azure"
    LOCAL = "local"
