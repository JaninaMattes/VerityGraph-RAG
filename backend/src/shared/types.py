from src.shared.enums import DocumentType

SUPPORTED_DOCUMENTS = {
    "application/pdf": DocumentType.PDF,
    "text/markdown": DocumentType.MARKDOWN,
    "text/csv": DocumentType.CSV,
    "image/png": DocumentType.IMAGE,
    "image/jpeg": DocumentType.IMAGE,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentType.DOCX,
    "application/vnd.ms-powerpoint": DocumentType.PPTX,
}
