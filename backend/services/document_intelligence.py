"""Azure Document Intelligence service for extracting tables from documents."""

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential

from backend.config import settings


class DocumentIntelligenceService:
    """Extract structured table data from uploaded seller files."""

    def __init__(self) -> None:
        self.client = DocumentIntelligenceClient(
            endpoint=settings.azure_document_intelligence_endpoint,
            credential=AzureKeyCredential(settings.azure_document_intelligence_key),
        )

    def extract_tables(self, file_bytes: bytes) -> list[list[dict]]:
        """Return a list of tables, each table being a list of row dicts."""
        poller = self.client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=AnalyzeDocumentRequest(bytes_source=file_bytes),
        )
        result = poller.result()

        tables: list[list[dict]] = []
        if result.tables:
            for table in result.tables:
                headers: list[str] = []
                rows: list[dict] = []
                for cell in table.cells:
                    if cell.kind == "columnHeader":
                        headers.append(cell.content)
                # build row dicts
                row_indices = sorted({c.row_index for c in table.cells if c.kind != "columnHeader"})
                for ri in row_indices:
                    row = {}
                    for cell in table.cells:
                        if cell.row_index == ri and cell.kind != "columnHeader":
                            col_header = headers[cell.column_index] if cell.column_index < len(headers) else f"col_{cell.column_index}"
                            row[col_header] = cell.content
                    rows.append(row)
                tables.append(rows)
        return tables
