import os
import base64

def generate_svg_receipt(title, subtitle, meta_lines, items, subtotal, tax_lines, tip, discount, total, currency="₹", footer_lines=None, is_blurry=False):
    filter_def = ""
    filter_attr = ""
    if is_blurry:
        filter_def = """
        <filter id="heavy-blur">
            <feGaussianBlur stdDeviation="7" />
        </filter>
        """
        filter_attr = 'filter="url(#heavy-blur)"'

    # Build SVG content
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 720" width="450" height="720" style="background:#ffffff; font-family: 'Courier New', Courier, monospace; color: #1e293b;">
    <defs>
        {filter_def}
        <pattern id="paper-texture" width="10" height="10" patternUnits="userSpaceOnUse">
            <rect width="10" height="10" fill="#fcfbf7" />
            <circle cx="2" cy="2" r="0.5" fill="#e2e8f0" opacity="0.4"/>
            <circle cx="7" cy="7" r="0.5" fill="#cbd5e1" opacity="0.3"/>
        </pattern>
        <filter id="paper-shadow" x="-5%" y="-5%" width="110%" height="110%">
            <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000000" flood-opacity="0.15" />
        </filter>
    </defs>
    
    <g {filter_attr} filter="url(#paper-shadow)">
        <!-- Receipt Paper -->
        <rect x="20" y="20" width="410" height="680" rx="4" fill="url(#paper-texture)" stroke="#e2e8f0" stroke-width="1.5" />
        
        <!-- Serrated top/bottom receipt edge simulation -->
        <path d="M 20 20 L 430 20 L 430 25 L 20 25 Z" fill="#f1f5f9" />
        
        <!-- Header -->
        <text x="225" y="65" text-anchor="middle" font-size="18" font-weight="bold" fill="#0f172a">{title}</text>
        <text x="225" y="85" text-anchor="middle" font-size="12" fill="#475569">{subtitle}</text>
    """
    
    y = 110
    for line in meta_lines:
        svg += f'<text x="225" y="{y}" text-anchor="middle" font-size="11" fill="#64748b">{line}</text>\n'
        y += 18
        
    y += 5
    svg += f'<line x1="40" y1="{y}" x2="410" y2="{y}" stroke="#0f172a" stroke-dasharray="4,3" stroke-width="1" />\n'
    y += 22
    
    # Table Header
    svg += f'<text x="45" y="{y}" font-size="11" font-weight="bold" fill="#0f172a">ITEM</text>\n'
    svg += f'<text x="260" y="{y}" text-anchor="end" font-size="11" font-weight="bold" fill="#0f172a">QTY</text>\n'
    svg += f'<text x="330" y="{y}" text-anchor="end" font-size="11" font-weight="bold" fill="#0f172a">PRICE</text>\n'
    svg += f'<text x="405" y="{y}" text-anchor="end" font-size="11" font-weight="bold" fill="#0f172a">TOTAL</text>\n'
    
    y += 8
    svg += f'<line x1="40" y1="{y}" x2="410" y2="{y}" stroke="#cbd5e1" stroke-width="1" />\n'
    y += 20
    
    # Items
    for item in items:
        name = item.get("name", "")
        if len(name) > 22:
            name = name[:20] + ".."
        qty = item.get("qty", 1)
        price = item.get("price", 0.0)
        tot = item.get("total", qty * price)
        svg += f'<text x="45" y="{y}" font-size="11" fill="#1e293b">{name}</text>\n'
        svg += f'<text x="260" y="{y}" text-anchor="end" font-size="11" fill="#334155">{qty}</text>\n'
        svg += f'<text x="330" y="{y}" text-anchor="end" font-size="11" fill="#334155">{currency}{price:.2f}</text>\n'
        svg += f'<text x="405" y="{y}" text-anchor="end" font-size="11" font-weight="bold" fill="#0f172a">{currency}{tot:.2f}</text>\n'
        y += 20
        
    y += 5
    svg += f'<line x1="40" y1="{y}" x2="410" y2="{y}" stroke="#cbd5e1" stroke-width="1" />\n'
    y += 22
    
    # Subtotal
    svg += f'<text x="45" y="{y}" font-size="11" fill="#475569">Subtotal:</text>\n'
    svg += f'<text x="405" y="{y}" text-anchor="end" font-size="11" fill="#1e293b">{currency}{subtotal:.2f}</text>\n'
    y += 18
    
    # Tax lines
    for t_name, t_val in tax_lines:
        svg += f'<text x="45" y="{y}" font-size="11" fill="#475569">{t_name}:</text>\n'
        svg += f'<text x="405" y="{y}" text-anchor="end" font-size="11" fill="#1e293b">{currency}{t_val:.2f}</text>\n'
        y += 18
        
    if tip > 0:
        svg += f'<text x="45" y="{y}" font-size="11" fill="#475569">Tip / Gratuity:</text>\n'
        svg += f'<text x="405" y="{y}" text-anchor="end" font-size="11" fill="#1e293b">{currency}{tip:.2f}</text>\n'
        y += 18
        
    if discount > 0:
        svg += f'<text x="45" y="{y}" font-size="11" fill="#16a34a">Store Discount:</text>\n'
        svg += f'<text x="405" y="{y}" text-anchor="end" font-size="11" fill="#16a34a">-{currency}{discount:.2f}</text>\n'
        y += 18
        
    y += 8
    svg += f'<line x1="40" y1="{y}" x2="410" y2="{y}" stroke="#0f172a" stroke-width="1.5" />\n'
    y += 24
    
    # Grand Total
    svg += f'<text x="45" y="{y}" font-size="15" font-weight="bold" fill="#0f172a">GRAND TOTAL:</text>\n'
    svg += f'<text x="405" y="{y}" text-anchor="end" font-size="16" font-weight="bold" fill="#0f172a">{currency}{total:.2f}</text>\n'
    y += 25
    
    svg += f'<line x1="40" y1="{y}" x2="410" y2="{y}" stroke="#cbd5e1" stroke-dasharray="3,3" stroke-width="1" />\n'
    y += 22
    
    if footer_lines:
        for f in footer_lines:
            svg += f'<text x="225" y="{y}" text-anchor="middle" font-size="10" fill="#64748b">{f}</text>\n'
            y += 16
            
    # Barcode simulation at bottom
    svg += f"""
        <g transform="translate(130, {y + 10})">
            <rect x="0" y="0" width="3" height="30" fill="#0f172a" />
            <rect x="6" y="0" width="2" height="30" fill="#0f172a" />
            <rect x="12" y="0" width="4" height="30" fill="#0f172a" />
            <rect x="20" y="0" width="2" height="30" fill="#0f172a" />
            <rect x="26" y="0" width="5" height="30" fill="#0f172a" />
            <rect x="35" y="0" width="2" height="30" fill="#0f172a" />
            <rect x="42" y="0" width="4" height="30" fill="#0f172a" />
            <rect x="50" y="0" width="1" height="30" fill="#0f172a" />
            <rect x="56" y="0" width="6" height="30" fill="#0f172a" />
            <rect x="68" y="0" width="2" height="30" fill="#0f172a" />
            <rect x="74" y="0" width="3" height="30" fill="#0f172a" />
            <rect x="82" y="0" width="5" height="30" fill="#0f172a" />
            <rect x="92" y="0" width="2" height="30" fill="#0f172a" />
            <rect x="98" y="0" width="4" height="30" fill="#0f172a" />
            <rect x="108" y="0" width="3" height="30" fill="#0f172a" />
            <rect x="116" y="0" width="5" height="30" fill="#0f172a" />
            <rect x="126" y="0" width="2" height="30" fill="#0f172a" />
            <rect x="134" y="0" width="4" height="30" fill="#0f172a" />
            <rect x="144" y="0" width="6" height="30" fill="#0f172a" />
            <rect x="156" y="0" width="2" height="30" fill="#0f172a" />
            <rect x="164" y="0" width="5" height="30" fill="#0f172a" />
            <rect x="174" y="0" width="2" height="30" fill="#0f172a" />
            <rect x="180" y="0" width="4" height="30" fill="#0f172a" />
        </g>
    """
    
    svg += "</g>\n</svg>"
    return svg

def create_all_samples():
    out_dir = "/Users/lavanyaadabala/Downloads/receiptlens/static/samples"
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. Indian Restaurant
    s1 = generate_svg_receipt(
        title="SARAVANA BHAVAN",
        subtitle="Pure Vegetarian South & North Indian Cuisine",
        meta_lines=[
            "Connaught Place, New Delhi - 110001",
            "Ph: +91 11 2341 7890 | GSTIN: 07AAAAA0000A1Z5",
            "Date: 28/09/2026 20:45 | Table: 14 | Bill: #SB-9842"
        ],
        items=[
            {"name": "Masala Dosa Special", "qty": 2, "price": 160.00, "total": 320.00},
            {"name": "Paneer Butter Masala", "qty": 1, "price": 280.00, "total": 280.00},
            {"name": "Butter Naan (Basket)", "qty": 3, "price": 50.00, "total": 150.00},
            {"name": "South Indian Filter Coffee", "qty": 2, "price": 50.00, "total": 100.00}
        ],
        subtotal=850.00,
        tax_lines=[("CGST @ 2.5%", 21.25), ("SGST @ 2.5%", 21.25)],
        tip=50.00,
        discount=0.0,
        total=942.50,
        currency="₹",
        footer_lines=["Payment Mode: UPI / GPay (Txn: 48192831)", "Thank You! Please Visit Again!"]
    )
    with open(os.path.join(out_dir, "demo_indian_bhavan.svg"), "w") as f:
        f.write(s1)
        
    # 2. Supermarket Groceries
    s2 = generate_svg_receipt(
        title="NATURE'S BASKET",
        subtitle="Organic & Gourmet Supermarket",
        meta_lines=[
            "Indiranagar 100ft Road, Bengaluru - 560038",
            "Tel: +91 80 4123 5566 | GST: 29AABCN8899K1Z4",
            "Date: 02/10/2026 14:15 | Cashier: #08 | Inv: NB-4819"
        ],
        items=[
            {"name": "Aashirvaad Shudh Chakki Atta 5kg", "qty": 1, "price": 295.00, "total": 295.00},
            {"name": "Organic Alphonso Mango Pulp 850g", "qty": 2, "price": 225.00, "total": 450.00},
            {"name": "Fortune Sunlite Sunflower Oil 1L", "qty": 2, "price": 160.00, "total": 320.00},
            {"name": "Amul Pasteurised Butter 500g", "qty": 1, "price": 275.00, "total": 275.00},
            {"name": "Broccoli Exotic 500g", "qty": 1, "price": 80.00, "total": 80.00}
        ],
        subtotal=1420.00,
        tax_lines=[("CGST @ 2.5%", 35.50), ("SGST @ 2.5%", 35.50)],
        tip=0.0,
        discount=50.00,
        total=1441.00,
        currency="₹",
        footer_lines=["Member Card: NB-7721 (Earned 45 Pts)", "Paid via HDFC Credit Card **** 4019"]
    )
    with open(os.path.join(out_dir, "demo_supermarket_groceries.svg"), "w") as f:
        f.write(s2)

    # 3. Uber Travel
    s3 = generate_svg_receipt(
        title="UBER INDIA SYSTEMS",
        subtitle="E-Receipt / Tax Invoice",
        meta_lines=[
            "Uber India Pvt Ltd | GSTIN: 27AABCV8901L1Z9",
            "Trip Date: 03/10/2026 18:30",
            "Pickup: BKC | Drop: Mumbai Airport T2"
        ],
        items=[
            {"name": "Uber Premier Airport Drop (28.4 km)", "qty": 1, "price": 580.00, "total": 580.00},
            {"name": "Airport Toll & Parking Surcharge", "qty": 1, "price": 100.00, "total": 100.00}
        ],
        subtotal=680.00,
        tax_lines=[("CGST @ 2.5%", 17.00), ("SGST @ 2.5%", 17.00)],
        tip=40.00,
        discount=0.0,
        total=754.00,
        currency="₹",
        footer_lines=["Driver: Rajesh Kumar | Vehicle: Swift Dzire", "Payment: Amazon Pay Balance"]
    )
    with open(os.path.join(out_dir, "demo_travel_uber.svg"), "w") as f:
        f.write(s3)

    # 4. Electronics Croma
    s4 = generate_svg_receipt(
        title="CROMA DIGITAL",
        subtitle="Infiniti Retail Limited - A Tata Enterprise",
        meta_lines=[
            "Phoenix Marketcity, Kurla, Mumbai - 400070",
            "GSTIN: 27AACCC1122D1Z0 | Ph: +91 22 6180 1200",
            "Invoice: CR-9912 | Date: 15/09/2026"
        ],
        items=[
            {"name": "SanDisk 1TB Extreme Portable SSD", "qty": 1, "price": 3499.00, "total": 3499.00},
            {"name": "Anker 65W GaN Fast Charger USB-C", "qty": 1, "price": 701.00, "total": 701.00}
        ],
        subtotal=4200.00,
        tax_lines=[("CGST @ 9%", 378.00), ("SGST @ 9%", 378.00)],
        tip=0.0,
        discount=200.00,
        total=4756.00,
        currency="₹",
        footer_lines=["1 Year Manufacturer Warranty Included", "Paid: ICICI Debit Card **** 9182"]
    )
    with open(os.path.join(out_dir, "demo_electronics_gadget.svg"), "w") as f:
        f.write(s4)

    # 5. Mismatch Cafe
    s5 = generate_svg_receipt(
        title="CAFE MOCHA DELUXE",
        subtitle="Artisan Roastery & Bakery",
        meta_lines=[
            "Bandra West, Mumbai - 400050",
            "Date: 04/10/2026 | Table #04 | Cashier: Neil"
        ],
        items=[
            {"name": "Hazelnut Cappuccino", "qty": 2, "price": 180.00, "total": 360.00},
            {"name": "Belgian Chocolate Croissant", "qty": 1, "price": 160.00, "total": 160.00}
        ],
        subtotal=520.00,
        tax_lines=[("CGST @ 2.5%", 13.00), ("SGST @ 2.5%", 13.00)],
        tip=20.00,
        discount=0.0,
        total=620.00, # Math discrepancy intentionally: 520 + 26 + 20 = 566 != 620
        currency="₹",
        footer_lines=["* Handwritten manual adjustment fee *", "Paid by Cash"]
    )
    with open(os.path.join(out_dir, "demo_mismatch_receipt.svg"), "w") as f:
        f.write(s5)

    # 6. Blurry rejection sample
    s6 = generate_svg_receipt(
        title="UNREADABLE RECEIPT",
        subtitle="Sample Blurry Document for Error Handling",
        meta_lines=["[BLURRY TEXT]", "[MOTION BLUR ARTIFACT]"],
        items=[{"name": "Unknown Scrambled Line", "qty": 1, "price": 99.0, "total": 99.0}],
        subtotal=99.0,
        tax_lines=[("TAX", 5.0)],
        tip=0.0,
        discount=0.0,
        total=104.0,
        currency="₹",
        footer_lines=["Image quality too degraded for OCR/AI extraction"],
        is_blurry=True
    )
    with open(os.path.join(out_dir, "demo_blurry_rejection.svg"), "w") as f:
        f.write(s6)

    print("SVG demo sample receipts created.")

if __name__ == "__main__":
    create_all_samples()
