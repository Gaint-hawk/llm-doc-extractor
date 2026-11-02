"""Checks the request ClaudeExtractor sends and how it handles responses, without calling the API."""

from types import SimpleNamespace

import pytest

from app.extractor import ClaudeExtractor, ExtractionError
from app.schemas import DocumentType, Invoice


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def make(response):
    messages = FakeMessages(response)
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return ClaudeExtractor(client=client, model="claude-opus-5-5"), messages


def test_sends_pdf_as_document_block_with_schema():
    parsed = Invoice(vendor_name="Acme")
    extractor, messages = make(SimpleNamespace(stop_reason="end_turn", parsed_output=parsed))
    assert extractor.extract(b"%PDF-1.4", DocumentType.invoice) is parsed

    sent = messages.kwargs
    assert sent["model"] == "claude-opus-5-5"
    assert sent["output_format"] is Invoice
    assert sent["fallbacks"] == "default"
    block = sent["messages"][0]["content"][0]
    assert block["type"] == "document"
    assert block["source"]["media_type"] == "application/pdf"


def test_refusal_raises():
    extractor, _ = make(SimpleNamespace(stop_reason="refusal", parsed_output=None))
    with pytest.raises(ExtractionError, match="declined"):
        extractor.extract(b"%PDF-1.4", DocumentType.invoice)


def test_truncated_output_raises():
    extractor, _ = make(SimpleNamespace(stop_reason="max_tokens", parsed_output=None))
    with pytest.raises(ExtractionError, match="incomplete"):
        extractor.extract(b"%PDF-1.4", DocumentType.spec_sheet)
