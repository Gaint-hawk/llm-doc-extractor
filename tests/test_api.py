import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app import main
from app.db import init_db
from app.extractor import ExtractionError
from app.schemas import Invoice, LineItem, SpecAttribute, SpecSheet
from app.storage import LocalStorage

PDF = b"%PDF-1.4\n%fake test pdf\n"


class StubExtractor:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = []

    def extract(self, pdf_bytes, document_type):
        self.calls.append(document_type)
        if self.fail:
            raise ExtractionError("The model declined to process this document")
        if document_type.value == "invoice":
            return Invoice(
                vendor_name="Acme Medical",
                invoice_number="INV-1001",
                currency="USD",
                line_items=[LineItem(description="Infusion pump", quantity=2, unit_price=1500, amount=3000)],
                total=3000,
            )
        return SpecSheet(
            manufacturer="Acme",
            product_name="Infusion Pump",
            model_number="IP-200",
            attributes=[SpecAttribute(name="Weight", value="2.1", unit="kg")],
        )


@pytest.fixture
def make_client(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _session():
        with Session() as s:
            yield s

    def _make(extractor):
        main.app.dependency_overrides = {
            main.get_session: _session,
            main.get_storage: lambda: LocalStorage(str(tmp_path)),
            main.get_extractor: lambda: extractor,
        }
        return TestClient(main.app)

    yield _make
    main.app.dependency_overrides = {}


def upload(client, doc_type="invoice", content=PDF, name="invoice.pdf"):
    return client.post(
        "/extractions",
        files={"file": (name, content, "application/pdf")},
        data={"document_type": doc_type},
    )


def test_extracts_invoice_and_stores_result(make_client, tmp_path):
    client = make_client(StubExtractor())
    r = upload(client)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "succeeded"
    assert body["data"]["vendor_name"] == "Acme Medical"
    assert body["data"]["line_items"][0]["amount"] == 3000
    assert len(list(tmp_path.iterdir())) == 1

    fetched = client.get(f"/extractions/{body['id']}").json()
    assert fetched["data"] == body["data"]


def test_spec_sheet_schema(make_client):
    client = make_client(StubExtractor())
    body = upload(client, "spec_sheet", name="pump.pdf").json()
    assert body["data"]["model_number"] == "IP-200"
    assert body["data"]["attributes"][0]["unit"] == "kg"


def test_failed_extraction_is_recorded_not_raised(make_client):
    client = make_client(StubExtractor(fail=True))
    body = upload(client).json()
    assert body["status"] == "failed"
    assert "declined" in body["error"]
    assert body["data"] is None


def test_rejects_non_pdf(make_client):
    client = make_client(StubExtractor())
    r = upload(client, content=b"hello", name="note.txt")
    assert r.status_code == 415


def test_rejects_unknown_document_type(make_client):
    client = make_client(StubExtractor())
    assert upload(client, doc_type="receipt").status_code == 422


def test_list_filters_by_type(make_client):
    client = make_client(StubExtractor())
    upload(client, "invoice")
    upload(client, "spec_sheet")
    upload(client, "invoice")
    all_rows = client.get("/extractions").json()
    invoices = client.get("/extractions", params={"document_type": "invoice"}).json()
    assert len(all_rows) == 3
    assert len(invoices) == 2
    assert all_rows[0]["id"] > all_rows[-1]["id"]


def test_missing_extraction_returns_404(make_client):
    client = make_client(StubExtractor())
    assert client.get("/extractions/999").status_code == 404
