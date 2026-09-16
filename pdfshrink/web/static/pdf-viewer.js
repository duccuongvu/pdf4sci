/* Thin wrapper around PDF.js: continuous vertical scroll through all pages
 * (one <canvas> per page, lazily rendered via IntersectionObserver as they
 * scroll near the viewport), with fit-width / fit-page / explicit-zoom
 * modes, page navigation, and Ctrl+wheel to zoom. */
const PdfViewer = (() => {
  "use strict";

  pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/pdfjs/pdf.worker.min.js";

  // Object URLs are owned by app.js (it needs both Original and Compressed
  // to stay alive for toggling) -- this module only ever reads them.
  const wrap = document.querySelector(".viewer-canvas-wrap");
  const pagesContainer = document.getElementById("pdf-pages");

  let doc = null;
  let pages = []; // { proxy, wrapperEl, canvas, ctx, rendered, renderTask }
  const visiblePages = new Set();
  let scale = 1.0;
  let fitMode = "width"; // "width" | "page" | null (explicit scale)
  let currentPage = 1;
  let onStateChange = () => {};
  let observer = null;
  let scrollHandler = null;
  let suppressScrollTracking = false;

  const ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0];

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  function notifyState() {
    onStateChange(getState());
  }

  function getState() {
    return { page: currentPage, scale, fitMode, numPages: doc ? doc.numPages : 0 };
  }

  function setOnStateChange(cb) {
    onStateChange = cb;
  }

  function applyFitScale() {
    if (!pages.length) return;
    // Assumes a roughly uniform page size across the document, same as a
    // typical paper -- good enough for a fit-width/fit-page target.
    const ref = pages[0].proxy.getViewport({ scale: 1 });
    if (fitMode === "width") {
      scale = clamp((wrap.clientWidth - 40) / ref.width, 0.1, 10);
    } else if (fitMode === "page") {
      scale = clamp(
        Math.min((wrap.clientWidth - 40) / ref.width, (wrap.clientHeight - 40) / ref.height),
        0.1,
        10
      );
    }
  }

  function layoutAll() {
    for (const p of pages) {
      const vp = p.proxy.getViewport({ scale });
      p.canvas.width = Math.floor(vp.width);
      p.canvas.height = Math.floor(vp.height);
      p.canvas.style.width = vp.width + "px";
      p.canvas.style.height = vp.height + "px";
      p.rendered = false;
    }
  }

  async function renderPage(pageNum) {
    const p = pages[pageNum - 1];
    if (!p || p.rendered) return;
    if (p.renderTask) {
      try { p.renderTask.cancel(); } catch (e) { /* already finished */ }
    }
    const viewport = p.proxy.getViewport({ scale });
    p.renderTask = p.proxy.render({ canvasContext: p.ctx, viewport });
    try {
      await p.renderTask.promise;
      p.rendered = true;
    } catch (err) {
      if (err && err.name === "RenderingCancelledException") return;
      throw err;
    }
  }

  function renderVisible() {
    return Promise.all([...visiblePages].map(renderPage));
  }

  function setupObserver() {
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const pageNum = Number(entry.target.dataset.pageNumber);
          if (entry.isIntersecting) {
            visiblePages.add(pageNum);
            renderPage(pageNum);
          } else {
            visiblePages.delete(pageNum);
          }
        }
      },
      { root: wrap, rootMargin: "400px 0px 400px 0px", threshold: 0.01 }
    );
    for (const p of pages) observer.observe(p.wrapperEl);
  }

  function computeCurrentPageFromScroll() {
    const wrapRect = wrap.getBoundingClientRect();
    const target = wrapRect.top + wrapRect.height * 0.3;
    let best = 1;
    for (const p of pages) {
      const r = p.wrapperEl.getBoundingClientRect();
      if (r.top <= target) best = Number(p.wrapperEl.dataset.pageNumber);
    }
    return best;
  }

  function setupScrollTracking() {
    scrollHandler = debounce(() => {
      if (suppressScrollTracking || !pages.length) return;
      currentPage = computeCurrentPageFromScroll();
      notifyState();
    }, 100);
    wrap.addEventListener("scroll", scrollHandler);
  }

  function scrollToPage(pageNum, behavior) {
    const p = pages[pageNum - 1];
    if (!p) return;
    suppressScrollTracking = true;
    p.wrapperEl.scrollIntoView({ behavior: behavior || "smooth", block: "start" });
    currentPage = pageNum;
    notifyState();
    setTimeout(() => { suppressScrollTracking = false; }, behavior === "auto" ? 50 : 400);
  }

  async function load(url, state) {
    teardown();

    const loadingTask = pdfjsLib.getDocument(url);
    doc = await loadingTask.promise;

    const initial = state || {};
    scale = initial.scale || 1.0;
    fitMode = "fitMode" in initial ? initial.fitMode : "width";

    const proxies = await Promise.all(
      Array.from({ length: doc.numPages }, (_, i) => doc.getPage(i + 1))
    );

    pages = proxies.map((proxy, idx) => {
      const wrapperEl = document.createElement("div");
      wrapperEl.className = "pdf-page";
      wrapperEl.dataset.pageNumber = String(idx + 1);
      const canvas = document.createElement("canvas");
      wrapperEl.appendChild(canvas);
      pagesContainer.appendChild(wrapperEl);
      return { proxy, wrapperEl, canvas, ctx: canvas.getContext("2d"), rendered: false, renderTask: null };
    });

    applyFitScale();
    layoutAll();
    setupObserver();
    setupScrollTracking();

    currentPage = clamp(initial.page || 1, 1, doc.numPages);
    scrollToPage(currentPage, "auto");
    await renderPage(currentPage);
    notifyState();
    return doc.numPages;
  }

  async function goTo(pageNum) {
    if (!doc) return;
    scrollToPage(clamp(pageNum, 1, doc.numPages));
  }

  async function nextPage() { await goTo(currentPage + 1); }
  async function prevPage() { await goTo(currentPage - 1); }

  async function setFit(mode) {
    fitMode = mode;
    applyFitScale();
    layoutAll();
    await renderVisible();
    notifyState();
  }

  async function setScale(newScale) {
    scale = clamp(newScale, 0.1, 10);
    fitMode = null;
    layoutAll();
    await renderVisible();
    notifyState();
  }

  async function zoomStep(direction) {
    let idx = ZOOM_STEPS.findIndex((z) => z >= scale - 0.001);
    if (idx === -1) idx = ZOOM_STEPS.length - 1;
    idx = clamp(idx + direction, 0, ZOOM_STEPS.length - 1);
    await setScale(ZOOM_STEPS[idx]);
  }

  // Ctrl+wheel (or a trackpad pinch, which browsers report as a wheel event
  // with ctrlKey set) zooms instead of scrolling. Rapid wheel ticks are
  // coalesced into one re-render, fired shortly after the gesture settles,
  // so a fast trackpad pinch doesn't trigger a re-render per tick.
  let pendingScale = null;
  let wheelZoomTimer = null;
  wrap.addEventListener(
    "wheel",
    (e) => {
      if (!e.ctrlKey || !doc) return;
      e.preventDefault();
      const base = pendingScale ?? scale;
      const factor = Math.exp(-e.deltaY * 0.0015);
      pendingScale = clamp(base * factor, 0.1, 10);
      clearTimeout(wheelZoomTimer);
      wheelZoomTimer = setTimeout(() => {
        const target = pendingScale;
        pendingScale = null;
        setScale(target);
      }, 120);
    },
    { passive: false }
  );

  window.addEventListener(
    "resize",
    debounce(() => {
      if (doc && (fitMode === "width" || fitMode === "page")) {
        applyFitScale();
        layoutAll();
        renderVisible();
      }
    }, 150)
  );

  function teardown() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    if (scrollHandler) {
      wrap.removeEventListener("scroll", scrollHandler);
      scrollHandler = null;
    }
    for (const p of pages) {
      if (p.renderTask) {
        try { p.renderTask.cancel(); } catch (e) { /* noop */ }
      }
    }
    pagesContainer.innerHTML = "";
    pages = [];
    visiblePages.clear();
    if (doc) {
      doc.destroy();
      doc = null;
    }
  }

  function dispose() {
    teardown();
  }

  return { load, goTo, nextPage, prevPage, setFit, zoomStep, getState, setOnStateChange, dispose };
})();
