// ReceiptLens - Analytics & Dashboard Controller

class ReceiptDashboard {
  constructor() {
    this.monthlyChart = null;
    this.categoryChart = null;
    this.currencySymbol = '₹';
  }

  async loadStats() {
    try {
      const resp = await fetch('/api/stats');
      if (!resp.ok) throw new Error('Failed to fetch stats');
      const data = await resp.json();
      this.renderOverview(data.overview);
      this.renderMonthlySpendingChart(data.monthly_spending);
      this.renderCategoryChart(data.category_spending);
      this.renderTopVendors(data.top_vendors);
    } catch (err) {
      console.error('Error loading dashboard stats:', err);
    }
  }

  renderOverview(overview) {
    if (!overview) return;

    const totalSpendEl = document.getElementById('stat-total-spend');
    const totalReceiptsEl = document.getElementById('stat-total-receipts');
    const avgSpendEl = document.getElementById('stat-avg-spend');
    const flaggedCountEl = document.getElementById('stat-flagged-count');

    if (totalSpendEl) totalSpendEl.textContent = `${this.currencySymbol}${Number(overview.total_spend || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (totalReceiptsEl) totalReceiptsEl.textContent = overview.total_receipts || 0;
    if (avgSpendEl) avgSpendEl.textContent = `${this.currencySymbol}${Number(overview.avg_spend || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (flaggedCountEl) {
      flaggedCountEl.textContent = overview.flagged_count || 0;
      if (overview.flagged_count > 0) {
        flaggedCountEl.classList.add('text-rose');
      } else {
        flaggedCountEl.classList.remove('text-rose');
      }
    }
  }

  renderMonthlySpendingChart(monthlyData) {
    const canvas = document.getElementById('chart-monthly-spending');
    if (!canvas) return;

    // Categories list
    const categories = ['Food', 'Groceries', 'Travel', 'Shopping', 'Utilities', 'Other'];
    const categoryColors = {
      Food: '#f59e0b',
      Groceries: '#10b981',
      Travel: '#06b6d4',
      Shopping: '#a855f7',
      Utilities: '#eab308',
      Other: '#94a3b8'
    };

    // Extract unique months sorted
    const monthsSet = new Set();
    monthlyData.forEach(d => {
      if (d.month_key) monthsSet.add(d.month_key);
    });
    
    // If no months or few, provide sample current month
    if (monthsSet.size === 0) {
      const currentMonth = new Date().toISOString().substring(0, 7);
      monthsSet.add(currentMonth);
    }

    const months = Array.from(monthsSet).sort();

    // Build datasets per category
    const datasets = categories.map(cat => {
      const data = months.map(m => {
        const entry = monthlyData.find(d => d.month_key === m && d.category === cat);
        return entry ? entry.amount : 0;
      });
      return {
        label: cat,
        data: data,
        backgroundColor: categoryColors[cat] || '#6366f1',
        borderRadius: 4
      };
    });

    if (this.monthlyChart) {
      this.monthlyChart.destroy();
    }

    this.monthlyChart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: months.map(m => {
          const [yr, mo] = m.split('-');
          const d = new Date(parseInt(yr), parseInt(mo) - 1, 1);
          return d.toLocaleString('default', { month: 'short', year: '2-digit' });
        }),
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } }
          },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ₹${Number(ctx.parsed.y).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
            }
          }
        },
        scales: {
          x: {
            stacked: true,
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#64748b' }
          },
          y: {
            stacked: true,
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: {
              color: '#64748b',
              callback: (v) => `₹${v}`
            }
          }
        }
      }
    });
  }

  renderCategoryChart(categoryData) {
    const canvas = document.getElementById('chart-category-distribution');
    if (!canvas) return;

    const categoryColors = {
      Food: '#f59e0b',
      Groceries: '#10b981',
      Travel: '#06b6d4',
      Shopping: '#a855f7',
      Utilities: '#eab308',
      Other: '#94a3b8'
    };

    const labels = categoryData.map(c => c.category);
    const amounts = categoryData.map(c => c.total_amount);
    const colors = labels.map(l => categoryColors[l] || '#6366f1');

    if (this.categoryChart) {
      this.categoryChart.destroy();
    }

    if (labels.length === 0) {
      labels.push('No Data');
      amounts.push(1);
      colors.push('#334155');
    }

    this.categoryChart = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: amounts,
          backgroundColor: colors,
          borderWidth: 0,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } }
          },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.label}: ₹${Number(ctx.parsed).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
            }
          }
        },
        cutout: '70%'
      }
    });
  }

  renderTopVendors(vendors) {
    const container = document.getElementById('top-vendors-list');
    if (!container) return;

    if (!vendors || vendors.length === 0) {
      container.innerHTML = '<div class="text-muted" style="text-align:center; padding: 2rem;">No vendor data recorded yet.</div>';
      return;
    }

    container.innerHTML = vendors.map(v => `
      <div class="vendor-item">
        <div class="vendor-info">
          <div class="vendor-info-name">${v.vendor || 'Unknown Store'}</div>
          <div class="vendor-visits">${v.visit_count} receipt${v.visit_count > 1 ? 's' : ''}</div>
        </div>
        <div class="vendor-spend">${this.currencySymbol}${Number(v.total_spend).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
      </div>
    `).join('');
  }
}

window.ReceiptDashboard = ReceiptDashboard;
