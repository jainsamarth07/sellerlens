"""Centralised configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — populated from .env or environment."""

    # Azure OpenAI
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment_name: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"

    # Azure Document Intelligence
    azure_document_intelligence_endpoint: str
    azure_document_intelligence_key: str

    # Azure Blob Storage
    azure_storage_connection_string: str
    azure_storage_container_name: str = "seller-uploads"

    # Azure AI Search
    azure_ai_search_endpoint: str
    azure_ai_search_key: str
    azure_ai_search_index_name: str = "seller-data-index"

    # PostgreSQL
    database_url: str = "postgresql://postgres:postgres@localhost:5432/analytics"

    # App
    app_env: str = "development"
    app_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()  # type: ignore[call-arg]
