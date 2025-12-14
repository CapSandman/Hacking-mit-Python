from io import BytesIO
from decimal import Decimal
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---- Font registration (Gothic Sans) ----
def _register_fonts():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(os.path.dirname(base_dir), "app","static")
    reg_path = os.path.join(fonts_dir, "GOTHIC.ttf")
    bold_path = os.path.join(fonts_dir, "GOTHICB.ttf")

    assert os.path.isfile(reg_path), f"Font not found: {reg_path}"
    assert os.path.isfile(bold_path), f"Font not found: {bold_path}"

    pdfmetrics.registerFont(TTFont("GOTHIC", reg_path))
    pdfmetrics.registerFont(TTFont("GOTHICB", bold_path))
    pdfmetrics.registerFontFamily('GOTHIC',
        normal='GOTHIC', bold='GOTHICB',
        italic='GOTHIC', boldItalic='GOTHICB')

    return "GOTHIC", "GOTHICB"

FONT_REG, FONT_BOLD = _register_fonts()

def _fmt_money(x, places=2):
    try:
        return f"{float(x):,.{places}f}"
    except Exception:
        return f"{x}"

class HR(Flowable):
    """Horizontal rule."""
    def __init__(self, width, thickness=0.5, color=colors.HexColor("#DDDDDD")):
        super().__init__()
        self.width = width; self.thickness = thickness; self.color = color
        self.height = thickness
    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)

