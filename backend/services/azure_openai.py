"""Azure OpenAI chat service using the gpt-4o deployment."""

from openai import AzureOpenAI

from backend.config import settings
from backend.services.azure_openai_service import (  # re-exports
    analyze_sku,
    generate_seller_insights,
)

__all__ = ["AzureOpenAIService", "analyze_sku", "generate_seller_insights"]

SYSTEM_PROMPT = (
    "You are an expert e-commerce profit analyst for Indian sellers on "
    "Flipkart and Amazon. Analyse the data provided and give actionable, "
    "concise insights in simple language. Use INR (₹) for all monetary values. "
    "When showing numbers, format them with Indian numbering (lakhs / crores)."
)


class AzureOpenAIService:
    """Thin wrapper around the Azure OpenAI chat completions API."""

    def __init__(self) -> None:
        self.client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self.deployment = settings.azure_openai_deployment_name

    def chat(
        self,
        user_query: str,
        context_documents: list[str] | None = None,
        profit_summary: dict | None = None,
    ) -> str:
        """Send a grounded chat request and return the assistant reply."""
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Inject retrieved context
        if context_documents:
            context_block = "\n---\n".join(context_documents)
            messages.append(
                {
                    "role": "system",
                    "content": f"Relevant seller data:\n{context_block}",
                }
            )

        if profit_summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"Profit summary JSON:\n{profit_summary}",
                }
            )

        messages.append({"role": "user", "content": user_query})

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""
