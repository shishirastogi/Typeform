/**
 * TYPEFORM — Multi-Resolution Export Controller (export.js)
 * Handles SVG, PNG, and JPG exports at 1x, 2x, 3x, and 4x resolution multipliers.
 */

(function () {
  "use strict";

  class ExportController {
    constructor(getStateFn, getCsrfTokenFn, setStatusFn) {
      this.getState = getStateFn;
      this.getCsrfToken = getCsrfTokenFn;
      this.setStatus = setStatusFn;

      this.modal = document.getElementById("export-modal");
      this.format = "png";
      this.scale = 1;
      this.transparent = false;
      this.bgColor = "#F5F3EF";
      this.jpgQuality = 95;
      this.outlineText = false;

      this._bindEvents();
    }

    _bindEvents() {
      const openBtns = [
        document.getElementById("btn-open-export"),
        document.getElementById("btn-sidebar-export"),
      ];
      openBtns.forEach((btn) => {
        if (btn) btn.addEventListener("click", () => this.openModal());
      });

      const closeBtns = [
        document.getElementById("btn-close-export"),
        document.getElementById("btn-cancel-export"),
      ];
      closeBtns.forEach((btn) => {
        if (btn) btn.addEventListener("click", () => this.closeModal());
      });

      if (this.modal) {
        this.modal.addEventListener("click", (e) => {
          if (e.target === this.modal) this.closeModal();
        });
      }

      window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && this.modal && !this.modal.hidden) {
          this.closeModal();
        }
      });

      // Format buttons
      const fmtButtons = document.querySelectorAll("[data-export-format]");
      fmtButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
          fmtButtons.forEach((b) => b.classList.remove("is-active"));
          btn.classList.add("is-active");
          this.format = btn.getAttribute("data-export-format") || "png";
          this.updateModalUI();
        });
      });

      // Scale buttons
      const scaleButtons = document.querySelectorAll("[data-export-scale]");
      scaleButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
          scaleButtons.forEach((b) => b.classList.remove("is-active"));
          btn.classList.add("is-active");
          this.scale = parseInt(btn.getAttribute("data-export-scale"), 10) || 1;
          this.updateModalUI();
        });
      });

      // Background color & transparency
      const bgSwatch = document.getElementById("ctrl-export-bg-color");
      const bgHex = document.getElementById("ctrl-export-bg-color-hex");
      const transCheck = document.getElementById("ctrl-export-transparent");
      const jpgQual = document.getElementById("ctrl-export-jpg-quality");
      const jpgQualVal = document.getElementById("val-export-jpg-quality");
      const outlineCheck = document.getElementById("ctrl-export-outline-text");

      if (bgSwatch && bgHex) {
        bgSwatch.addEventListener("input", () => {
          this.bgColor = window.StudioControls.normalizeHex(bgSwatch.value);
          bgHex.value = this.bgColor;
          this.updateModalUI();
        });
        bgHex.addEventListener("change", () => {
          this.bgColor = window.StudioControls.normalizeHex(
            bgHex.value,
            this.bgColor
          );
          bgHex.value = this.bgColor;
          bgSwatch.value = this.bgColor;
          this.updateModalUI();
        });
      }

      if (transCheck) {
        transCheck.addEventListener("change", () => {
          this.transparent = transCheck.checked;
          this.updateModalUI();
        });
      }

      if (jpgQual) {
        jpgQual.addEventListener("input", () => {
          this.jpgQuality = parseInt(jpgQual.value, 10) || 95;
          if (jpgQualVal) jpgQualVal.textContent = `${this.jpgQuality}%`;
          this.updateModalUI();
        });
      }

      if (outlineCheck) {
        outlineCheck.addEventListener("change", () => {
          this.outlineText = outlineCheck.checked;
          this.updateModalUI();
        });
      }

      const downloadBtn = document.getElementById("btn-download-export");
      if (downloadBtn) {
        downloadBtn.addEventListener("click", () => this.executeDownload());
      }
    }

    openModal() {
      if (!this.modal) return;
      const st = this.getState();
      const s = st.settings || {};

      this.bgColor = window.StudioControls.normalizeHex(
        s.background_color || "#F5F3EF"
      );
      this.transparent = Boolean(s.transparent_bg);

      const bgSwatch = document.getElementById("ctrl-export-bg-color");
      const bgHex = document.getElementById("ctrl-export-bg-color-hex");
      const transCheck = document.getElementById("ctrl-export-transparent");
      if (bgSwatch) bgSwatch.value = this.bgColor;
      if (bgHex) bgHex.value = this.bgColor;
      if (transCheck) transCheck.checked = this.transparent;

      const errBanner = document.getElementById("export-error-msg");
      if (errBanner) errBanner.hidden = true;

      this.updateModalUI();
      this.modal.hidden = false;
    }

    closeModal() {
      if (this.modal) this.modal.hidden = true;
    }

    updateModalUI() {
      const st = this.getState();
      const s = st.settings || {};
      const layout = st.layout || {};

      const baseW = Number(s.canvas_width) || 900;
      const baseH = Number(s.canvas_height) || 1125;
      const outW = baseW * this.scale;
      const outH = baseH * this.scale;

      const transGroup = document.getElementById("export-transparent-group");
      const jpgGroup = document.getElementById("export-jpg-quality-group");
      const svgGroup = document.getElementById("export-svg-outline-group");

      if (this.format === "jpg") {
        if (transGroup) transGroup.hidden = true;
        if (jpgGroup) jpgGroup.hidden = false;
        if (svgGroup) svgGroup.hidden = true;
      } else if (this.format === "svg") {
        if (transGroup) transGroup.hidden = false;
        if (jpgGroup) jpgGroup.hidden = true;
        if (svgGroup) svgGroup.hidden = false;
      } else {
        if (transGroup) transGroup.hidden = false;
        if (jpgGroup) jpgGroup.hidden = true;
        if (svgGroup) svgGroup.hidden = true;
      }

      const dimsEl = document.getElementById("export-summary-dims");
      const fmtEl = document.getElementById("export-summary-format");
      const bgEl = document.getElementById("export-summary-bg");
      const boxesEl = document.getElementById("export-summary-boxes");

      if (dimsEl) {
        dimsEl.textContent = `${outW} × ${outH} px`;
      }
      if (fmtEl) {
        if (this.format === "svg") {
          fmtEl.textContent = `SVG · ${this.scale}× Vector (${
            this.outlineText ? "Path Outlines" : "Editable Text"
          })`;
        } else if (this.format === "jpg") {
          fmtEl.textContent = `JPG · ${this.scale}× Raster (Quality ${this.jpgQuality}%)`;
        } else {
          fmtEl.textContent = `PNG · ${this.scale}× Lossless Raster`;
        }
      }
      if (bgEl) {
        const isTrans = this.format !== "jpg" && this.transparent;
        bgEl.textContent = isTrans
          ? "Transparent Alpha"
          : `Solid (${this.bgColor})`;
      }
      if (boxesEl) {
        const count =
          layout.stats && layout.stats.box_count !== undefined
            ? layout.stats.box_count
            : (layout.boxes || []).length;
        boxesEl.textContent = `${count} placed rectangles`;
      }
    }

    async executeDownload() {
      const downloadBtn = document.getElementById("btn-download-export");
      const errBanner = document.getElementById("export-error-msg");
      if (errBanner) errBanner.hidden = true;

      if (downloadBtn) {
        downloadBtn.disabled = true;
        downloadBtn.textContent = "Rendering...";
      }
      this.setStatus("Exporting...");

      const st = this.getState();
      const payload = {
        settings: st.settings,
        export_format: this.format,
        export_scale: this.scale,
        export_transparent: this.format !== "jpg" && this.transparent,
        export_bg_color: this.bgColor,
        export_jpg_quality: this.jpgQuality,
        export_outline_text: this.outlineText,
      };

      try {
        const response = await fetch("/api/export", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": this.getCsrfToken(),
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          let errMsg = `Export failed (${response.status})`;
          try {
            const errJson = await response.json();
            if (errJson && errJson.error) errMsg = errJson.error;
          } catch (_) {}
          throw new Error(errMsg);
        }

        const blob = await response.blob();
        const baseW = Number(st.settings.canvas_width) || 900;
        const baseH = Number(st.settings.canvas_height) || 1125;
        const outW = baseW * this.scale;
        const outH = baseH * this.scale;
        const filename = `typeform-${outW}x${outH}-${this.scale}x.${this.format}`;

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 5000);

        this.setStatus(`Exported ${filename}`);
        this.closeModal();
      } catch (err) {
        if (errBanner) {
          errBanner.textContent = err.message || "Failed to generate export.";
          errBanner.hidden = false;
        }
        this.setStatus("Export Error");
      } finally {
        if (downloadBtn) {
          downloadBtn.disabled = false;
          downloadBtn.textContent = "Download File";
        }
      }
    }
  }

  window.ExportController = ExportController;
})();