def generate_invoice_pdf(*, invoice, items, site,
                         rate_bam_per_eur: float, pdv_percent: float,
                         logo_path: str | None = None,
                         seller: dict | None = None,
                         buyer: dict | None = None):
    """
    Uljepšani PDF: veći logo, Century Gothic, footer s Matični/JIB/IBAN/SWIFT + page.
    """
    seller = seller or {}
    buyer  = buyer or {}

    # footer company ids from env
    REG_NO   = os.getenv("COMPANY_REG_NO", "")
    JIB      = os.getenv("COMPANY_JIB", "")
    IBAN_BAM = os.getenv("COMPANY_IBAN_BAM", "")
    IBAN_EUR = os.getenv("COMPANY_IBAN_EUR", "")
    SWIFT    = os.getenv("COMPANY_SWIFT", "")

    buf = BytesIO()
    # malo veći bottom margin da footer stane lijepo
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=30*mm, bottomMargin=22*mm
    )
    styles = getSampleStyleSheet()

    # styles override to use Century Gothic
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName=FONT_BOLD, fontSize=16, spaceAfter=6)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName=FONT_BOLD, fontSize=12, spaceAfter=3)
    P  = ParagraphStyle("P",  parent=styles["Normal"],   fontName=FONT_REG,  fontSize=9,  leading=11, spaceAfter=30)

    elems: list = []

    # --- HEADER/FOOTER drawer ---
    class HeaderFooter:
        def __init__(self, logo_path, seller, site, invoice):
            self.logo_path = logo_path
            self.seller = seller
            self.site = site
            self.invoice = invoice

        def __call__(self, canv, doc):
            W, H = A4
            # Header: veći logo
            if self.logo_path:
                try:
                    # 30 mm visina, širinu proporcionalno
                    canv.drawImage(
                        self.logo_path,
                        doc.leftMargin, H - 35*mm,  # malo više prema gore
                        width=45*mm, height=45*mm,  # VEĆI LOGO
                        preserveAspectRatio=True,
                        mask='auto'
                    )

                except Exception:
                    pass
            canv.setFont(FONT_BOLD, 13)
            canv.drawString(doc.leftMargin + 45*mm, H-12*mm, "FAKTURA (PPA/Billing)")
            canv.setFont(FONT_REG, 9)
            canv.drawString(doc.leftMargin + 45*mm, H-17*mm, f"Elektrana: {self.site.name}")
            canv.drawString(doc.leftMargin + 45*mm, H-21*mm, f"Period: {self.invoice.period_start} – {self.invoice.period_end}")
            canv.drawRightString(W - doc.rightMargin, H-14*mm, f"Invoice ID: {self.invoice.id}")

            # separator
            canv.setStrokeColor(colors.HexColor("#DDDDDD"))
            canv.setLineWidth(0.7)
            canv.line(doc.leftMargin, H-26*mm, W - doc.rightMargin, H-26*mm)

            # Footer: firm identifiers (left) + page (right)
            canv.setFont(FONT_REG, 8.5)
            footer_y = 14*mm
            left_x = doc.leftMargin
            line1 = f"Matični: {REG_NO}   JIB: {JIB}"
            line2 = f"ŽR (KM): {IBAN_BAM}   ŽR (EUR): {IBAN_EUR}   SWIFT: {SWIFT}"
            canv.setFillColor(colors.HexColor("#555555"))
            canv.drawString(left_x, footer_y, line1)
            canv.drawString(left_x, footer_y - 4.5*mm, line2)
            canv.setFillColor(colors.HexColor("#777777"))
            canv.drawRightString(W - doc.rightMargin, footer_y, f"Page {canv.getPageNumber()}")

    # --- Seller / Buyer block ---
    elems.append(Spacer(1, 4*mm))
    seller_table = Table([
        [Paragraph("<b>Prodavac</b>", H2), Paragraph("<b>Kupac</b>", H2)],
        [Paragraph(seller.get("name",""), P), Paragraph(buyer.get("name",""), P)],
        [Paragraph(seller.get("addr",""), P), Paragraph(buyer.get("addr",""), P)],
        [Paragraph(seller.get("email",""),  P), Paragraph(buyer.get("vat",""),  P)],
        [Paragraph(seller.get("phone",""), P), Paragraph(buyer.get("email",""),P)],
    ], colWidths=[(doc.width/2)-4*mm, (doc.width/2)-4*mm])
    seller_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("FONTNAME", (0,0), (-1,-1), FONT_REG),
        ("FONTSIZE", (0,0), (-1,-1), 9),
    ]))
    elems.append(seller_table)
    elems.append(Spacer(1, 2*mm))
    elems.append(HR(doc.width))

    # --- Hourly table ---
    data = [["Sat", "Energija (MWh)", "Jed. cijena (€/MWh)", "Iznos (EUR)", "Iznos (KM)"]]
    total_eur = Decimal("0")
    for it in items:
        e = Decimal(str(it.energy_mwh))
        unit = Decimal(str(it.unit_price_eur_mwh))
        amt_eur = Decimal(str(it.line_amount_eur))
        amt_km  = (amt_eur * Decimal(str(rate_bam_per_eur)))
        total_eur += amt_eur
        data.append([
            it.ts.strftime("%Y-%m-%d %H:00"),
            f"{e:.6f}", f"{unit:.4f}", f"{amt_eur:.4f}", f"{amt_km:.4f}"
        ])

    table = Table(data, colWidths=[30*mm, 30*mm, 35*mm, 35*mm, 35*mm], repeatRows=1)
    ts = [
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#CCCCCC")),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F5F7FA")),
        ("FONTNAME", (0,0), (-1,0), FONT_BOLD),
        ("FONTNAME", (0,1), (-1,-1), FONT_REG),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]
    for r in range(1, len(data)):
        if r % 2 == 0:
            ts.append(("BACKGROUND", (0,r), (-1,r), colors.HexColor("#FBFCFE")))
    table.setStyle(TableStyle(ts))
    elems.append(Spacer(1, 4*mm))
    elems.append(table)
    elems.append(Spacer(1, 6*mm))

    # --- Totals box ---
    total_km_net = total_eur * Decimal(str(rate_bam_per_eur))
    pdv_amount   = total_km_net * Decimal(str(pdv_percent/100.0))
    grand_total  = total_km_net + pdv_amount

    totals = [
        ["Ukupno (EUR)", _fmt_money(total_eur, 2)],
        [f"Ukupno (KM)    Kurs: {rate_bam_per_eur:.5f}", _fmt_money(total_km_net, 2)],
        [f"PDV {pdv_percent:.0f}%", _fmt_money(pdv_amount, 2)],
        ["ZA PLATITI (KM)", _fmt_money(grand_total, 2)],
    ]
    totals_tbl = Table(totals, colWidths=[70*mm, 40*mm])
    totals_tbl.setStyle(TableStyle([
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("FONTNAME", (0,0), (-1,-1), FONT_REG),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#EAF7EA")),
        ("FONTNAME", (0,-1), (-1,-1), FONT_BOLD),
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#A3D9A5")),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#CFEACF")),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    totals_wrap = Table([[Spacer(1,0), totals_tbl]], colWidths=[doc.width-112*mm, 112*mm])
    totals_wrap.setStyle(TableStyle([("VALIGN", (1,0), (1,0), "TOP")]))
    elems.append(totals_wrap)
    elems.append(Spacer(1, 4*mm))

    note1 = Paragraph(
        "Napomena: Obračun baziran na satnim PPA pravilima i CROPEX cijenama (ako primjenjivo). \n"
        "Konverzija EUR→KM prema važećem kursu dana. PDV obračunat prema propisima.\n",
        P
    )
    elems.append(note1)

    note2 = Paragraph(
        "Faktura je kreirana elektronskim putem i punovažna je bez potpisa i pečata",
        P
    )
    elems.append(note2)

    header_footer = HeaderFooter(logo_path, seller, site, invoice)
    doc.build(elems, onFirstPage=header_footer, onLaterPages=header_footer)
    buf.seek(0)
    return buf
