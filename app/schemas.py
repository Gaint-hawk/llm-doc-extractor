"""Output schemas Claude fills in. Each document type maps to one Pydantic model."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    invoice = "invoice"
    spec_sheet = "spec_sheet"


class LineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class Invoice(BaseModel):
    vendor_name: str
    invoice_number: str | None = None
    invoice_date: str | None = Field(None, description="ISO 8601 date if present")
    currency: str | None = Field(None, description="ISO 4217 code, e.g. USD")
    line_items: list[LineItem] = []
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None


class SpecAttribute(BaseModel):
    name: str
    value: str
    unit: str | None = None


class SpecSheet(BaseModel):
    manufacturer: str | None = None
    product_name: str
    model_number: str | None = None
    attributes: list[SpecAttribute] = []


SCHEMAS: dict[DocumentType, type[BaseModel]] = {
    DocumentType.invoice: Invoice,
    DocumentType.spec_sheet: SpecSheet,
}


class ExtractionOut(BaseModel):
    id: int
    filename: str
    document_type: DocumentType
    status: str
    data: dict | None
    error: str | None
    created_at: datetime
