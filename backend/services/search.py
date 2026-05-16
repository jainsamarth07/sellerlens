"""Azure AI Search service for semantic search over seller data."""

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from backend.config import settings


class SearchService:
    """Query the Azure AI Search index for relevant seller-data chunks."""

    def __init__(self) -> None:
        self.client = SearchClient(
            endpoint=settings.azure_ai_search_endpoint,
            index_name=settings.azure_ai_search_index_name,
            credential=AzureKeyCredential(settings.azure_ai_search_key),
        )

    def search(self, query: str, top: int = 5) -> list[str]:
        """Return the top-k most relevant text chunks for *query*."""
        results = self.client.search(
            search_text=query,
            top=top,
            query_type="semantic",
            semantic_configuration_name="default",
        )
        return [doc["content"] for doc in results if "content" in doc]

    def index_document(self, doc_id: str, content: str, metadata: dict | None = None) -> None:
        """Upsert a single document into the search index."""
        document: dict = {"id": doc_id, "content": content}
        if metadata:
            document["metadata"] = str(metadata)
        self.client.upload_documents(documents=[document])
