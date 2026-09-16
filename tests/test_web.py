import io
import json

import pymupdf
import pytest

from pdf4sci.web.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_pdf_bytes(png_bytes) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=png_bytes(3000, 3000))  # ~3000 DPI
    page.insert_text((50, 300), "Some scientific text")
    return doc.tobytes()


def test_index_serves_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Drop PDF here" in resp.data


def test_upload_rejects_non_pdf(client):
    resp = client.post(
        "/api/upload", data={"file": (io.BytesIO(b"not a pdf"), "notes.txt")}, content_type="multipart/form-data"
    )
    assert resp.status_code == 400
    assert "PDF" in resp.get_json()["error"]


def test_upload_rejects_corrupt_pdf(client):
    resp = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b"not really a pdf"), "fake.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "valid PDF" in resp.get_json()["error"]


def test_upload_then_compress_then_download(client, png_bytes):
    pdf_bytes = _make_pdf_bytes(png_bytes)

    upload_resp = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(pdf_bytes), "paper.pdf")},
        content_type="multipart/form-data",
    )
    assert upload_resp.status_code == 200
    upload_data = upload_resp.get_json()
    assert upload_data["analysis"]["total_images"] == 1
    assert upload_data["analysis"]["oversized"] == 1
    token = upload_data["token"]

    compress_resp = client.post(
        "/api/compress",
        data=json.dumps({"token": token, "preset": "scientific"}),
        content_type="application/json",
    )
    assert compress_resp.status_code == 200
    result = compress_resp.get_json()
    assert result["output_size"] < result["original_size"]
    assert result["validation"]["passed"] is True
    assert result["images_optimized"] == 1

    download_resp = client.get(result["download_url"])
    assert download_resp.status_code == 200
    assert download_resp.headers["Content-Type"] == "application/pdf"
    assert "paper_compressed.pdf" in download_resp.headers["Content-Disposition"]
    # the downloaded bytes must be a valid, reopenable PDF
    reopened = pymupdf.open(stream=download_resp.data, filetype="pdf")
    assert reopened.page_count == 1


def test_compress_with_target_size(client, png_bytes):
    pdf_bytes = _make_pdf_bytes(png_bytes)
    token = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(pdf_bytes), "paper.pdf")},
        content_type="multipart/form-data",
    ).get_json()["token"]

    original_size = len(pdf_bytes)
    target_mb = (original_size / (1024 * 1024)) / 2

    resp = client.post(
        "/api/compress",
        data=json.dumps({"token": token, "target_size_mb": target_mb}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["output_size"] <= original_size


def test_target_already_met_is_rejected_cleanly(client, png_bytes):
    pdf_bytes = _make_pdf_bytes(png_bytes)
    token = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(pdf_bytes), "paper.pdf")},
        content_type="multipart/form-data",
    ).get_json()["token"]

    resp = client.post(
        "/api/compress",
        data=json.dumps({"token": token, "target_size_mb": 999}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "nothing to compress" in resp.get_json()["error"]


def test_compress_with_unknown_token_is_rejected(client):
    resp = client.post(
        "/api/compress",
        data=json.dumps({"token": "deadbeef"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "Unknown or expired" in resp.get_json()["error"]


def test_download_with_bad_token_is_404(client):
    resp = client.get("/api/download/not-a-real-token")
    assert resp.status_code == 404


def test_download_before_compress_is_404(client, png_bytes):
    pdf_bytes = _make_pdf_bytes(png_bytes)
    token = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(pdf_bytes), "paper.pdf")},
        content_type="multipart/form-data",
    ).get_json()["token"]

    resp = client.get(f"/api/download/{token}")
    assert resp.status_code == 404
