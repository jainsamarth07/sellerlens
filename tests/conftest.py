"""Test bootstrap — sets stub env vars so ``backend.config.Settings`` can
initialise without a real ``.env`` file.

Must run *before* any test module imports ``backend.config`` (which happens
transitively via the service modules under test).
"""

from __future__ import annotations

import os

_DEFAULTS = {
    "AZURE_OPENAI_ENDPOINT": "https://stub.openai.azure.com/",
    "AZURE_OPENAI_API_KEY": "stub-key",
    "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o",
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://stub.cognitiveservices.azure.com/",
    "AZURE_DOCUMENT_INTELLIGENCE_KEY": "stub-key",
    "AZURE_STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true",
    "AZURE_STORAGE_CONTAINER_NAME": "test-uploads",
    "AZURE_AI_SEARCH_ENDPOINT": "https://stub.search.windows.net/",
    "AZURE_AI_SEARCH_KEY": "stub-key",
    "DATABASE_URL": "sqlite:///:memory:",
    "APP_ENV": "test",
}

for k, v in _DEFAULTS.items():
    os.environ.setdefault(k, v)
