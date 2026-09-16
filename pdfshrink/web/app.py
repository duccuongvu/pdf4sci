"""Flask web app: a single-page UI over the pdfshrink backend.

Reuses analyzer.analyze_pdf / optimizer.optimize_pdf / quality.optimize_to_
target_size / validation.validate directly -- the exact same functions the
CLI calls -- so there is exactly one compression engine and one policy,
shared by both front ends.
"""

from __future__ import annotations

import os
import re
import traceback

from flask import Flask, abort, jsonify, render_template, request, send_file

from ..analyzer import analyze_pdf
from ..config import DEFAULT_PRESET, PRESETS, AnalyzerConfig
from ..optimizer import optimize_pdf
from ..pdf_utils import human_size
from ..quality import optimize_to_target_size
from ..validation import validate
from . import storage

TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_UPLOAD_BYTES = 300 * 1024 * 1024  # generous for a scientific paper


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            presets=list(PRESETS.keys()),
            default_preset=DEFAULT_PRESET,
            preset_values={
                name: {"max_dpi": p.max_dpi, "jpeg_quality": p.jpeg_quality}
                for name, p in PRESETS.items()
            },
        )

    @app.post("/api/upload")
    def upload():
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify(error="No file was uploaded."), 400
        if not f.filename.lower().endswith(".pdf"):
            return jsonify(error="Please upload a PDF file."), 400

        stored = storage.save_upload(f)
        try:
            analysis = analyze_pdf(stored.path)
        except Exception:
            storage.cleanup(stored.token)
            return jsonify(error="This does not look like a valid PDF file."), 400

        n_downsample = sum(1 for i in analysis.images if i.recommendation == "downsample")
        n_keep = len(analysis.images) - n_downsample

        return jsonify(
            token=stored.token,
            filename=stored.original_name,
            size=analysis.file_size,
            size_human=human_size(analysis.file_size),
            pages=analysis.num_pages,
            analysis={
                "total_images": len(analysis.images),
                "oversized": n_downsample,
                "already_optimized": n_keep,
                "images": [
                    {
                        "page": i.page,
                        "xref": i.xref,
                        "width": i.width,
                        "height": i.height,
                        "dpi": round(i.effective_dpi),
                        "size_human": human_size(i.compressed_size),
                        "recommendation": i.recommendation,
                    }
                    for i in analysis.images
                ],
            },
        )

    @app.post("/api/compress")
    def compress():
        data = request.get_json(force=True, silent=True) or {}
        token = data.get("token", "")
        if not TOKEN_RE.match(token) or not storage.job_exists(token):
            return jsonify(error="Unknown or expired upload. Please upload the PDF again."), 400

        preset_name = data.get("preset") or DEFAULT_PRESET
        if preset_name not in PRESETS:
            return jsonify(error=f"Unknown preset {preset_name!r}."), 400
        preset = PRESETS[preset_name]

        max_dpi = data.get("max_dpi")
        min_jpeg_quality = data.get("min_jpeg_quality")
        target_size_mb = data.get("target_size_mb")

        try:
            effective_max_dpi = int(max_dpi) if max_dpi else preset.max_dpi
            effective_jpeg_quality = int(min_jpeg_quality) if min_jpeg_quality else preset.jpeg_quality
        except (TypeError, ValueError):
            return jsonify(error="Advanced settings must be numbers."), 400

        in_path = storage.input_path(token)
        out_path = storage.output_path(token)
        original_size = os.path.getsize(in_path)

        try:
            if target_size_mb:
                target_bytes = int(float(target_size_mb) * 1024 * 1024)
                if target_bytes >= original_size:
                    return (
                        jsonify(
                            error=(
                                f"The requested target ({human_size(target_bytes)}) is already "
                                f"at or above the original size ({human_size(original_size)}); "
                                "there is nothing to compress."
                            )
                        ),
                        400,
                    )
                result = optimize_to_target_size(
                    in_path, out_path, target_bytes, min_jpeg_quality=effective_jpeg_quality
                )
                opt_results = result.results
                warning = result.warning
            else:
                config = AnalyzerConfig(max_dpi=effective_max_dpi)
                opt_results = optimize_pdf(in_path, out_path, config, jpeg_quality=effective_jpeg_quality)
                warning = None
        except Exception:
            app.logger.exception("compression failed for token %s", token)
            return (
                jsonify(
                    error=(
                        "Could not compress this PDF. It may use an image format this tool "
                        "cannot safely optimize. The original file was not modified."
                    ),
                    details=traceback.format_exc(),
                ),
                500,
            )

        report = validate(in_path, out_path)
        output_size = os.path.getsize(out_path)

        return jsonify(
            token=token,
            original_size=original_size,
            original_size_human=human_size(original_size),
            output_size=output_size,
            output_size_human=human_size(output_size),
            reduction_pct=round((1 - output_size / original_size) * 100, 1) if original_size else 0,
            warning=warning,
            images_optimized=sum(1 for r in opt_results if r.action == "optimized"),
            images_kept=sum(1 for r in opt_results if r.action != "optimized"),
            validation={
                "passed": report.passed,
                "reopened_ok": report.reopened_ok,
                "page_count_match": report.page_count_match,
                "page_dims_match": report.page_dims_match,
                "text_match": report.text_match,
                "links_match": report.links_match,
                "image_count_match": report.image_count_match,
                "alpha_count_match": report.alpha_count_match,
                "vector_count_match": report.vector_count_match,
            },
            download_url=f"/api/download/{token}",
        )

    @app.get("/api/download/<token>")
    def download(token: str):
        if not TOKEN_RE.match(token):
            abort(404)
        path = storage.output_path(token)
        if not os.path.isfile(path):
            abort(404)
        original = storage.get_original_name(token)
        stem = os.path.splitext(original)[0]
        return send_file(
            path,
            as_attachment=True,
            download_name=f"{stem}_compressed.pdf",
            mimetype="application/pdf",
        )

    return app


def main() -> None:
    create_app().run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
