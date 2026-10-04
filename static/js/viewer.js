// ReceiptLens - Interactive Pan & Zoom Image Viewer

class ReceiptViewer {
  constructor(canvasWrapId, imageId) {
    this.wrap = document.getElementById(canvasWrapId);
    this.img = document.getElementById(imageId);
    
    this.scale = 1;
    this.minScale = 0.2;
    this.maxScale = 5.0;
    this.translateX = 0;
    this.translateY = 0;
    this.rotation = 0;
    
    this.isDragging = false;
    this.startX = 0;
    this.startY = 0;
    
    this.initEvents();
  }
  
  initEvents() {
    if (!this.wrap || !this.img) return;
    
    // Mouse Wheel Zoom
    this.wrap.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.15 : 0.15;
      this.zoom(delta);
    }, { passive: false });
    
    // Mouse Drag / Pan
    this.wrap.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      this.isDragging = true;
      this.startX = e.clientX - this.translateX;
      this.startY = e.clientY - this.translateY;
      this.wrap.classList.add('grabbing');
    });
    
    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      this.translateX = e.clientX - this.startX;
      this.translateY = e.clientY - this.startY;
      this.updateTransform();
    });
    
    window.addEventListener('mouseup', () => {
      this.isDragging = false;
      this.wrap.classList.remove('grabbing');
    });
    
    // Touch support
    let touchStartDist = 0;
    this.wrap.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        this.isDragging = true;
        this.startX = e.touches[0].clientX - this.translateX;
        this.startY = e.touches[0].clientY - this.translateY;
      } else if (e.touches.length === 2) {
        touchStartDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
      }
    });
    
    this.wrap.addEventListener('touchmove', (e) => {
      e.preventDefault();
      if (e.touches.length === 1 && this.isDragging) {
        this.translateX = e.touches[0].clientX - this.startX;
        this.translateY = e.touches[0].clientY - this.startY;
        this.updateTransform();
      } else if (e.touches.length === 2) {
        const dist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        const factor = (dist - touchStartDist) * 0.005;
        this.zoom(factor);
        touchStartDist = dist;
      }
    }, { passive: false });
    
    this.wrap.addEventListener('touchend', () => {
      this.isDragging = false;
    });
  }
  
  loadImage(src) {
    if (!this.img) return;
    this.img.src = src;
    this.reset();
  }
  
  zoom(delta) {
    const newScale = Math.min(Math.max(this.scale + delta, this.minScale), this.maxScale);
    this.scale = newScale;
    this.updateTransform();
    this.updateZoomLabel();
  }
  
  zoomIn() {
    this.zoom(0.25);
  }
  
  zoomOut() {
    this.zoom(-0.25);
  }
  
  rotate() {
    this.rotation = (this.rotation + 90) % 360;
    this.updateTransform();
  }
  
  reset() {
    this.scale = 1;
    this.translateX = 0;
    this.translateY = 0;
    this.rotation = 0;
    this.updateTransform();
    this.updateZoomLabel();
  }
  
  fitWidth() {
    if (!this.wrap || !this.img) return;
    const wrapWidth = this.wrap.clientWidth;
    const imgWidth = this.img.naturalWidth || 400;
    this.scale = Math.min(Math.max((wrapWidth * 0.85) / imgWidth, 0.4), 2.5);
    this.translateX = 0;
    this.translateY = 0;
    this.updateTransform();
    this.updateZoomLabel();
  }
  
  updateTransform() {
    if (!this.img) return;
    this.img.style.transform = `translate(${this.translateX}px, ${this.translateY}px) scale(${this.scale}) rotate(${this.rotation}deg)`;
  }
  
  updateZoomLabel() {
    const label = document.getElementById('zoom-percentage');
    if (label) {
      label.textContent = `${Math.round(this.scale * 100)}%`;
    }
  }
}

window.ReceiptViewer = ReceiptViewer;
