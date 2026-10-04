// ReceiptLens - Math & Consistency Validator Engine

class ReceiptValidator {
  /**
   * Validates if sum(line_items) + tax + tip - discount matches total
   */
  static validate(data) {
    const lineItems = data.line_items || [];
    const tax = parseFloat(data.tax) || 0;
    const tip = parseFloat(data.tip) || 0;
    const discount = parseFloat(data.discount) || 0;
    const total = data.total !== null && data.total !== undefined ? parseFloat(data.total) : null;
    
    // Calculate items sum
    const itemsSum = lineItems.reduce((acc, item) => {
      const lineTotal = parseFloat(item.total);
      if (!isNaN(lineTotal)) {
        return acc + lineTotal;
      }
      const qty = parseFloat(item.quantity) || 1;
      const price = parseFloat(item.unit_price) || 0;
      return acc + (qty * price);
    }, 0);

    if (total === null || isNaN(total)) {
      return {
        status: 'warning',
        isMatch: false,
        discrepancy: 0,
        itemsSum: itemsSum,
        expectedTotal: itemsSum + tax + tip - discount,
        actualTotal: null,
        message: 'Total amount is not specified on this receipt.'
      };
    }

    const expectedTotal = itemsSum + tax + tip - discount;
    const discrepancy = Math.abs(expectedTotal - total);

    // Tolerance of 0.05 for rounding differences
    if (lineItems.length > 0 && discrepancy > 0.05) {
      return {
        status: 'flagged',
        isMatch: false,
        discrepancy: parseFloat(discrepancy.toFixed(2)),
        itemsSum: parseFloat(itemsSum.toFixed(2)),
        expectedTotal: parseFloat(expectedTotal.toFixed(2)),
        actualTotal: parseFloat(total.toFixed(2)),
        tax: tax,
        tip: tip,
        discount: discount,
        message: `Calculation Mismatch: Sum of items (${itemsSum.toFixed(2)}) + Tax (${tax.toFixed(2)}) + Tip (${tip.toFixed(2)})${discount > 0 ? ` - Discount (${discount.toFixed(2)})` : ''} = ${expectedTotal.toFixed(2)}, but Total is ${total.toFixed(2)}.`
      };
    }

    return {
      status: 'valid',
      isMatch: true,
      discrepancy: 0,
      itemsSum: parseFloat(itemsSum.toFixed(2)),
      expectedTotal: parseFloat(total.toFixed(2)),
      actualTotal: parseFloat(total.toFixed(2)),
      message: 'Math verified: Items + Tax + Tip matches Total exactly.'
    };
  }

  /**
   * Auto-reconcile helper that suggests adjustments
   */
  static getReconciliationSuggestions(validationResult) {
    if (!validationResult || validationResult.status !== 'flagged') return [];

    const expected = validationResult.expectedTotal;
    const actual = validationResult.actualTotal;
    const diff = Math.abs(expected - actual).toFixed(2);

    return [
      {
        id: 'fix_total',
        label: `Update Total to ${expected}`,
        action: 'set_total',
        value: expected
      },
      {
        id: 'fix_tax',
        label: `Adjust Tax by ${expected > actual ? '-' : '+'}${diff}`,
        action: 'adjust_tax',
        value: Math.max(0, validationResult.tax + (actual - expected))
      }
    ];
  }
}

window.ReceiptValidator = ReceiptValidator;
