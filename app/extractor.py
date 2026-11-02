"""Turns a PDF into a validated Pydantic object with Claude structured outputs."""

import base64
from typing import Protocol

import anthropic
from pydantic import BaseModel

from app.config import settings
from app.schemas import SCHEMAS, DocumentType

SYSTEM_PROMPT = (
    "You extract structured data from business documents. "
    "Copy values exactly as they appear in the document. "
    "If a field is not present, leave it null instead of guessing."
)


class ExtractionError(Exception):
    pass


class Extractor(Protocol):
    def extract(self, pdf_bytes: bytes, document_type: DocumentType) -> BaseModel: ...


class ClaudeExtractor:
    def __init__(self, client: anthropic.Anthropic | None = None, model: str | None = None):
        self.client = client or anthropic.Anthropic()
        self.model = model or settings.claude_model

    def extract(self, pdf_bytes: bytes, document_type: DocumentType) -> BaseModel:
        schema = SCHEMAS[document_type]
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode()
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                output_config={"effort": "medium"},
                # Re-run a safety-declined request on Anthropic's recommended fallback model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                        },
                        {"type": "text", "text": f"Extract this {document_type.value.replace('_', ' ')}."},
                    ],
                }],
                output_format=schema,
            )
        except anthropic.RateLimitError as e:
            raise ExtractionError("Rate limited by the Claude API, try again shortly") from e
        except anthropic.BadRequestError as e:
            raise ExtractionError(f"Claude rejected the document: {e.message}") from e
        except anthropic.APIStatusError as e:
            raise ExtractionError(f"Claude API error {e.status_code}") from e
        except anthropic.APIConnectionError as e:
            raise ExtractionError("Could not reach the Claude API") from e

        if response.stop_reason == "refusal":
            raise ExtractionError("The model declined to process this document")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise ExtractionError("The extraction was incomplete")
        return response.parsed_output
