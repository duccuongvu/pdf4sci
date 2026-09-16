(() => {
  "use strict";

  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const fileInfo = document.getElementById("file-info");
  const fileNameEl = document.getElementById("file-name");
  const fileSizeEl = document.getElementById("file-size");
  const analysisSummary = document.getElementById("analysis-summary");
  const settingsForm = document.getElementById("settings-form");
  const compressBtn = document.getElementById("compress-btn");
  const targetSizeInput = document.getElementById("target-size");
  const presetSelect = document.getElementById("preset");
  const maxDpiInput = document.getElementById("max-dpi");
  const minJpegQualityInput = document.getElementById("min-jpeg-quality");
  const statusEl = document.getElementById("status");
  const statusText = document.getElementById("status-text");
  const errorBox = document.getElementById("error-box");
  const errorMessage = document.getElementById("error-message");
  const errorDetailsToggle = document.getElementById("error-details-toggle");
  const errorDetails = document.getElementById("error-details");
  const resultEl = document.getElementById("result");
  const resultBefore = document.getElementById("result-before");
  const resultAfter = document.getElementById("result-after");
  const resultReduction = document.getElementById("result-reduction");
  const resultWarning = document.getElementById("result-warning");
  const validationList = document.getElementById("validation-list");
  const resultImages = document.getElementById("result-images");
  const downloadLink = document.getElementById("download-link");
  const compressAnotherBtn = document.getElementById("compress-another");

  let currentToken = null;

  function hide(el) { el.hidden = true; }
  function show(el) { el.hidden = false; }

  function resetForNewUpload() {
    hide(resultEl);
    hide(errorBox);
    hide(statusEl);
    hide(analysisSummary);
    hide(settingsForm);
    hide(fileInfo);
    currentToken = null;
    fileInput.value = "";
  }

  function showError(message, details) {
    errorMessage.textContent = message;
    if (details) {
      errorDetails.textContent = details;
      show(errorDetailsToggle);
      hide(errorDetails);
      errorDetailsToggle.textContent = "Show details";
    } else {
      hide(errorDetailsToggle);
      hide(errorDetails);
    }
    show(errorBox);
  }

  errorDetailsToggle.addEventListener("click", () => {
    const willShow = errorDetails.hidden;
    errorDetails.hidden = !willShow;
    errorDetailsToggle.textContent = willShow ? "Hide details" : "Show details";
  });

  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
  });

  ["dragenter", "dragover"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
    });
  });

  dropZone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length) handleFile(files[0]);
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) handleFile(fileInput.files[0]);
  });

  async function handleFile(file) {
    resetForNewUpload();

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showError("Please choose a PDF file.");
      return;
    }

    statusText.textContent = "Reading " + file.name + "…";
    show(statusEl);

    const formData = new FormData();
    formData.append("file", file);

    let response, data;
    try {
      response = await fetch("/api/upload", { method: "POST", body: formData });
      data = await response.json();
    } catch (err) {
      hide(statusEl);
      showError("Could not reach the server. Please try again.");
      return;
    }

    hide(statusEl);

    if (!response.ok) {
      showError(data.error || "Could not read this PDF.");
      return;
    }

    currentToken = data.token;
    fileNameEl.textContent = data.filename;
    fileSizeEl.textContent = data.size_human;
    show(fileInfo);

    const a = data.analysis;
    if (a && a.total_images > 0) {
      analysisSummary.textContent =
        `${a.total_images} raster image${a.total_images === 1 ? "" : "s"} · ` +
        `${a.oversized} oversized · ${a.already_optimized} already optimized`;
      show(analysisSummary);
    }

    show(settingsForm);
  }

  settingsForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentToken) return;

    hide(errorBox);
    hide(resultEl);
    compressBtn.disabled = true;
    statusText.textContent = "Compressing…";
    show(statusEl);

    const payload = {
      token: currentToken,
      preset: presetSelect.value,
    };
    if (targetSizeInput.value) payload.target_size_mb = parseFloat(targetSizeInput.value);
    if (maxDpiInput.value) payload.max_dpi = parseInt(maxDpiInput.value, 10);
    if (minJpegQualityInput.value) payload.min_jpeg_quality = parseInt(minJpegQualityInput.value, 10);

    let response, data;
    try {
      response = await fetch("/api/compress", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      data = await response.json();
    } catch (err) {
      hide(statusEl);
      compressBtn.disabled = false;
      showError("Could not reach the server. Please try again.");
      return;
    }

    hide(statusEl);
    compressBtn.disabled = false;

    if (!response.ok) {
      showError(data.error || "Compression failed.", data.details);
      return;
    }

    renderResult(data);
  });

  function renderResult(data) {
    resultBefore.textContent = data.original_size_human;
    resultAfter.textContent = data.output_size_human;
    resultReduction.textContent = `Reduction: ${data.reduction_pct}%`;

    if (data.warning) {
      resultWarning.textContent = data.warning;
      show(resultWarning);
    } else {
      hide(resultWarning);
    }

    const v = data.validation;
    const checks = [
      ["PDF valid", v.reopened_ok],
      ["Page count & dimensions preserved", v.page_count_match && v.page_dims_match],
      ["Text preserved", v.text_match],
      ["Links preserved", v.links_match],
      ["Images present", v.image_count_match],
      ["Transparency preserved", v.alpha_count_match],
      ["Vector content preserved", v.vector_count_match],
    ];
    validationList.innerHTML = "";
    for (const [label, ok] of checks) {
      const li = document.createElement("li");
      li.className = ok ? "pass" : "fail";
      li.textContent = label;
      validationList.appendChild(li);
    }

    resultImages.textContent =
      `${data.images_optimized} image${data.images_optimized === 1 ? "" : "s"} optimized, ` +
      `${data.images_kept} unchanged`;

    downloadLink.href = data.download_url;
    show(resultEl);
  }

  compressAnotherBtn.addEventListener("click", () => {
    resetForNewUpload();
  });
})();
