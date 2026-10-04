// ReceiptLens - WebRTC Camera Capture Module

class CameraCapture {
  constructor(videoElementId, modalId) {
    this.video = document.getElementById(videoElementId);
    this.modal = document.getElementById(modalId);
    this.stream = null;
    this.facingMode = 'environment'; // back camera on mobile by default
  }

  async start() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert('Camera access is not supported in this browser.');
      return false;
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: this.facingMode },
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        },
        audio: false
      });

      if (this.video) {
        this.video.srcObject = this.stream;
        await this.video.play();
      }
      return true;
    } catch (err) {
      console.error('Camera stream error:', err);
      // Fallback without exact constraints
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (this.video) {
          this.video.srcObject = this.stream;
          await this.video.play();
        }
        return true;
      } catch (e) {
        alert('Could not access camera: ' + e.message);
        return false;
      }
    }
  }

  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    if (this.video) {
      this.video.srcObject = null;
    }
  }

  flipCamera() {
    this.facingMode = this.facingMode === 'environment' ? 'user' : 'environment';
    this.stop();
    this.start();
  }

  captureFrame() {
    if (!this.video) return null;

    const canvas = document.createElement('canvas');
    canvas.width = this.video.videoWidth || 1280;
    canvas.height = this.video.videoHeight || 720;
    
    const ctx = canvas.getContext('2d');
    ctx.drawImage(this.video, 0, 0, canvas.width, canvas.height);

    return new Promise((resolve) => {
      canvas.toBlob((blob) => {
        const file = new File([blob], `camera_receipt_${Date.now()}.jpg`, { type: 'image/jpeg' });
        resolve({ blob, file, dataUrl: canvas.toDataURL('image/jpeg', 0.92) });
      }, 'image/jpeg', 0.92);
    });
  }
}

window.CameraCapture = CameraCapture;
