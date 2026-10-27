/**
 * TYPEFORM — HTML5 Canvas Interactive Preview Renderer (preview.js)
 * Handles requestAnimationFrame rendering, zoom, pan, fit-to-view,
 * mask overlay, mask-only view, and before/after split comparison.
 */

(function () {
  "use strict";

  class ArtworkPreview {
    constructor(canvasEl, viewportEl, transformLayerEl) {
      this.canvas = canvasEl;
      this.ctx = canvasEl.getContext("2d");
      this.viewport = viewportEl;
      this.transformLayer = transformLayerEl;

      this.layout = null;
      this.maskImg = null;
      this.sourceImg = null;

      this.viewMode = "artwork"; // artwork | overlay | mask | split
      this.splitPos = 0.5;
      this.zoom = 1.0;
      this.panX = 0;
      this.panY = 0;

      this.isDragging = false;
      this.dragStartX = 0;
      this.dragStartY = 0;
      this.panStartX = 0;
      this.panStartY = 0;

      this._rafId = null;
      this._bindInteraction();
    }

    _bindInteraction() {
      if (!this.viewport) return;

      this.viewport.addEventListener("mousedown", (e) => {
        if (e.button !== 0) return;
        this.isDragging = true;
        this.dragStartX = e.clientX;
        this.dragStartY = e.clientY;
        this.panStartX = this.panX;
        this.panStartY = this.panY;
        this.viewport.classList.add("is-panning");
      });

      window.addEventListener("mousemove", (e) => {
        if (!this.isDragging) return;
        const dx = e.clientX - this.dragStartX;
        const dy = e.clientY - this.dragStartY;
        this.panX = this.panStartX + dx;
        this.panY = this.panStartY + dy;
        this._applyTransform();
      });

      window.addEventListener("mouseup", () => {
        if (this.isDragging) {
          this.isDragging = false;
          this.viewport.classList.remove("is-panning");
        }
      });

      this.viewport.addEventListener(
        "wheel",
        (e) => {
          e.preventDefault();
          const factor = e.deltaY < 0 ? 1.1 : 0.9;
          this.setZoom(this.zoom * factor);
        },
        { passive: false }
      );

      window.addEventListener("resize", () => {
        this.scheduleRender();
      });
    }

    setZoom(newZoom, resetPan = false) {
      this.zoom = Math.max(0.15, Math.min(4.0, newZoom));
      if (resetPan) {
        this.panX = 0;
        this.panY = 0;
      }
      this._applyTransform();
      const readout = document.getElementById("zoom-readout");
      if (readout) {
        readout.textContent = `${Math.round(this.zoom * 100)}%`;
      }
    }

    fitToView() {
      if (!this.viewport || !this.canvas) return;
      const vw = Math.max(100, this.viewport.clientWidth - 48);
      const vh = Math.max(100, this.viewport.clientHeight - 48);
      const cw = this.canvas.width || 900;
      const ch = this.canvas.height || 1125;
      const fitScale = Math.min(vw / cw, vh / ch, 1.5);
      this.setZoom(fitScale, true);
    }

    _applyTransform() {
      if (!this.transformLayer) return;
      this.transformLayer.style.transform = `translate(${Math.round(
        this.panX
      )}px, ${Math.round(this.panY)}px) scale(${this.zoom.toFixed(3)})`;
    }

    setViewMode(mode) {
      this.viewMode = mode || "artwork";
      this.scheduleRender();
    }

    setSplitPosition(pct) {
      this.splitPos = Math.max(0.05, Math.min(0.95, Number(pct) / 100));
      this.scheduleRender();
    }

    updateImages(maskDataUrl, sourceDataUrl) {
      if (maskDataUrl) {
        const mImg = new Image();
        mImg.onload = () => {
          this.maskImg = mImg;
          this.scheduleRender();
        };
        mImg.src = maskDataUrl;
      }
      if (sourceDataUrl) {
        const sImg = new Image();
        sImg.onload = () => {
          this.sourceImg = sImg;
          this.scheduleRender();
        };
        sImg.src = sourceDataUrl;
      }
    }

    setLayout(layoutData, autoFitIfChangedSize = false) {
      const prevW = this.canvas.width;
      const prevH = this.canvas.height;
      this.layout = layoutData;

      if (layoutData) {
        const cw = Number(layoutData.canvas_width) || 900;
        const ch = Number(layoutData.canvas_height) || 1125;
        if (this.canvas.width !== cw || this.canvas.height !== ch) {
          this.canvas.width = cw;
          this.canvas.height = ch;
          if (autoFitIfChangedSize || prevW !== cw || prevH !== ch) {
            this.fitToView();
          }
        }
      }
      this.scheduleRender();
    }

    scheduleRender() {
      if (this._rafId) {
        cancelAnimationFrame(this._rafId);
      }
      this._rafId = requestAnimationFrame(() => {
        this._rafId = null;
        this.render();
      });
    }

    _drawSpacedLine(ctx, text, x, y, letterSpacing) {
      if (!text) return;
      if (Math.abs(letterSpacing) < 0.05 || text.length <= 1) {
        ctx.fillText(text, x, y);
        return;
      }
      let cursorX = x;
      for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        ctx.fillText(ch, cursorX, y);
        cursorX += ctx.measureText(ch).width + letterSpacing;
      }
    }

    _measureSpacedLine(ctx, text, letterSpacing) {
      if (!text) return 0;
      const baseW = ctx.measureText(text).width;
      if (text.length <= 1 || Math.abs(letterSpacing) < 0.05) {
        return baseW;
      }
      return baseW + (text.length - 1) * letterSpacing;
    }

    _renderArtworkLayer(ctx, cw, ch) {
      const layout = this.layout;
      if (!layout) return;

      if (!layout.transparent_bg) {
        ctx.fillStyle = layout.background_color || "#F5F3EF";
        ctx.fillRect(0, 0, cw, ch);
      } else {
        ctx.clearRect(0, 0, cw, ch);
      }

      const fontFamily = layout.font_family || "Space Grotesk";
      const fontWeight = layout.font_weight || "700";
      const fontStyle = layout.font_style || "normal";
      const letterSpacing = Number(layout.letter_spacing) || 0;
      const lineHeight = Number(layout.line_height) || 1.15;
      const padX = Number(layout.padding_x) || 6;
      const padY = Number(layout.padding_y) || 4;

      const boxes = layout.boxes || [];
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";

      for (let i = 0; i < boxes.length; i++) {
        const b = boxes[i];
        const bx = b.x;
        const by = b.y;
        const bw = b.w;
        const bh = b.h;

        if (b.fill && b.fill !== "none") {
          ctx.fillStyle = b.fill;
          ctx.fillRect(bx, by, bw, bh);
        }

        if (b.border_width && b.border_width > 0) {
          ctx.strokeStyle = b.border_color || "#171717";
          ctx.lineWidth = b.border_width;
          ctx.strokeRect(
            bx + b.border_width * 0.5,
            by + b.border_width * 0.5,
            Math.max(1, bw - b.border_width),
            Math.max(1, bh - b.border_width)
          );
        }

        const lines = b.lines && b.lines.length ? b.lines : [b.text || ""];
        const fsize = Number(b.font_size) || 15;
        ctx.font = `${fontStyle} ${fontWeight} ${fsize}px "${fontFamily}", "Neue Machina", sans-serif`;
        ctx.fillStyle = b.text_color || "#F5F3EF";

        const capH = Number(b.cap_h) || fsize * 0.72;
        const nLines = lines.length;
        const lineStep = capH * lineHeight;
        const totalBlockH = capH + (nLines - 1) * lineStep;

        let firstCenterY;
        if (b.v_align === "top") {
          firstCenterY = by + padY + capH * 0.5;
        } else if (b.v_align === "bottom") {
          firstCenterY = by + bh - padY - totalBlockH + capH * 0.5;
        } else {
          firstCenterY = by + (bh - totalBlockH) * 0.5 + capH * 0.5;
        }

        ctx.save();
        ctx.beginPath();
        ctx.rect(bx, by, bw, bh);
        ctx.clip();

        for (let l = 0; l < nLines; l++) {
          const ln = lines[l];
          if (!ln) continue;
          const lineW = this._measureSpacedLine(ctx, ln, letterSpacing);
          let lineX;
          if (b.h_align === "left") {
            lineX = bx + padX;
          } else if (b.h_align === "right") {
            lineX = bx + bw - padX - lineW;
          } else {
            lineX = bx + (bw - lineW) * 0.5;
          }
          const lineY = firstCenterY + l * lineStep;
          this._drawSpacedLine(ctx, ln, lineX, lineY, letterSpacing);
        }

        ctx.restore();
      }
    }

    render() {
      const ctx = this.ctx;
      const cw = this.canvas.width;
      const ch = this.canvas.height;
      ctx.clearRect(0, 0, cw, ch);

      if (this.viewMode === "mask") {
        ctx.fillStyle = "#F5F3EF";
        ctx.fillRect(0, 0, cw, ch);
        if (this.maskImg) {
          ctx.imageSmoothingEnabled = false;
          ctx.drawImage(this.maskImg, 0, 0, cw, ch);
        }
        return;
      }

      if (this.viewMode === "split") {
        const splitX = Math.round(cw * this.splitPos);

        // Left half: source or mask preview
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, splitX, ch);
        ctx.clip();
        ctx.fillStyle = "#F5F3EF";
        ctx.fillRect(0, 0, cw, ch);
        const refImg = this.sourceImg || this.maskImg;
        if (refImg) {
          ctx.drawImage(refImg, 0, 0, cw, ch);
        }
        ctx.restore();

        // Right half: generated artwork
        ctx.save();
        ctx.beginPath();
        ctx.rect(splitX, 0, cw - splitX, ch);
        ctx.clip();
        this._renderArtworkLayer(ctx, cw, ch);
        ctx.restore();

        // Editorial divider line
        ctx.strokeStyle = "#171717";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(splitX, 0);
        ctx.lineTo(splitX, ch);
        ctx.stroke();
        return;
      }

      // Default "artwork" or "overlay"
      this._renderArtworkLayer(ctx, cw, ch);

      if (this.viewMode === "overlay" && this.maskImg) {
        ctx.save();
        ctx.globalAlpha = 0.24;
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(this.maskImg, 0, 0, cw, ch);
        ctx.restore();
      }
    }
  }

  window.ArtworkPreview = ArtworkPreview;
})();
