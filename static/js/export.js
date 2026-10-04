// ReceiptLens - CSV & JSON Exporter

class ReceiptExporter {
  /**
   * Export single receipt to JSON
   */
  static exportReceiptJSON(receipt) {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(receipt, null, 2));
    const filename = `receipt_${(receipt.vendor_name || 'receipt').replace(/[^a-z0-9]/gi, '_').toLowerCase()}_${receipt.date || 'unknown'}.json`;
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", filename);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  }

  /**
   * Export single receipt to CSV
   */
  static exportReceiptCSV(receipt) {
    const rows = [];
    rows.push(["Field", "Value"]);
    rows.push(["Receipt ID", receipt.id || ""]);
    rows.push(["Vendor Name", receipt.vendor_name || ""]);
    rows.push(["Date", receipt.date || ""]);
    rows.push(["Category", receipt.category || ""]);
    rows.push(["Currency", receipt.currency || "INR"]);
    rows.push(["Subtotal", receipt.subtotal !== null ? receipt.subtotal : ""]);
    rows.push(["Tax", receipt.tax !== null ? receipt.tax : ""]);
    rows.push(["Tip", receipt.tip !== null ? receipt.tip : ""]);
    rows.push(["Discount", receipt.discount !== null ? receipt.discount : ""]);
    rows.push(["Total", receipt.total !== null ? receipt.total : ""]);
    rows.push(["Payment Method", receipt.payment_method || ""]);
    rows.push(["Notes", receipt.notes || ""]);
    rows.push([]);
    rows.push(["Line Item Name", "Quantity", "Unit Price", "Total"]);

    (receipt.line_items || []).forEach(item => {
      rows.push([item.name, item.quantity || "", item.unit_price || "", item.total || ""]);
    });

    const csvContent = "data:text/csv;charset=utf-8," + rows.map(e => e.map(val => `"${String(val).replace(/"/g, '""')}"`).join(",")).join("\n");
    const filename = `receipt_${(receipt.vendor_name || 'receipt').replace(/[^a-z0-9]/gi, '_').toLowerCase()}_${receipt.date || 'unknown'}.csv`;
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", encodeURI(csvContent));
    downloadAnchor.setAttribute("download", filename);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  }

  /**
   * Bulk CSV Download from Server
   */
  static downloadAllCSV(mode = 'flattened') {
    window.location.href = `/api/export/csv?mode=${mode}`;
  }

  /**
   * Bulk JSON Download from Server
   */
  static downloadAllJSON() {
    window.location.href = `/api/export/json`;
  }
}

window.ReceiptExporter = ReceiptExporter;
