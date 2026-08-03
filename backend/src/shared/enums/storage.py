from enum import StrEnum


class StorageProvider(StrEnum):
    MINIO = "minio"
    S3 = "s3"
    AZURE = "azure"
    LOCAL = "local"
