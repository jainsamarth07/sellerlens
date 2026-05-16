"""Azure Blob Storage service for seller file uploads."""

import uuid

from azure.storage.blob import BlobServiceClient, ContentSettings

from backend.config import settings


class StorageService:
    """Upload and manage seller files in Azure Blob Storage."""

    def __init__(self) -> None:
        self.blob_service = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string,
        )
        self.container_name = settings.azure_storage_container_name

    def upload_blob(self, filename: str, data: bytes) -> str:
        """Upload *data* and return the blob URL. Filename is prefixed with a UUID."""
        safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        container_client = self.blob_service.get_container_client(self.container_name)

        # Ensure container exists
        if not container_client.exists():
            container_client.create_container()

        blob_client = container_client.get_blob_client(safe_name)
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/octet-stream"),
        )
        return blob_client.url

    def download_blob(self, blob_url_or_name: str) -> bytes:
        """Download a blob's bytes given either its URL or its name."""
        # Extract just the blob name if a full URL was supplied
        name = blob_url_or_name.rsplit("/", 1)[-1] if "://" in blob_url_or_name else blob_url_or_name
        container_client = self.blob_service.get_container_client(self.container_name)
        return container_client.get_blob_client(name).download_blob().readall()
