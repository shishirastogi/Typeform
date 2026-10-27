/**
 * TYPEFORM — Sidebar Controls & Palette Manager (controls.js)
 * Binds all input, mask, typography, layout, and color controls.
 */

(function () {
  "use strict";

  const PALETTE_PRESETS = {
    editorial: {
      palette: ["#171717", "#D9381E", "#DDD7CD", "#3D3A36", "#FFFFFF"],
      weights: [42, 18, 20, 12, 8],
    },
    mono: {
      palette: ["#171717", "#3A3835", "#EAE6DF"],
      weights: [55, 25, 20],
    },
    swiss: {
      palette: ["#171717", "#E02B1D", "#F5F3EF"],
      weights: [50, 30, 20],
    },
    archive: {
      palette: ["#1F1E1C", "#59544F", "#A69F95", "#D8D2C7", "#F2EFE9"],
      weights: [30, 25, 20, 15, 10],
    },
  };

  function normalizeHex(val, fallback = "#171717") {
    if (!val || typeof val !== "string") return fallback;
    let clean = val.trim();
    if (!clean.startsWith("#")) clean = "#" + clean;
    if (/^#[0-9A-Fa-f]{3}$/.test(clean)) {
      return (
        "#" +
        clean[1] +
        clean[1] +
        clean[2] +
        clean[2] +
        clean[3] +
        clean[3]
      ).toUpperCase();
    }
    if (/^#[0-9A-Fa-f]{6}$/.test(clean)) {
      return clean.toUpperCase();
    }
    return fallback;
  }

  function updateTextStats(text) {
    const statsEl = document.getElementById("text-stats");
    if (!statsEl) return;
    const raw = text || "";
    const chars = raw.length;
    const trimmed = raw.trim();
    const words = trimmed ? trimmed.split(/\s+/).length : 0;
    statsEl.textContent = `${words} WORDS · ${chars} CHARS`;
  }

  function updateReadoutLabels(settings) {
    const map = {
      "val-threshold": `${settings.threshold}`,
      "val-contrast": `${Number(settings.contrast).toFixed(2)}`,
      "val-min-overlap": `${Math.round(Number(settings.min_overlap) * 100)}%`,
      "val-image-scale": `${Number(settings.image_scale).toFixed(2)}×`,
      "val-image-offset-x": `${Math.round(Number(settings.image_offset_x))}%`,
      "val-image-offset-y": `${Math.round(Number(settings.image_offset_y))}%`,
      "val-letter-spacing": `${Number(settings.letter_spacing).toFixed(1)}px`,
      "val-line-height": `${Number(settings.line_height).toFixed(2)}`,
      "val-box-width": `${settings.box_width}px`,
      "val-box-height": `${settings.box_height}px`,
      "val-h-spacing": `${settings.h_spacing}px`,
      "val-v-spacing": `${settings.v_spacing}px`,
      "val-row-offset": `${settings.row_offset}px`,
      "val-irregular-edge": `${settings.irregular_edge}%`,
      "val-box-density": `${Math.round(Number(settings.box_density) * 100)}%`,
      "val-box-border-width": `${settings.box_border_width}px`,
    };
    Object.keys(map).forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = map[id];
    });
  }

  function renderPaletteEditor(settings, onPaletteChange) {
    const container = document.getElementById("palette-list");
    if (!container) return;
    container.innerHTML = "";

    const palette = Array.isArray(settings.palette)
      ? settings.palette
      : ["#171717", "#D9381E", "#DDD7CD"];
    const weights = Array.isArray(settings.palette_weights)
      ? settings.palette_weights
      : palette.map(() => 20);

    palette.forEach((hexColor, idx) => {
      const weightVal = weights[idx] !== undefined ? weights[idx] : 20;
      const row = document.createElement("div");
      row.className = "palette-item";

      const swatch = document.createElement("input");
      swatch.type = "color";
      swatch.className = "color-swatch-input";
      swatch.value = normalizeHex(hexColor);
      swatch.title = `Palette color ${idx + 1}`;

      const hexIn = document.createElement("input");
      hexIn.type = "text";
      hexIn.className = "text-input hex-input";
      hexIn.maxLength = 7;
      hexIn.value = normalizeHex(hexColor);

      const weightSlider = document.createElement("input");
      weightSlider.type = "range";
      weightSlider.className = "range-input";
      weightSlider.min = "1";
      weightSlider.max = "100";
      weightSlider.value = String(weightVal);
      weightSlider.title = "Color assignment frequency weight";

      const weightLabel = document.createElement("span");
      weightLabel.className = "palette-weight-val";
      weightLabel.textContent = `${weightVal}%`;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "text-btn text-btn-xs";
      removeBtn.textContent = "×";
      removeBtn.title = "Remove color from palette";
      removeBtn.disabled = palette.length <= 1;

      const handleSwatchChange = () => {
        const clean = normalizeHex(swatch.value);
        hexIn.value = clean;
        settings.palette[idx] = clean;
        if (idx === 0) {
          settings.box_bg_color = clean;
          const bgSw = document.getElementById("ctrl-box-bg-color");
          const bgHx = document.getElementById("ctrl-box-bg-color-hex");
          if (bgSw) bgSw.value = clean;
          if (bgHx) bgHx.value = clean;
        }
        onPaletteChange();
      };
      swatch.addEventListener("input", handleSwatchChange);
      swatch.addEventListener("change", handleSwatchChange);

      hexIn.addEventListener("input", () => {
        const raw = (hexIn.value || "").trim();
        if (/^#?[0-9A-Fa-f]{6}$/.test(raw)) {
          const clean = normalizeHex(raw, settings.palette[idx]);
          swatch.value = clean;
          settings.palette[idx] = clean;
          if (idx === 0) {
            settings.box_bg_color = clean;
            const bgSw = document.getElementById("ctrl-box-bg-color");
            const bgHx = document.getElementById("ctrl-box-bg-color-hex");
            if (bgSw) bgSw.value = clean;
            if (bgHx) bgHx.value = clean;
          }
          onPaletteChange();
        }
      });

      hexIn.addEventListener("change", () => {
        const clean = normalizeHex(hexIn.value, settings.palette[idx]);
        hexIn.value = clean;
        swatch.value = clean;
        settings.palette[idx] = clean;
        if (idx === 0) {
          settings.box_bg_color = clean;
          const bgSw = document.getElementById("ctrl-box-bg-color");
          const bgHx = document.getElementById("ctrl-box-bg-color-hex");
          if (bgSw) bgSw.value = clean;
          if (bgHx) bgHx.value = clean;
        }
        onPaletteChange();
      });

      const handleWeightChange = () => {
        const w = parseInt(weightSlider.value, 10) || 20;
        weightLabel.textContent = `${w}%`;
        settings.palette_weights[idx] = w;
        onPaletteChange();
      };
      weightSlider.addEventListener("input", handleWeightChange);
      weightSlider.addEventListener("change", handleWeightChange);

      removeBtn.addEventListener("click", () => {
        if (settings.palette.length <= 1) return;
        settings.palette.splice(idx, 1);
        settings.palette_weights.splice(idx, 1);
        renderPaletteEditor(settings, onPaletteChange);
        onPaletteChange();
      });

      row.appendChild(swatch);
      row.appendChild(hexIn);
      row.appendChild(weightSlider);
      row.appendChild(weightLabel);
      row.appendChild(removeBtn);
      container.appendChild(row);
    });
  }

  function updateUploadInfoUI(imageMeta, imageId) {
    const infoBar = document.getElementById("upload-info-bar");
    const fnameEl = document.getElementById("upload-filename");
    const dimsEl = document.getElementById("upload-dimensions");
    const shapeSelect = document.getElementById("ctrl-builtin-shape");
    const optUploaded = document.getElementById("opt-uploaded-shape");

    const isUploaded =
      imageMeta &&
      imageId &&
      !String(imageId).startsWith("builtin:") &&
      imageId !== "none";

    if (isUploaded) {
      if (infoBar) infoBar.hidden = false;
      if (fnameEl) fnameEl.textContent = imageMeta.filename || "uploaded-image";
      if (dimsEl) {
        const kb = Math.max(1, Math.round((imageMeta.size_bytes || 0) / 1024));
        dimsEl.textContent = `${imageMeta.width}×${imageMeta.height} px · ${
          imageMeta.format || "IMG"
        } · ${kb} KB`;
      }
      if (optUploaded) {
        optUploaded.disabled = false;
        optUploaded.textContent = `Uploaded: ${imageMeta.filename || "Image"}`;
      }
      if (shapeSelect) {
        shapeSelect.value = "uploaded";
      }
    } else {
      if (infoBar) infoBar.hidden = true;
      if (optUploaded) {
        optUploaded.disabled = true;
        optUploaded.textContent = "Uploaded Image";
      }
      if (shapeSelect && String(imageId).startsWith("builtin:")) {
        shapeSelect.value = imageId;
      }
    }
  }

  function populateControlsFromSettings(settings, imageMeta, onPaletteChange) {
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (!el || val === undefined || val === null) return;
      if (el.type === "checkbox") {
        el.checked = Boolean(val);
      } else {
        el.value = String(val);
      }
    };

    setVal("ctrl-text", settings.text);
    setVal("ctrl-repeat-text", settings.repeat_text);
    setVal("ctrl-distribution-mode", settings.distribution_mode);
    setVal("ctrl-custom-phrase", settings.custom_phrase);

    setVal("ctrl-fill-mode", settings.fill_mode);
    setVal("ctrl-canvas-width", settings.canvas_width);
    setVal("ctrl-canvas-height", settings.canvas_height);
    setVal("ctrl-fit-mode", settings.fit_mode);
    setVal("ctrl-fg-mode", settings.fg_mode);
    setVal("ctrl-threshold", settings.threshold);
    setVal("ctrl-contrast", settings.contrast);
    setVal("ctrl-min-overlap", settings.min_overlap);
    setVal("ctrl-invert-mask", settings.invert_mask);
    setVal("ctrl-image-scale", settings.image_scale);
    setVal("ctrl-image-offset-x", settings.image_offset_x);
    setVal("ctrl-image-offset-y", settings.image_offset_y);
    setVal("ctrl-crop-left", settings.crop_left);
    setVal("ctrl-crop-top", settings.crop_top);
    setVal("ctrl-crop-right", settings.crop_right);
    setVal("ctrl-crop-bottom", settings.crop_bottom);

    setVal("ctrl-font-family", settings.font_family);
    setVal("ctrl-font-size", settings.font_size);
    setVal("ctrl-font-weight", settings.font_weight);
    setVal("ctrl-font-style", settings.font_style);
    setVal("ctrl-text-case", settings.text_case);
    setVal("ctrl-letter-spacing", settings.letter_spacing);
    setVal("ctrl-line-height", settings.line_height);
    setVal("ctrl-text-align", settings.text_align);
    setVal("ctrl-box-h-align", settings.box_h_align);
    setVal("ctrl-box-v-align", settings.box_v_align);

    setVal("ctrl-layout-mode", settings.layout_mode);
    setVal("ctrl-box-width", settings.box_width);
    setVal("ctrl-box-height", settings.box_height);
    setVal("ctrl-min-box-width", settings.min_box_width);
    setVal("ctrl-max-box-width", settings.max_box_width);
    setVal("ctrl-h-spacing", settings.h_spacing);
    setVal("ctrl-v-spacing", settings.v_spacing);
    setVal("ctrl-padding-x", settings.padding_x);
    setVal("ctrl-padding-y", settings.padding_y);
    setVal("ctrl-box-align", settings.box_align);
    setVal("ctrl-word-wrap", settings.word_wrap);
    setVal("ctrl-row-offset", settings.row_offset);
    setVal("ctrl-irregular-edge", settings.irregular_edge);
    setVal("ctrl-box-density", settings.box_density);
    setVal("ctrl-box-border-width", settings.box_border_width);

    setVal("ctrl-color-mode", settings.color_mode);
    setVal("ctrl-apply-to", settings.apply_to);
    setVal("ctrl-background-color", normalizeHex(settings.background_color, "#F5F3EF"));
    setVal("ctrl-background-color-hex", normalizeHex(settings.background_color, "#F5F3EF"));
    setVal("ctrl-transparent-bg", settings.transparent_bg);
    setVal("ctrl-primary-text-color", normalizeHex(settings.primary_text_color, "#171717"));
    setVal("ctrl-primary-text-color-hex", normalizeHex(settings.primary_text_color, "#171717"));
    setVal("ctrl-secondary-text-color", normalizeHex(settings.secondary_text_color, "#F5F3EF"));
    setVal("ctrl-secondary-text-color-hex", normalizeHex(settings.secondary_text_color, "#F5F3EF"));
    setVal("ctrl-box-bg-color", normalizeHex(settings.box_bg_color, "#171717"));
    setVal("ctrl-box-bg-color-hex", normalizeHex(settings.box_bg_color, "#171717"));
    setVal("ctrl-box-border-color", normalizeHex(settings.box_border_color, "#171717"));
    setVal("ctrl-box-border-color-hex", normalizeHex(settings.box_border_color, "#171717"));
    setVal("ctrl-seed", settings.seed);

    updateTextStats(settings.text);
    updateReadoutLabels(settings);
    updateUploadInfoUI(imageMeta, settings.image_id);
    renderPaletteEditor(settings, onPaletteChange);
  }

  window.StudioControls = {
    PALETTE_PRESETS,
    normalizeHex,
    updateTextStats,
    updateReadoutLabels,
    renderPaletteEditor,
    updateUploadInfoUI,
    populateControlsFromSettings,
  };
})();
