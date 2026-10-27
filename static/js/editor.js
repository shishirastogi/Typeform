/**
 * TYPEFORM — Main Studio Editor Application Controller (editor.js)
 * Coordinates state persistence, debounced mask & layout API requests,
 * image upload/replacement, live canvas rendering, and project reset/save.
 */

(function () {
  "use strict";

  const LOCAL_STORAGE_KEY = "typeform_studio_settings_v1";

  const state = {
    settings: {},
    imageMeta: null,
    projectId: "",
    layout: null,
    maskPreviewUrl: null,
    sourcePreviewUrl: null,
    isGenerating: false,
  };

  let preview = null;
  let exportCtrl = null;
  let generateTimer = null;
  let maskTimer = null;

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") || "" : "";
  }

  function setStatus(text) {
    const el = document.getElementById("status-indicator");
    if (el) el.textContent = text;
  }

  function saveToLocalStorage() {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(state.settings));
    } catch (_) {}
  }

  function updateCanvasMetricsBar() {
    const metricsEl = document.getElementById("canvas-metrics");
    if (!metricsEl) return;
    const cw = state.settings.canvas_width || 900;
    const ch = state.settings.canvas_height || 1125;
    const count =
      state.layout && state.layout.stats
        ? state.layout.stats.box_count
        : state.layout && state.layout.boxes
        ? state.layout.boxes.length
        : 0;
    const cov =
      state.layout && state.layout.stats
        ? state.layout.stats.mask_coverage
        : "—";
    metricsEl.textContent = `${count} BOXES · ${cw}×${ch} · ${cov}% MASK · SEED ${state.settings.seed}`;
  }

  function updateMaskThumb(maskDataUrl, coveragePct) {
    const thumbImg = document.getElementById("mask-thumb-img");
    if (thumbImg && maskDataUrl) {
      thumbImg.src = maskDataUrl;
    }
    const covEl = document.getElementById("mask-coverage-readout");
    if (covEl && coveragePct !== undefined && coveragePct !== null) {
      covEl.textContent = `${coveragePct}% ACTIVE`;
    }
  }

  function scheduleGenerate(delayMs = 140) {
    if (generateTimer) clearTimeout(generateTimer);
    generateTimer = setTimeout(() => {
      generateTimer = null;
      requestGenerateArtwork();
    }, delayMs);
  }

  function scheduleMaskPreview(delayMs = 90) {
    if (maskTimer) clearTimeout(maskTimer);
    maskTimer = setTimeout(() => {
      maskTimer = null;
      requestMaskProcess();
    }, delayMs);
  }

  async function requestMaskProcess() {
    try {
      const response = await fetch("/api/process-mask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": getCsrfToken(),
        },
        body: JSON.stringify(state.settings),
      });
      if (!response.ok) return;
      const data = await response.json();
      if (data.mask_preview) {
        state.maskPreviewUrl = data.mask_preview;
        state.sourcePreviewUrl = data.source_preview || state.sourcePreviewUrl;
        updateMaskThumb(data.mask_preview, data.coverage_ratio);
        if (preview) {
          preview.updateImages(state.maskPreviewUrl, state.sourcePreviewUrl);
        }
      }
    } catch (_) {}
  }

  function hexToRgb(hex) {
    let h = String(hex || "#171717").replace("#", "").trim();
    if (h.length === 3) {
      h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    }
    const num = parseInt(h, 16);
    if (isNaN(num)) return [23, 23, 23];
    return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
  }

  function rgbToHex(r, g, b) {
    const clamp = (v) => Math.max(0, Math.min(255, Math.round(v)));
    return (
      "#" +
      [clamp(r), clamp(g), clamp(b)]
        .map((v) => v.toString(16).padStart(2, "0"))
        .join("")
        .toUpperCase()
    );
  }

  function relLum(hex) {
    const [r, g, b] = hexToRgb(hex);
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0;
  }

  function colorDist(h1, h2) {
    const [r1, g1, b1] = hexToRgb(h1);
    const [r2, g2, b2] = hexToRgb(h2);
    return Math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2);
  }

  function chooseTextColorClient(bgHex, primaryText, secondaryText, idx) {
    const bgLum = relLum(bgHex);
    const distP = colorDist(bgHex, primaryText);
    const distS = colorDist(bgHex, secondaryText);
    const pNorm = String(primaryText || "#171717").toUpperCase();
    const sNorm = String(secondaryText || "#F5F3EF").toUpperCase();
    const pCustom = pNorm !== "#171717";
    const sCustom = sNorm !== "#F5F3EF";

    if (pCustom && sCustom) {
      if (idx % 2 === 0 && distP >= 35) return primaryText;
      if (distS >= 35) return secondaryText;
      return distP >= distS ? primaryText : secondaryText;
    }
    if (pCustom) {
      if (distP >= 40) return primaryText;
      return distS >= 40 ? secondaryText : bgLum < 0.5 ? "#F5F3EF" : "#171717";
    }
    if (sCustom) {
      if (bgLum < 0.55 && distS >= 40) return secondaryText;
      if (distP >= 45) return primaryText;
      return secondaryText;
    }
    if (bgLum < 0.48) {
      return distS >= 45 ? secondaryText : "#F5F3EF";
    }
    return distP >= 45 ? primaryText : "#171717";
  }

  function interpolatePaletteClient(palette, t) {
    if (!palette || !palette.length) return "#171717";
    if (palette.length === 1) return palette[0];
    const clamped = Math.max(0, Math.min(1, t));
    const scaled = clamped * (palette.length - 1);
    const idx = Math.floor(scaled);
    const frac = scaled - idx;
    if (idx >= palette.length - 1) return palette[palette.length - 1];
    const [r1, g1, b1] = hexToRgb(palette[idx]);
    const [r2, g2, b2] = hexToRgb(palette[idx + 1]);
    return rgbToHex(
      r1 + (r2 - r1) * frac,
      g1 + (g2 - g1) * frac,
      b1 + (b2 - b1) * frac
    );
  }

  function applyColorsClientSideImmediate() {
    if (!state.layout || !Array.isArray(state.layout.boxes)) return;
    const s = state.settings;
    state.layout.background_color = s.background_color || "#F5F3EF";
    state.layout.transparent_bg = Boolean(s.transparent_bg);

    const colorMode = s.color_mode || "random";
    const applyTo = s.apply_to || "box_and_text";
    const primaryText = s.primary_text_color || "#171717";
    const secondaryText = s.secondary_text_color || "#F5F3EF";
    const boxBg = s.box_bg_color || "#171717";
    const borderColor = s.box_border_color || "#171717";
    const borderWidth = Number(s.box_border_width) || 0;
    const palette =
      Array.isArray(s.palette) && s.palette.length
        ? s.palette
        : ["#171717", "#D9381E", "#DDD7CD"];
    const weights =
      Array.isArray(s.palette_weights) && s.palette_weights.length
        ? s.palette_weights
        : palette.map(() => 20);
    const cw = Number(state.layout.canvas_width) || 900;
    const ch = Number(state.layout.canvas_height) || 1125;
    const seed = Number(s.seed) || 42;
    const grayRamp = [
      "#171717",
      "#2E2E2E",
      "#4A4845",
      "#77736F",
      "#C8C4BC",
      "#EAE6DF",
    ];

    const totalWeight = weights.reduce((acc, w) => acc + (Number(w) || 1), 0);

    state.layout.boxes.forEach((box, idx) => {
      // Deterministic pseudo-random number in [0, 1) per box + seed
      const hash = Math.sin((idx + 1) * 12.9898 + (seed + 7919) * 78.233) * 43758.5453;
      const rand01 = hash - Math.floor(hash);

      let chosen = boxBg;
      if (colorMode === "monochrome") {
        chosen = boxBg;
      } else if (colorMode === "two_color") {
        const w0 = Number(weights[0]) || 50;
        const w1 = Number(weights[1]) || 50;
        chosen = rand01 * (w0 + w1) < w0 ? boxBg : secondaryText;
      } else if (colorMode === "custom_palette") {
        chosen = palette[idx % palette.length];
      } else if (colorMode === "grayscale") {
        chosen = grayRamp[Math.floor(rand01 * grayRamp.length) % grayRamp.length];
      } else if (colorMode === "gradient") {
        const nx = (box.x + box.w * 0.5) / Math.max(1, cw);
        const ny = (box.y + box.h * 0.5) / Math.max(1, ch);
        chosen = interpolatePaletteClient(palette, 0.45 * nx + 0.55 * ny);
      } else {
        let target = rand01 * totalWeight;
        chosen = palette[palette.length - 1];
        for (let i = 0; i < palette.length; i++) {
          target -= Number(weights[i]) || 1;
          if (target <= 0) {
            chosen = palette[i];
            break;
          }
        }
      }

      if (applyTo === "box_only") {
        box.fill = chosen;
        box.text_color = primaryText;
      } else if (applyTo === "text_only") {
        box.fill = "none";
        box.text_color = chosen;
      } else {
        box.fill = chosen;
        box.text_color = chooseTextColorClient(
          chosen,
          primaryText,
          secondaryText,
          idx
        );
      }
      box.border_color = borderColor;
      box.border_width = borderWidth;
    });

    if (preview) {
      preview.scheduleRender();
    }
  }

  async function requestGenerateArtwork(autoFit = false) {
    setStatus("Generating...");
    saveToLocalStorage();

    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": getCsrfToken(),
        },
        body: JSON.stringify(state.settings),
      });

      if (!response.ok) {
        let msg = "Generation Error";
        try {
          const err = await response.json();
          if (err && err.error) msg = err.error;
        } catch (_) {}
        setStatus(msg);
        return;
      }

      const data = await response.json();
      if (data.layout) {
        state.layout = data.layout;
        if (preview) {
          preview.setLayout(data.layout, autoFit);
        }
      }
      if (data.mask_preview) {
        state.maskPreviewUrl = data.mask_preview;
        const cov =
          data.layout && data.layout.stats
            ? data.layout.stats.mask_coverage
            : undefined;
        updateMaskThumb(data.mask_preview, cov);
        if (preview) {
          preview.updateImages(state.maskPreviewUrl, state.sourcePreviewUrl);
        }
      }
      updateCanvasMetricsBar();
      setStatus("Ready");
    } catch (err) {
      setStatus("Network Error");
    }
  }

  async function handleFileUpload(file) {
    if (!file) return;
    const allowedTypes = [
      "image/png",
      "image/jpeg",
      "image/webp",
    ];
    const ext = (file.name.split(".").pop() || "").toLowerCase();
    if (
      !allowedTypes.includes(file.type) &&
      !["png", "jpg", "jpeg", "webp"].includes(ext)
    ) {
      setStatus("Unsupported file type (use PNG, JPG, WebP)");
      return;
    }

    setStatus("Uploading image...");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        headers: {
          "X-CSRF-Token": getCsrfToken(),
        },
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        setStatus(data.error || "Upload failed");
        return;
      }

      state.imageMeta = {
        image_id: data.image_id,
        filename: data.filename,
        width: data.width,
        height: data.height,
        format: data.format,
        size_bytes: data.size_bytes,
        has_alpha: data.has_alpha,
      };
      state.settings.image_id = data.image_id;
      state.settings.fill_mode = "silhouette";

      const fillSelect = document.getElementById("ctrl-fill-mode");
      if (fillSelect) fillSelect.value = "silhouette";

      window.StudioControls.updateUploadInfoUI(
        state.imageMeta,
        state.settings.image_id
      );

      if (data.mask_preview) {
        state.maskPreviewUrl = data.mask_preview;
        state.sourcePreviewUrl = data.source_preview || null;
        updateMaskThumb(data.mask_preview, data.coverage_ratio);
        if (preview) {
          preview.updateImages(state.maskPreviewUrl, state.sourcePreviewUrl);
        }
      }

      await requestGenerateArtwork(false);
    } catch (err) {
      setStatus("Upload failed");
    }
  }

  async function handleRemoveImage() {
    const currentId = state.settings.image_id;
    setStatus("Removing image...");
    try {
      const response = await fetch("/api/upload/remove", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": getCsrfToken(),
        },
        body: JSON.stringify({
          image_id: currentId,
          fallback_id: "builtin:portrait",
        }),
      });
      if (response.ok) {
        state.imageMeta = null;
        state.settings.image_id = "builtin:portrait";
        window.StudioControls.updateUploadInfoUI(
          null,
          state.settings.image_id
        );
        scheduleMaskPreview(10);
        scheduleGenerate(20);
      }
    } catch (_) {
      setStatus("Error removing image");
    }
  }

  async function handleSaveProject() {
    setStatus("Saving project...");
    saveToLocalStorage();
    try {
      const response = await fetch("/api/project/save", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": getCsrfToken(),
        },
        body: JSON.stringify({ settings: state.settings }),
      });
      if (response.ok) {
        const data = await response.json();
        if (data.settings) Object.assign(state.settings, data.settings);
        setStatus("Project Saved");
      } else {
        setStatus("Save Failed");
      }
    } catch (_) {
      setStatus("Save Error");
    }
  }

  function onPaletteUpdated() {
    applyColorsClientSideImmediate();
    scheduleGenerate(80);
  }

  async function handleResetProject() {
    setStatus("Resetting...");
    try {
      localStorage.removeItem(LOCAL_STORAGE_KEY);
    } catch (_) {}

    try {
      const response = await fetch("/api/project/reset", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": getCsrfToken(),
        },
        body: JSON.stringify({}),
      });
      if (response.ok) {
        const data = await response.json();
        if (data.settings) {
          Object.keys(state.settings).forEach((k) => delete state.settings[k]);
          Object.assign(state.settings, data.settings);
        }
        state.imageMeta = null;
        window.StudioControls.populateControlsFromSettings(
          state.settings,
          state.imageMeta,
          onPaletteUpdated
        );
        scheduleMaskPreview(10);
        await requestGenerateArtwork(true);
        setStatus("Project Reset");
      }
    } catch (_) {
      setStatus("Reset Failed");
    }
  }

  function bindAllControls() {
    const s = state.settings;
    const C = window.StudioControls;

    // Collapsible sections
    document.querySelectorAll("[data-toggle-section]").forEach((hdr) => {
      hdr.addEventListener("click", () => {
        const secId = hdr.getAttribute("data-toggle-section");
        const sec = document.getElementById(secId);
        if (!sec) return;
        const collapsed = sec.classList.toggle("is-collapsed");
        const lbl = hdr.querySelector(".section-toggle-label");
        if (lbl) lbl.textContent = collapsed ? "Expand" : "Collapse";
      });
    });

    // Helper for binding inputs
    const bindInput = (id, key, parser, isMaskParam = false, delay = 140) => {
      const el = document.getElementById(id);
      if (!el) return;
      const evtName =
        el.type === "range" || el.tagName === "TEXTAREA" || el.type === "text"
          ? "input"
          : "change";
      el.addEventListener(evtName, () => {
        const val =
          el.type === "checkbox" ? el.checked : parser ? parser(el.value) : el.value;
        state.settings[key] = val;
        C.updateReadoutLabels(state.settings);
        if (key === "text") {
          C.updateTextStats(val);
        }
        if (isMaskParam) {
          scheduleMaskPreview(70);
        }
        scheduleGenerate(delay);
      });
    };

    // 01 / Text controls
    bindInput("ctrl-text", "text", String, false, 220);
    bindInput("ctrl-repeat-text", "repeat_text", Boolean, false, 80);
    bindInput("ctrl-distribution-mode", "distribution_mode", String, false, 80);
    bindInput("ctrl-custom-phrase", "custom_phrase", String, false, 180);

    const genBtn = document.getElementById("btn-generate");
    if (genBtn) {
      genBtn.addEventListener("click", () => requestGenerateArtwork(false));
    }

    // 02 / Mask & Silhouette controls
    bindInput("ctrl-fill-mode", "fill_mode", String, true, 80);
    bindInput("ctrl-canvas-width", "canvas_width", (v) => parseInt(v, 10) || 900, true, 160);
    bindInput("ctrl-canvas-height", "canvas_height", (v) => parseInt(v, 10) || 1125, true, 160);
    bindInput("ctrl-fit-mode", "fit_mode", String, true, 80);
    bindInput("ctrl-fg-mode", "fg_mode", String, true, 80);
    bindInput("ctrl-threshold", "threshold", (v) => parseInt(v, 10) || 0, true, 100);
    bindInput("ctrl-contrast", "contrast", (v) => parseFloat(v) || 1.0, true, 100);
    bindInput("ctrl-min-overlap", "min_overlap", (v) => parseFloat(v) || 0.55, false, 100);
    bindInput("ctrl-invert-mask", "invert_mask", Boolean, true, 80);
    bindInput("ctrl-image-scale", "image_scale", (v) => parseFloat(v) || 1.0, true, 100);
    bindInput("ctrl-image-offset-x", "image_offset_x", (v) => parseFloat(v) || 0, true, 100);
    bindInput("ctrl-image-offset-y", "image_offset_y", (v) => parseFloat(v) || 0, true, 100);
    bindInput("ctrl-crop-left", "crop_left", (v) => parseFloat(v) || 0, true, 120);
    bindInput("ctrl-crop-top", "crop_top", (v) => parseFloat(v) || 0, true, 120);
    bindInput("ctrl-crop-right", "crop_right", (v) => parseFloat(v) || 0, true, 120);
    bindInput("ctrl-crop-bottom", "crop_bottom", (v) => parseFloat(v) || 0, true, 120);

    // Built-in reference shape selector
    const builtinSelect = document.getElementById("ctrl-builtin-shape");
    if (builtinSelect) {
      builtinSelect.addEventListener("change", () => {
        const val = builtinSelect.value;
        if (val === "uploaded" && state.imageMeta) {
          state.settings.image_id = state.imageMeta.image_id;
        } else if (val.startsWith("builtin:")) {
          state.settings.image_id = val;
        }
        scheduleMaskPreview(30);
        scheduleGenerate(60);
      });
    }

    // Aspect ratio quick buttons
    document.querySelectorAll("[data-aspect]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const parts = (btn.getAttribute("data-aspect") || "900x1125").split("x");
        const w = parseInt(parts[0], 10) || 900;
        const h = parseInt(parts[1], 10) || 1125;
        state.settings.canvas_width = w;
        state.settings.canvas_height = h;
        const wIn = document.getElementById("ctrl-canvas-width");
        const hIn = document.getElementById("ctrl-canvas-height");
        if (wIn) wIn.value = String(w);
        if (hIn) hIn.value = String(h);
        scheduleMaskPreview(20);
        requestGenerateArtwork(true);
      });
    });

    // Upload dropzone & file input
    const dropzone = document.getElementById("upload-dropzone");
    const fileInput = document.getElementById("ctrl-file-input");
    const replaceBtn = document.getElementById("btn-replace-image");
    const removeBtn = document.getElementById("btn-remove-image");

    if (dropzone && fileInput) {
      dropzone.addEventListener("click", () => fileInput.click());
      dropzone.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          fileInput.click();
        }
      });
      dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("is-dragover");
      });
      dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("is-dragover");
      });
      dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("is-dragover");
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleFileUpload(e.dataTransfer.files[0]);
        }
      });
      fileInput.addEventListener("change", () => {
        if (fileInput.files && fileInput.files[0]) {
          handleFileUpload(fileInput.files[0]);
          fileInput.value = "";
        }
      });
    }
    if (replaceBtn && fileInput) {
      replaceBtn.addEventListener("click", () => fileInput.click());
    }
    if (removeBtn) {
      removeBtn.addEventListener("click", () => handleRemoveImage());
    }

    // 03 / Typography controls
    bindInput("ctrl-font-family", "font_family", String, false, 80);
    bindInput("ctrl-font-size", "font_size", (v) => parseInt(v, 10) || 15, false, 100);
    bindInput("ctrl-font-weight", "font_weight", String, false, 80);
    bindInput("ctrl-font-style", "font_style", String, false, 80);
    bindInput("ctrl-text-case", "text_case", String, false, 80);
    bindInput("ctrl-letter-spacing", "letter_spacing", (v) => parseFloat(v) || 0, false, 100);
    bindInput("ctrl-line-height", "line_height", (v) => parseFloat(v) || 1.15, false, 100);
    bindInput("ctrl-text-align", "text_align", String, false, 80);
    bindInput("ctrl-box-h-align", "box_h_align", String, false, 80);
    bindInput("ctrl-box-v-align", "box_v_align", String, false, 80);

    // 04 / Box & Layout controls
    bindInput("ctrl-layout-mode", "layout_mode", String, false, 80);
    bindInput("ctrl-box-width", "box_width", (v) => parseInt(v, 10) || 66, false, 90);
    bindInput("ctrl-box-height", "box_height", (v) => parseInt(v, 10) || 26, false, 90);
    bindInput("ctrl-min-box-width", "min_box_width", (v) => parseInt(v, 10) || 28, false, 120);
    bindInput("ctrl-max-box-width", "max_box_width", (v) => parseInt(v, 10) || 210, false, 120);
    bindInput("ctrl-h-spacing", "h_spacing", (v) => parseInt(v, 10) || 4, false, 90);
    bindInput("ctrl-v-spacing", "v_spacing", (v) => parseInt(v, 10) || 4, false, 90);
    bindInput("ctrl-padding-x", "padding_x", (v) => parseInt(v, 10) || 6, false, 100);
    bindInput("ctrl-padding-y", "padding_y", (v) => parseInt(v, 10) || 4, false, 100);
    bindInput("ctrl-box-align", "box_align", String, false, 80);
    bindInput("ctrl-word-wrap", "word_wrap", String, false, 80);
    bindInput("ctrl-row-offset", "row_offset", (v) => parseInt(v, 10) || 0, false, 90);
    bindInput("ctrl-irregular-edge", "irregular_edge", (v) => parseInt(v, 10) || 0, false, 90);
    bindInput("ctrl-box-density", "box_density", (v) => parseFloat(v) || 1.0, false, 90);
    const borderWidthEl = document.getElementById("ctrl-box-border-width");
    if (borderWidthEl) {
      const onBorderW = () => {
        state.settings.box_border_width = parseInt(borderWidthEl.value, 10) || 0;
        C.updateReadoutLabels(state.settings);
        applyColorsClientSideImmediate();
        scheduleGenerate(80);
      };
      borderWidthEl.addEventListener("input", onBorderW);
      borderWidthEl.addEventListener("change", onBorderW);
    }

    // 05 / Color controls
    const colorModeEl = document.getElementById("ctrl-color-mode");
    if (colorModeEl) {
      colorModeEl.addEventListener("change", () => {
        state.settings.color_mode = colorModeEl.value;
        applyColorsClientSideImmediate();
        scheduleGenerate(60);
      });
    }

    const applyToEl = document.getElementById("ctrl-apply-to");
    if (applyToEl) {
      applyToEl.addEventListener("change", () => {
        state.settings.apply_to = applyToEl.value;
        applyColorsClientSideImmediate();
        scheduleGenerate(60);
      });
    }

    bindInput("ctrl-seed", "seed", (v) => parseInt(v, 10) || 0, false, 80);

    const transBgEl = document.getElementById("ctrl-transparent-bg");
    if (transBgEl) {
      transBgEl.addEventListener("change", () => {
        state.settings.transparent_bg = transBgEl.checked;
        applyColorsClientSideImmediate();
        scheduleGenerate(120);
      });
    }

    const bindColorPair = (swatchId, hexId, settingKey) => {
      const swatch = document.getElementById(swatchId);
      const hex = document.getElementById(hexId);
      if (!swatch || !hex) return;

      const applyColorValue = (clean, fromSwatch) => {
        if (fromSwatch) {
          hex.value = clean;
        } else {
          swatch.value = clean;
        }
        state.settings[settingKey] = clean;

        if (settingKey === "box_bg_color") {
          if (Array.isArray(state.settings.palette) && state.settings.palette.length > 0) {
            state.settings.palette[0] = clean;
            C.renderPaletteEditor(state.settings, onPaletteUpdated);
          }
        } else if (settingKey === "box_border_color") {
          if (!state.settings.box_border_width || Number(state.settings.box_border_width) === 0) {
            state.settings.box_border_width = 1;
            const bwSlider = document.getElementById("ctrl-box-border-width");
            if (bwSlider) bwSlider.value = "1";
            C.updateReadoutLabels(state.settings);
          }
        }

        applyColorsClientSideImmediate();
        scheduleGenerate(70);
      };

      swatch.addEventListener("input", () => {
        applyColorValue(C.normalizeHex(swatch.value), true);
      });
      swatch.addEventListener("change", () => {
        applyColorValue(C.normalizeHex(swatch.value), true);
      });

      hex.addEventListener("input", () => {
        const raw = (hex.value || "").trim();
        if (/^#?[0-9A-Fa-f]{6}$/.test(raw)) {
          applyColorValue(C.normalizeHex(raw, state.settings[settingKey]), false);
        }
      });
      hex.addEventListener("change", () => {
        const clean = C.normalizeHex(hex.value, state.settings[settingKey]);
        hex.value = clean;
        applyColorValue(clean, false);
      });
    };

    bindColorPair(
      "ctrl-background-color",
      "ctrl-background-color-hex",
      "background_color"
    );
    bindColorPair(
      "ctrl-primary-text-color",
      "ctrl-primary-text-color-hex",
      "primary_text_color"
    );
    bindColorPair(
      "ctrl-secondary-text-color",
      "ctrl-secondary-text-color-hex",
      "secondary_text_color"
    );
    bindColorPair("ctrl-box-bg-color", "ctrl-box-bg-color-hex", "box_bg_color");
    bindColorPair(
      "ctrl-box-border-color",
      "ctrl-box-border-color-hex",
      "box_border_color"
    );

    // Add color to palette
    const addColorBtn = document.getElementById("btn-add-palette-color");
    if (addColorBtn) {
      addColorBtn.addEventListener("click", () => {
        if (state.settings.palette.length >= 12) return;
        state.settings.palette.push("#77736F");
        state.settings.palette_weights.push(15);
        C.renderPaletteEditor(state.settings, onPaletteUpdated);
        onPaletteUpdated();
      });
    }

    // Palette presets
    document.querySelectorAll("[data-palette-preset]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const name = btn.getAttribute("data-palette-preset");
        const preset = C.PALETTE_PRESETS[name];
        if (!preset) return;
        state.settings.palette = preset.palette.slice();
        state.settings.palette_weights = preset.weights.slice();
        state.settings.box_bg_color = preset.palette[0];
        const bgSw = document.getElementById("ctrl-box-bg-color");
        const bgHx = document.getElementById("ctrl-box-bg-color-hex");
        if (bgSw) bgSw.value = preset.palette[0];
        if (bgHx) bgHx.value = preset.palette[0];
        C.renderPaletteEditor(state.settings, onPaletteUpdated);
        onPaletteUpdated();
      });
    });

    // Shuffle seed
    const shuffleBtn = document.getElementById("btn-shuffle-seed");
    if (shuffleBtn) {
      shuffleBtn.addEventListener("click", () => {
        const nextSeed = Math.floor(Math.random() * 90000) + 100;
        state.settings.seed = nextSeed;
        const seedIn = document.getElementById("ctrl-seed");
        if (seedIn) seedIn.value = String(nextSeed);
        requestGenerateArtwork(false);
      });
    }

    // Top Header Actions
    const saveBtn = document.getElementById("btn-save-project");
    if (saveBtn) saveBtn.addEventListener("click", () => handleSaveProject());

    const resetBtn = document.getElementById("btn-reset-project");
    if (resetBtn) resetBtn.addEventListener("click", () => handleResetProject());

    // Preview Toolbar Actions
    const zOut = document.getElementById("btn-zoom-out");
    const zIn = document.getElementById("btn-zoom-in");
    const zFit = document.getElementById("btn-zoom-fit");
    const z100 = document.getElementById("btn-zoom-100");
    if (zOut) zOut.addEventListener("click", () => preview && preview.setZoom(preview.zoom * 0.85));
    if (zIn) zIn.addEventListener("click", () => preview && preview.setZoom(preview.zoom * 1.15));
    if (zFit) zFit.addEventListener("click", () => preview && preview.fitToView());
    if (z100) z100.addEventListener("click", () => preview && preview.setZoom(1.0, true));

    const viewBtns = document.querySelectorAll("[data-view-mode]");
    const splitGroup = document.getElementById("split-slider-group");
    viewBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        viewBtns.forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        const mode = btn.getAttribute("data-view-mode") || "artwork";
        if (splitGroup) splitGroup.hidden = mode !== "split";
        if (preview) preview.setViewMode(mode);
      });
    });

    const splitSlider = document.getElementById("ctrl-split-pos");
    if (splitSlider) {
      splitSlider.addEventListener("input", () => {
        if (preview) preview.setSplitPosition(splitSlider.value);
      });
    }

    const stageBtns = document.querySelectorAll("[data-stage-bg]");
    const viewport = document.getElementById("canvas-viewport");
    stageBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        stageBtns.forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        const stage = btn.getAttribute("data-stage-bg") || "paper";
        if (viewport) {
          viewport.classList.remove("stage-paper", "stage-dark", "stage-checker");
          viewport.classList.add(`stage-${stage}`);
        }
      });
    });

    const regenToolbarBtn = document.getElementById("btn-toolbar-regenerate");
    if (regenToolbarBtn) {
      regenToolbarBtn.addEventListener("click", () => requestGenerateArtwork(false));
    }
  }

  function initEditor() {
    const stateScript = document.getElementById("initial-state-json");
    if (!stateScript) return;

    try {
      const parsed = JSON.parse(stateScript.textContent);
      state.settings = parsed.settings || {};
      state.imageMeta = parsed.image_meta || null;
      state.projectId = parsed.project_id || "";
    } catch (_) {}

    // Restore from localStorage only if no server-uploaded image overrode it
    try {
      const cachedRaw = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (cachedRaw) {
        const cached = JSON.parse(cachedRaw);
        if (cached && typeof cached === "object") {
          const keepImageId = state.settings.image_id;
          state.settings = Object.assign({}, state.settings, cached);
          if (
            state.settings.image_id &&
            !String(state.settings.image_id).startsWith("builtin:") &&
            !state.imageMeta
          ) {
            state.settings.image_id = keepImageId || "builtin:portrait";
          }
        }
      }
    } catch (_) {}

    const canvasEl = document.getElementById("artwork-canvas");
    const viewportEl = document.getElementById("canvas-viewport");
    const transformEl = document.getElementById("canvas-transform-layer");
    preview = new window.ArtworkPreview(canvasEl, viewportEl, transformEl);

    exportCtrl = new window.ExportController(
      () => state,
      getCsrfToken,
      setStatus
    );

    window.StudioControls.populateControlsFromSettings(
      state.settings,
      state.imageMeta,
      onPaletteUpdated
    );

    bindAllControls();

    // Perform initial mask preview and artwork generation, then fit canvas to view
    requestMaskProcess();
    requestGenerateArtwork(true);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initEditor);
  } else {
    initEditor();
  }
})();
