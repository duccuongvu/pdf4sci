/* Thin wrapper around PDF.js: one canvas, one page at a time, with fit-width
 * / fit-page / explicit-zoom modes and page navigation. Deliberately does
 * not do continuous scrolling -- the sidebar spec calls for a paginated
 * toolbar (‹ Page 3/8 › · Fit Width · zoom), so one rendered page keeps the
 * implementation simple and matches that. */
const PdfViewer = (() => {
  "use strict";

  pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/pdfjs/pdf.worker.min.js";

  const canvas = document.getElementById("pdf-canvas");
  const ctx = canvas.getContext("2d");
  const wrap = document.querySelector(".viewer-canvas-wrap");

  // Object URLs are owned by app.js (it needs both Original and Compressed
  // to stay alive for toggling) -- this module only ever reads them.
  let doc = null;
  let currentPage = 1;
  let scale = 1.0;
  let fitMode = "width"; // "width" | "page" | null (explicit scale)
  let renderTask = null;
  let onStateChange = () => {};

  const ZOOM_STEPS = [1.0, 1.25, 1.5, 2.0, 3.0, 4.0];

  async function load(url, state) {
    if (doc) {
      doc.destroy();
      doc = null;
    }

    const loadingTask = pdfjsLib.getDocument(url);
    doc = await loadingTask.promise;

    const initial = state || {};
    currentPage = Math.min(Math.max(initial.page || 1, 1), doc.numPages);
    scale = initial.scale || 1.0;
    fitMode = "fitMode" in initial ? initial.fitMode : "width";

    await renderCurrentPage();
    return doc.numPages;
  }

  async function renderCurrentPage() {
    if (!doc) return;
    const page = await doc.getPage(currentPage);
    const unscaled = page.getViewport({ scale: 1 });

    if (fitMode === "width") {
      scale = Math.max(0.1, (wrap.clientWidth - 40) / unscaled.width);
    } else if (fitMode === "page") {
      scale = Math.max(
        0.1,
        Math.min((wrap.clientWidth - 40) / unscaled.width, (wrap.clientHeight - 40) / unscaled.height)
      );
    }

    const viewport = page.getViewport({ scale });
    canvas.width = viewport.width;
    canvas.height = viewport.height;

    if (renderTask) {
      try { renderTask.cancel(); } catch (e) { /* already finished */ }
    }
    renderTask = page.render({ canvasContext: ctx, viewport });
    try {
      await renderTask.promise;
    } catch (err) {
      if (err && err.name === "RenderingCancelledException") return;
      throw err;
    }
    onStateChange(getState());
  }

  function getState() {
    return { page: currentPage, scale, fitMode, numPages: doc ? doc.numPages : 0 };
  }

  function setOnStateChange(cb) {
    onStateChange = cb;
  }

  async function goTo(pageNum) {
    if (!doc) return;
    const clamped = Math.max(1, Math.min(pageNum, doc.numPages));
    if (clamped === currentPage) return;
    currentPage = clamped;
    await renderCurrentPage();
  }

  async function nextPage() { await goTo(currentPage + 1); }
  async function prevPage() { await goTo(currentPage - 1); }

  async function setFit(mode) {
    fitMode = mode;
    await renderCurrentPage();
  }

  async function zoomStep(direction) {
    fitMode = null;
    let idx = ZOOM_STEPS.findIndex((z) => z >= scale - 0.001);
    if (idx === -1) idx = ZOOM_STEPS.length - 1;
    idx = Math.max(0, Math.min(ZOOM_STEPS.length - 1, idx + direction));
    scale = ZOOM_STEPS[idx];
    await renderCurrentPage();
  }

  function dispose() {
    if (renderTask) {
      try { renderTask.cancel(); } catch (e) { /* noop */ }
      renderTask = null;
    }
    if (doc) {
      doc.destroy();
      doc = null;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    canvas.width = 0;
    canvas.height = 0;
  }

  window.addEventListener(
    "resize",
    debounce(() => {
      if (doc && (fitMode === "width" || fitMode === "page")) renderCurrentPage();
    }, 150)
  );

  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  return { load, goTo, nextPage, prevPage, setFit, zoomStep, getState, setOnStateChange, dispose };
})();
