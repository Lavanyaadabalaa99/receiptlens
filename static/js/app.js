// ReceiptLens - Main Application Controller

document.addEventListener('DOMContentLoaded', () => {
  const app = {
    state: {
      activeTab: 'upload',
      currentReceipt: null,
      receipts: [],
      samples: [],
      hasApiKey: false,
      uploadQueue: [],
      isProcessing: false
    },

    modules: {
      viewer: null,
      camera: null,
      dashboard: null
    },

    init() {
      this.initModules();
      this.bindEvents();
      this.checkConfig();
      this.loadSamples();
      this.loadReceipts();
      this.showTab('upload');
    },

    initModules() {
      this.modules.viewer = new ReceiptViewer('viewer-canvas-wrap', 'viewer-receipt-image');
      this.modules.camera = new CameraCapture('camera-video', 'camera-modal');
      this.modules.dashboard = new ReceiptDashboard();
    },

    bindEvents() {
      // Navigation Tabs
      document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
          const target = tab.dataset.tab;
          this.showTab(target);
        });
      });

      // Drag & Drop / File Input
      const dropzone = document.getElementById('dropzone');
      const fileInput = document.getElementById('file-input');

      if (dropzone && fileInput) {
        dropzone.addEventListener('click', () => fileInput.click());
        
        ['dragenter', 'dragover'].forEach(eventName => {
          dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
          });
        });

        ['dragleave', 'drop'].forEach(eventName => {
          dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
          });
        });

        dropzone.addEventListener('drop', (e) => {
          const files = e.dataTransfer.files;
          if (files.length > 0) {
            this.handleFiles(Array.from(files));
          }
        });

        fileInput.addEventListener('change', (e) => {
          if (e.target.files.length > 0) {
            this.handleFiles(Array.from(e.target.files));
          }
        });
      }

      // Camera Modal buttons
      const btnOpenCam = document.getElementById('btn-open-camera');
      const btnCloseCam = document.getElementById('btn-close-camera');
      const btnSnapCam = document.getElementById('btn-snap-camera');
      const btnFlipCam = document.getElementById('btn-flip-camera');

      if (btnOpenCam) {
        btnOpenCam.addEventListener('click', async () => {
          this.openModal('camera-modal');
          await this.modules.camera.start();
        });
      }

      if (btnCloseCam) {
        btnCloseCam.addEventListener('click', () => {
          this.modules.camera.stop();
          this.closeModal('camera-modal');
        });
      }

      if (btnFlipCam) {
        btnFlipCam.addEventListener('click', () => {
          this.modules.camera.flipCamera();
        });
      }

      if (btnSnapCam) {
        btnSnapCam.addEventListener('click', async () => {
          const captured = await this.modules.camera.captureFrame();
          if (captured) {
            this.modules.camera.stop();
            this.closeModal('camera-modal');
            this.handleFiles([captured.file]);
          }
        });
      }

      // Settings Modal
      const btnSettings = document.getElementById('btn-settings');
      const btnCloseSettings = document.getElementById('btn-close-settings');
      const btnSaveApiKey = document.getElementById('btn-save-api-key');

      if (btnSettings) {
        btnSettings.addEventListener('click', () => {
          this.openModal('settings-modal');
        });
      }

      if (btnCloseSettings) {
        btnCloseSettings.addEventListener('click', () => {
          this.closeModal('settings-modal');
        });
      }

      if (btnSaveApiKey) {
        btnSaveApiKey.addEventListener('click', () => this.saveApiKey());
      }

      // Viewer Controls
      document.getElementById('btn-zoom-in')?.addEventListener('click', () => this.modules.viewer.zoomIn());
      document.getElementById('btn-zoom-out')?.addEventListener('click', () => this.modules.viewer.zoomOut());
      document.getElementById('btn-zoom-reset')?.addEventListener('click', () => this.modules.viewer.reset());
      document.getElementById('btn-zoom-fit')?.addEventListener('click', () => this.modules.viewer.fitWidth());
      document.getElementById('btn-rotate')?.addEventListener('click', () => this.modules.viewer.rotate());

      // Editor Actions
      document.getElementById('btn-add-item')?.addEventListener('click', () => this.addNewLineItem());
      document.getElementById('btn-save-receipt')?.addEventListener('click', () => this.saveCurrentReceipt());
      document.getElementById('btn-delete-receipt')?.addEventListener('click', () => this.deleteCurrentReceipt());
      document.getElementById('btn-export-single-csv')?.addEventListener('click', () => {
        if (this.state.currentReceipt) ReceiptExporter.exportReceiptCSV(this.state.currentReceipt);
      });
      document.getElementById('btn-export-single-json')?.addEventListener('click', () => {
        if (this.state.currentReceipt) ReceiptExporter.exportReceiptJSON(this.state.currentReceipt);
      });

      // Bulk Export Buttons
      document.getElementById('btn-export-all-csv')?.addEventListener('click', () => ReceiptExporter.downloadAllCSV('flattened'));
      document.getElementById('btn-export-all-json')?.addEventListener('click', () => ReceiptExporter.downloadAllJSON());

      // Table filters & Search
      document.getElementById('search-input')?.addEventListener('input', (e) => this.filterReceiptsTable());
      document.getElementById('filter-category')?.addEventListener('change', (e) => this.filterReceiptsTable());
      document.getElementById('filter-status')?.addEventListener('change', (e) => this.filterReceiptsTable());

      // Form real-time inputs change
      const editorForm = document.getElementById('receipt-editor-form');
      if (editorForm) {
        editorForm.addEventListener('input', (e) => {
          this.syncFormDataToState();
          this.runMathValidation();
        });
      }
    },

    showTab(tabName) {
      this.state.activeTab = tabName;
      document.querySelectorAll('.nav-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tabName);
      });
      document.querySelectorAll('.view-section').forEach(s => {
        s.classList.toggle('active', s.id === `view-${tabName}`);
      });

      if (tabName === 'dashboard') {
        this.modules.dashboard.loadStats();
      } else if (tabName === 'receipts') {
        this.loadReceipts();
      } else if (tabName === 'review') {
        if (this.state.currentReceipt) {
          this.renderEditor(this.state.currentReceipt);
        }
      }
    },

    openModal(id) {
      const el = document.getElementById(id);
      if (el) el.classList.add('active');
    },

    closeModal(id) {
      const el = document.getElementById(id);
      if (el) el.classList.remove('active');
    },

    toast(msg, type = 'info') {
      const container = document.getElementById('toast-container');
      if (!container) return;
      const toast = document.createElement('div');
      toast.className = `toast ${type}`;
      toast.innerHTML = `<span>${msg}</span>`;
      container.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        setTimeout(() => toast.remove(), 300);
      }, 3500);
    },

    async checkConfig() {
      try {
        const resp = await fetch('/api/config');
        const data = await resp.json();
        this.state.hasApiKey = data.has_api_key;
        const statusEl = document.getElementById('gemini-status');
        if (statusEl) {
          if (data.has_api_key) {
            statusEl.innerHTML = `<span class="status-dot"></span> Gemini Active (${data.key_preview})`;
          } else {
            statusEl.innerHTML = `<span class="status-dot warning"></span> Gemini Key Needed`;
          }
        }
      } catch (err) {
        console.error('Config check failed:', err);
      }
    },

    async saveApiKey() {
      const input = document.getElementById('setting-gemini-key');
      const key = input.value.trim();
      if (!key) {
        this.toast('Please enter a valid Gemini API Key', 'error');
        return;
      }
      try {
        const resp = await fetch('/api/config/key', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: key })
        });
        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || 'Failed to save key');
        }
        this.toast('Gemini API key saved successfully!', 'success');
        this.closeModal('settings-modal');
        this.checkConfig();
      } catch (err) {
        this.toast(err.message, 'error');
      }
    },

    async loadSamples() {
      try {
        const resp = await fetch('/api/samples');
        this.state.samples = await resp.json();
        this.renderSamplesList();
      } catch (err) {
        console.error('Failed to fetch samples:', err);
      }
    },

    renderSamplesList() {
      const grid = document.getElementById('samples-grid');
      if (!grid) return;

      grid.innerHTML = this.state.samples.map(s => {
        const isBlurry = !s.is_valid_receipt;
        return `
          <div class="sample-card" onclick="window.App.loadSampleReceipt('${s.id}')">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="sample-badge category-tag ${s.category}">${s.category}</span>
              <span class="sample-tag">${isBlurry ? '⚠️ Unreadable' : (s.date || '')}</span>
            </div>
            <div class="sample-vendor">${s.vendor_name || 'Blurry / Unreadable Slip'}</div>
            <div class="sample-amount">${s.total ? `${s.currency_symbol || '₹'}${s.total.toFixed(2)}` : 'N/A'}</div>
            <div class="sample-tag">${isBlurry ? 'Click to see rejection handling' : `${s.line_items.length} line items extracted`}</div>
          </div>
        `;
      }).join('');
    },

    loadSampleReceipt(sampleId) {
      const sample = this.state.samples.find(s => s.id === sampleId);
      if (!sample) return;

      const fullReceipt = {
        ...sample,
        id: `sample_${Date.now()}`,
        image_data: `/samples/${sampleId}.svg`,
        mime_type: 'image/svg+xml'
      };

      this.state.currentReceipt = JSON.parse(JSON.stringify(fullReceipt));
      this.toast(`Loaded sample: ${sample.vendor_name || 'Blurry Image'}`, 'info');
      this.showTab('review');
    },

    async handleFiles(files) {
      if (!files || files.length === 0) return;

      if (!this.state.hasApiKey) {
        this.openModal('settings-modal');
        this.toast('Please configure your Gemini API Key first, or explore sample receipts below.', 'info');
        return;
      }

      this.state.uploadQueue = files.map((file, idx) => ({
        id: `queue_${Date.now()}_${idx}`,
        file: file,
        filename: file.name,
        size: `${(file.size / 1024).toFixed(1)} KB`,
        status: 'pending', // pending, extracting, done, error
        result: null
      }));

      this.renderQueue();
      this.processQueue();
    },

    renderQueue() {
      const queueWrap = document.getElementById('queue-container');
      const list = document.getElementById('queue-list');
      if (!queueWrap || !list) return;

      if (this.state.uploadQueue.length === 0) {
        queueWrap.style.display = 'none';
        return;
      }

      queueWrap.style.display = 'block';
      list.innerHTML = this.state.uploadQueue.map(item => `
        <div class="queue-item">
          <div style="display:flex; align-items:center; gap:0.75rem;">
            <div class="queue-thumb" style="display:flex; align-items:center; justify-content:center;">
              <i data-lucide="file-text" style="width:20px; color:#94a3b8;"></i>
            </div>
            <div class="queue-info">
              <div class="queue-filename">${item.filename}</div>
              <div class="queue-size">${item.size}</div>
            </div>
          </div>
          <div>
            ${item.status === 'pending' ? '<span class="status-badge warning">In Queue</span>' : ''}
            ${item.status === 'extracting' ? '<span class="status-badge" style="background:#4338ca; color:#c7d2fe;">Extracting with Gemini...</span>' : ''}
            ${item.status === 'done' ? '<span class="status-badge valid">Ready</span>' : ''}
            ${item.status === 'error' ? '<span class="status-badge flagged">Failed</span>' : ''}
          </div>
        </div>
      `).join('');

      if (window.lucide) window.lucide.createIcons();
    },

    async processQueue() {
      if (this.state.isProcessing) return;
      this.state.isProcessing = true;

      for (const item of this.state.uploadQueue) {
        if (item.status !== 'pending') continue;

        item.status = 'extracting';
        this.renderQueue();

        const formData = new FormData();
        formData.append('file', item.file);

        try {
          const resp = await fetch('/api/extract', {
            method: 'POST',
            body: formData
          });

          if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Extraction failed');
          }

          const res = await resp.json();
          item.status = 'done';
          item.result = res;

          // Normalize receipt object for editor
          const raw = res.extracted_data;
          const processedReceipt = {
            id: res.id,
            filename: res.filename,
            image_data: res.image_data,
            mime_type: res.mime_type,
            vendor_name: raw.vendor_name,
            vendor_address: raw.vendor_address,
            vendor_phone: raw.vendor_phone,
            date: raw.date,
            currency: raw.currency || 'INR',
            currency_symbol: raw.currency_symbol || '₹',
            category: raw.category || 'Other',
            line_items: raw.line_items || [],
            subtotal: raw.subtotal,
            tax: raw.tax,
            tax_breakdown: raw.tax_breakdown,
            tip: raw.tip,
            discount: raw.discount,
            total: raw.total,
            payment_method: raw.payment_method,
            confidence: raw.confidence || 0.9,
            unclear_fields: raw.unclear_fields || [],
            is_valid_receipt: raw.is_receipt !== false,
            rejection_reason: raw.rejection_reason,
            notes: raw.notes
          };

          // Save automatically to DB
          await this.saveReceiptToBackend(processedReceipt);
          this.state.currentReceipt = processedReceipt;
        } catch (err) {
          console.error('Extraction error for', item.filename, err);
          item.status = 'error';
          this.toast(`Error extracting ${item.filename}: ${err.message}`, 'error');
        }

        this.renderQueue();
      }

      this.state.isProcessing = false;
      this.loadReceipts();

      if (this.state.currentReceipt) {
        this.showTab('review');
      }
    },

    renderEditor(receipt) {
      if (!receipt) return;

      // 1. Load image into Left Panel Viewer
      const viewerImg = document.getElementById('viewer-receipt-image');
      if (receipt.image_data) {
        this.modules.viewer.loadImage(receipt.image_data);
      } else {
        this.modules.viewer.loadImage('/samples/demo_indian_bhavan.svg');
      }

      // 2. Error banner if unreadable / rejected
      const errorBanner = document.getElementById('rejection-error-banner');
      if (!receipt.is_valid_receipt) {
        errorBanner.style.display = 'block';
        document.getElementById('rejection-reason-text').textContent = receipt.rejection_reason || 'Image is blurry or not a financial receipt.';
      } else {
        errorBanner.style.display = 'none';
      }

      // 3. Populate Header meta & form inputs
      document.getElementById('input-vendor-name').value = receipt.vendor_name || '';
      document.getElementById('input-date').value = receipt.date || '';
      document.getElementById('select-category').value = receipt.category || 'Other';
      document.getElementById('select-currency').value = receipt.currency || 'INR';
      document.getElementById('input-payment-method').value = receipt.payment_method || '';
      document.getElementById('input-vendor-address').value = receipt.vendor_address || '';
      document.getElementById('input-notes').value = receipt.notes || '';

      // Totals
      document.getElementById('input-subtotal').value = receipt.subtotal !== null && receipt.subtotal !== undefined ? receipt.subtotal : '';
      document.getElementById('input-tax').value = receipt.tax !== null && receipt.tax !== undefined ? receipt.tax : '';
      document.getElementById('input-tip').value = receipt.tip !== null && receipt.tip !== undefined ? receipt.tip : '';
      document.getElementById('input-discount').value = receipt.discount !== null && receipt.discount !== undefined ? receipt.discount : '';
      document.getElementById('input-total').value = receipt.total !== null && receipt.total !== undefined ? receipt.total : '';

      // Confidence chip
      const confScore = Math.round((receipt.confidence || 0.9) * 100);
      const confChip = document.getElementById('confidence-chip');
      if (confChip) {
        confChip.textContent = `${confScore}% Confidence`;
        confChip.className = `confidence-chip ${confScore >= 85 ? 'high' : confScore >= 60 ? 'medium' : 'low'}`;
      }

      // Unclear fields chips
      const unclearWrap = document.getElementById('unclear-chips-wrap');
      if (unclearWrap) {
        const fields = receipt.unclear_fields || [];
        if (fields.length > 0) {
          unclearWrap.innerHTML = fields.map(f => `<span class="unclear-chip">⚠️ ${f}</span>`).join('');
        } else {
          unclearWrap.innerHTML = '<span style="font-size:0.75rem; color:#10b981;">✓ All visible fields clear</span>';
        }
      }

      // 4. Render Line Items Table
      this.renderLineItemsTable(receipt.line_items || []);

      // 5. Run Live Validation
      this.runMathValidation();
    },

    renderLineItemsTable(items) {
      const tbody = document.getElementById('line-items-tbody');
      if (!tbody) return;

      tbody.innerHTML = items.map((item, idx) => `
        <tr class="item-row" data-idx="${idx}">
          <td>
            <input type="text" class="form-input item-name" value="${item.name || ''}" placeholder="Item description" />
          </td>
          <td style="width: 80px;">
            <input type="number" step="any" class="form-input item-qty number" value="${item.quantity !== null && item.quantity !== undefined ? item.quantity : ''}" placeholder="1" />
          </td>
          <td style="width: 110px;">
            <input type="number" step="any" class="form-input item-price number" value="${item.unit_price !== null && item.unit_price !== undefined ? item.unit_price : ''}" placeholder="0.00" />
          </td>
          <td style="width: 120px;">
            <input type="number" step="any" class="form-input item-total number" value="${item.total !== null && item.total !== undefined ? item.total : ''}" placeholder="0.00" />
          </td>
          <td style="width: 40px; text-align:center;">
            <button type="button" class="item-delete-btn" onclick="window.App.deleteLineItem(${idx})" title="Delete Item">
              <i data-lucide="trash-2" style="width:16px;"></i>
            </button>
          </td>
        </tr>
      `).join('');

      if (window.lucide) window.lucide.createIcons();

      // Bind row input listeners for auto item-total calculate
      tbody.querySelectorAll('.item-row').forEach(row => {
        const qtyInp = row.querySelector('.item-qty');
        const priceInp = row.querySelector('.item-price');
        const totalInp = row.querySelector('.item-total');

        const recalculateRow = () => {
          const qty = parseFloat(qtyInp.value) || 1;
          const price = parseFloat(priceInp.value);
          if (!isNaN(price)) {
            totalInp.value = (qty * price).toFixed(2);
          }
          this.syncFormDataToState();
          this.runMathValidation();
        };

        qtyInp.addEventListener('input', recalculateRow);
        priceInp.addEventListener('input', recalculateRow);
        totalInp.addEventListener('input', () => {
          this.syncFormDataToState();
          this.runMathValidation();
        });
      });
    },

    addNewLineItem() {
      if (!this.state.currentReceipt) return;
      if (!this.state.currentReceipt.line_items) {
        this.state.currentReceipt.line_items = [];
      }
      this.state.currentReceipt.line_items.push({
        name: 'New Item',
        quantity: 1,
        unit_price: 0,
        total: 0
      });
      this.renderLineItemsTable(this.state.currentReceipt.line_items);
      this.syncFormDataToState();
      this.runMathValidation();
    },

    deleteLineItem(idx) {
      if (!this.state.currentReceipt || !this.state.currentReceipt.line_items) return;
      this.state.currentReceipt.line_items.splice(idx, 1);
      this.renderLineItemsTable(this.state.currentReceipt.line_items);
      this.syncFormDataToState();
      this.runMathValidation();
    },

    syncFormDataToState() {
      if (!this.state.currentReceipt) return;

      const r = this.state.currentReceipt;
      r.vendor_name = document.getElementById('input-vendor-name')?.value || '';
      r.date = document.getElementById('input-date')?.value || '';
      r.category = document.getElementById('select-category')?.value || 'Other';
      r.currency = document.getElementById('select-currency')?.value || 'INR';
      r.currency_symbol = r.currency === 'INR' ? '₹' : (r.currency === 'USD' ? '$' : (r.currency === 'EUR' ? '€' : '£'));
      r.payment_method = document.getElementById('input-payment-method')?.value || '';
      r.vendor_address = document.getElementById('input-vendor-address')?.value || '';
      r.notes = document.getElementById('input-notes')?.value || '';

      const subVal = parseFloat(document.getElementById('input-subtotal')?.value);
      r.subtotal = !isNaN(subVal) ? subVal : null;

      const taxVal = parseFloat(document.getElementById('input-tax')?.value);
      r.tax = !isNaN(taxVal) ? taxVal : null;

      const tipVal = parseFloat(document.getElementById('input-tip')?.value);
      r.tip = !isNaN(tipVal) ? tipVal : null;

      const discVal = parseFloat(document.getElementById('input-discount')?.value);
      r.discount = !isNaN(discVal) ? discVal : null;

      const totVal = parseFloat(document.getElementById('input-total')?.value);
      r.total = !isNaN(totVal) ? totVal : null;

      // Sync Line items from table
      const rows = document.querySelectorAll('#line-items-tbody .item-row');
      r.line_items = Array.from(rows).map(row => {
        const name = row.querySelector('.item-name')?.value || '';
        const qty = parseFloat(row.querySelector('.item-qty')?.value);
        const price = parseFloat(row.querySelector('.item-price')?.value);
        const lineTot = parseFloat(row.querySelector('.item-total')?.value);

        return {
          name: name,
          quantity: !isNaN(qty) ? qty : null,
          unit_price: !isNaN(price) ? price : null,
          total: !isNaN(lineTot) ? lineTot : null
        };
      });
    },

    runMathValidation() {
      if (!this.state.currentReceipt) return;

      const val = ReceiptValidator.validate(this.state.currentReceipt);
      const banner = document.getElementById('math-validation-banner');
      const bannerTitle = document.getElementById('validation-banner-title');
      const bannerDesc = document.getElementById('validation-banner-desc');
      const reconcileBtnWrap = document.getElementById('reconcile-actions-wrap');

      if (!banner) return;

      if (val.status === 'flagged') {
        banner.className = 'validation-banner flagged';
        bannerTitle.textContent = `⚠️ Calculation Mismatch (Discrepancy: ${this.state.currentReceipt.currency_symbol || '₹'}${val.discrepancy})`;
        bannerDesc.textContent = val.message;
        
        // Render 1-click Auto-Reconcile buttons
        reconcileBtnWrap.innerHTML = `
          <button type="button" class="btn btn-sm btn-secondary" onclick="window.App.autoReconcileTotal(${val.expectedTotal})">
            Fix Grand Total to ${this.state.currentReceipt.currency_symbol || '₹'}${val.expectedTotal}
          </button>
        `;
        reconcileBtnWrap.style.display = 'flex';
      } else if (val.status === 'valid') {
        banner.className = 'validation-banner valid';
        bannerTitle.textContent = '✓ Math Verified';
        bannerDesc.textContent = `Sum of items (${val.itemsSum.toFixed(2)}) + Tax + Tip matches Grand Total (${val.actualTotal.toFixed(2)}) accurately.`;
        reconcileBtnWrap.style.display = 'none';
      } else {
        banner.className = 'validation-banner warning';
        bannerTitle.textContent = 'Total Missing';
        bannerDesc.textContent = val.message;
        reconcileBtnWrap.style.display = 'none';
      }
    },

    autoReconcileTotal(newTotal) {
      document.getElementById('input-total').value = newTotal;
      this.syncFormDataToState();
      this.runMathValidation();
      this.toast(`Updated total to ${this.state.currentReceipt.currency_symbol || '₹'}${newTotal}`, 'success');
    },

    async saveCurrentReceipt() {
      if (!this.state.currentReceipt) return;
      this.syncFormDataToState();
      try {
        await this.saveReceiptToBackend(this.state.currentReceipt);
        this.toast('Receipt saved successfully!', 'success');
        this.loadReceipts();
      } catch (err) {
        this.toast(`Failed to save receipt: ${err.message}`, 'error');
      }
    },

    async saveReceiptToBackend(receiptData) {
      const resp = await fetch('/api/receipts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(receiptData)
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Save failed');
      }
      return await resp.json();
    },

    async deleteCurrentReceipt() {
      if (!this.state.currentReceipt || !confirm('Are you sure you want to delete this receipt?')) return;
      try {
        await fetch(`/api/receipts/${this.state.currentReceipt.id}`, { method: 'DELETE' });
        this.toast('Receipt deleted', 'info');
        this.state.currentReceipt = null;
        this.loadReceipts();
        this.showTab('receipts');
      } catch (err) {
        this.toast(`Delete failed: ${err.message}`, 'error');
      }
    },

    async loadReceipts() {
      try {
        const resp = await fetch('/api/receipts');
        this.state.receipts = await resp.json();
        
        // If DB was empty, seed with demo samples automatically
        if (this.state.receipts.length === 0) {
          await fetch('/api/samples/seed', { method: 'POST' });
          const res = await fetch('/api/receipts');
          this.state.receipts = await res.json();
        }
        
        this.renderReceiptsTable(this.state.receipts);
      } catch (err) {
        console.error('Failed to load receipts:', err);
      }
    },

    renderReceiptsTable(list) {
      const tbody = document.getElementById('all-receipts-tbody');
      if (!tbody) return;

      if (!list || list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 2.5rem; color: #64748b;">No receipts found. Upload a receipt or try sample data above.</td></tr>`;
        return;
      }

      tbody.innerHTML = list.map(r => {
        const sym = r.currency_symbol || (r.currency === 'INR' ? '₹' : '$');
        const isFlagged = r.validation_status === 'flagged';
        return `
          <tr style="cursor: pointer;" onclick="window.App.openReceiptInEditor('${r.id}')">
            <td>
              <div style="font-weight: 600;">${r.vendor_name || 'Unknown Store'}</div>
              <div style="font-size: 0.75rem; color: #64748b;">${r.date || 'No Date'}</div>
            </td>
            <td><span class="category-tag ${r.category}">${r.category}</span></td>
            <td>${(r.line_items || []).length} item${(r.line_items || []).length !== 1 ? 's' : ''}</td>
            <td style="font-family: var(--font-mono); font-weight: 700;">
              ${r.total !== null ? `${sym}${Number(r.total).toFixed(2)}` : 'N/A'}
            </td>
            <td>
              <span class="status-badge ${r.validation_status || 'valid'}">
                ${isFlagged ? '⚠️ Mismatch' : '✓ Verified'}
              </span>
            </td>
            <td>
              <span class="confidence-chip ${Math.round((r.confidence || 0.9)*100) >= 85 ? 'high' : 'medium'}">
                ${Math.round((r.confidence || 0.9)*100)}%
              </span>
            </td>
            <td onclick="event.stopPropagation();">
              <div style="display:flex; gap:0.35rem;">
                <button class="btn btn-sm btn-secondary" onclick="window.App.openReceiptInEditor('${r.id}')" title="Review & Edit">
                  <i data-lucide="edit-3" style="width:14px;"></i>
                </button>
                <button class="btn btn-sm btn-secondary" onclick="window.App.exportSingle('${r.id}', 'json')" title="Download JSON">
                  <i data-lucide="download" style="width:14px;"></i>
                </button>
                <button class="btn btn-sm btn-danger" onclick="window.App.deleteReceiptById('${r.id}')" title="Delete">
                  <i data-lucide="trash" style="width:14px;"></i>
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');

      if (window.lucide) window.lucide.createIcons();
    },

    openReceiptInEditor(id) {
      const r = this.state.receipts.find(item => item.id === id);
      if (r) {
        this.state.currentReceipt = JSON.parse(JSON.stringify(r));
        this.showTab('review');
      }
    },

    async deleteReceiptById(id) {
      if (!confirm('Are you sure you want to delete this receipt?')) return;
      try {
        await fetch(`/api/receipts/${id}`, { method: 'DELETE' });
        this.toast('Receipt deleted', 'info');
        this.loadReceipts();
      } catch (err) {
        this.toast(`Delete failed: ${err.message}`, 'error');
      }
    },

    exportSingle(id, format) {
      const r = this.state.receipts.find(item => item.id === id);
      if (r) {
        if (format === 'json') ReceiptExporter.exportReceiptJSON(r);
        else ReceiptExporter.exportReceiptCSV(r);
      }
    },

    filterReceiptsTable() {
      const search = document.getElementById('search-input')?.value.toLowerCase() || '';
      const cat = document.getElementById('filter-category')?.value || 'All';
      const status = document.getElementById('filter-status')?.value || 'All';

      const filtered = this.state.receipts.filter(r => {
        const matchesSearch = !search || 
          (r.vendor_name && r.vendor_name.toLowerCase().includes(search)) ||
          (r.notes && r.notes.toLowerCase().includes(search));
        const matchesCat = cat === 'All' || r.category === cat;
        const matchesStatus = status === 'All' || r.validation_status === status;

        return matchesSearch && matchesCat && matchesStatus;
      });

      this.renderReceiptsTable(filtered);
    }
  };

  window.App = app;
  app.init();
});
