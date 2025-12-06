"""
pdf_generator.py
Platypus-based PDF generator (formatted layout) that also remains compatible with
older task code that may call it with upload_to_cloudinary=True.

Behavior:
- By default generate_visit_pdf(visit_info, processed_items, output_dir) returns (pdf_path, pdf_filename)
- If called with upload_to_cloudinary=True and Cloudinary SDK/config is available, the function will upload
  the produced PDF as a raw resource and attempt to return a signed download URL.
  In that case it returns (pdf_path, pdf_filename, signed_pdf_url_or_None)

This file is a backwards-compatible update to accept the optional keyword args that
existing tasks.py may pass (upload_to_cloudinary, cloudinary_folder, public_id_prefix).
"""
import os
import time
import tempfile
import logging
from io import BytesIO
from datetime import datetime

import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# Cloudinary optional imports + compatibility for download_url
try:
    import cloudinary.uploader
    try:
        from cloudinary.utils import download_url  # type: ignore
        _HAS_DOWNLOAD_URL = True
    except Exception:
        try:
            from cloudinary.utils import cloudinary_url as _cloudinary_url  # type: ignore
            _HAS_DOWNLOAD_URL = False
        except Exception:
            _cloudinary_url = None
            _HAS_DOWNLOAD_URL = False
    _HAS_CLOUDINARY = True
except Exception:
    _HAS_CLOUDINARY = False
    _HAS_DOWNLOAD_URL = False
    _cloudinary_url = None

def _download_url_fallback(public_id, resource_type='raw', sign_url=True, attachment=True, **kwargs):
    """
    Build a signed URL using cloudinary_url when download_url is not present.
    Returns URL string or None on failure.
    """
    if _cloudinary_url is None:
        return None
    options = dict(resource_type=resource_type, sign_url=sign_url)
    if attachment:
        options['attachment'] = True
    try:
        url, _opts = _cloudinary_url(public_id, **options)
        return url
    except Exception as e:
        logger.warning(f"_download_url_fallback failed for {public_id}: {e}")
        return None

# Provide download_url name for later usage (either real or fallback)
if _HAS_DOWNLOAD_URL:
    # download_url is available
    pass
else:
    download_url = _download_url_fallback  # type: ignore

# --- CONFIGURATION & BRANDING ---
BRAND_COLOR = colors.HexColor('#198754')
ACCENT_BG_COLOR = colors.HexColor('#F2FBF8')
GRID_COLOR = colors.HexColor('#CCCCCC')

LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'INJAAZ.png')

# Initialize styles
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name='BoldTitle',
    fontName='Helvetica-Bold',
    fontSize=14,
    leading=16,
    textColor=BRAND_COLOR,
    spaceAfter=0.1 * inch
))
styles.add(ParagraphStyle(name='Question', fontName='Helvetica-Bold', fontSize=10, leading=12))
styles.add(ParagraphStyle(name='Answer', fontName='Helvetica', fontSize=10, leading=12))
styles.add(ParagraphStyle(name='SmallText', fontName='Helvetica', fontSize=8, leading=10))

# Timeout for HTTP requests when fetching images
HTTP_TIMEOUT = 20  # seconds

def _fetch_image_bytes(url):
    """Fetch image bytes from a URL with timeout. Returns BytesIO or None on failure."""
    try:
        resp = requests.get(url, stream=True, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return BytesIO(resp.content)
    except Exception as e:
        logger.warning(f"Failed to fetch image {url}: {e}")
        return None

def _bytesio_to_reportlab_image(bio, width, height):
    """
    Try to create a reportlab.platypus.Image from a BytesIO. If direct creation fails,
    write to a temp file and return Image(tempfile).
    """
    try:
        bio.seek(0)
        PILImage.open(bio).verify()
        bio.seek(0)
        img = Image(bio, width=width, height=height)
        img.hAlign = 'CENTER'
        return img
    except Exception as e:
        logger.warning(f"BytesIO to Image failed, falling back to temp file: {e}")
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(bio.getvalue())
            tmp.flush()
            tmp.close()
            img = Image(tmp.name, width=width, height=height)
            img.hAlign = 'CENTER'
            return img
        except Exception as e2:
            logger.error(f"Failed to create Image from temp file: {e2}")
            return Paragraph(f'<font size="8">Image Error</font>', styles['SmallText'])

def get_image_element(source, width, height, placeholder_text="No Photo"):
    """
    Accepts:
      - source: None / local filepath / URL / BytesIO
    Returns a ReportLab flowable (Image or Paragraph placeholder).
    """
    if not source:
        return Paragraph(f'<font size="8">{placeholder_text}</font>', styles['SmallText'])

    # If source is a BytesIO already
    if isinstance(source, BytesIO):
        return _bytesio_to_reportlab_image(source, width, height)

    # If source looks like a URL
    if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
        bio = _fetch_image_bytes(source)
        if not bio:
            return Paragraph(f'<font size="8">Image Load Failed</font>', styles['SmallText'])
        return _bytesio_to_reportlab_image(bio, width, height)

    # Otherwise assume it's a local path
    if isinstance(source, str) and os.path.exists(source):
        try:
            img = Image(source, width=width, height=height)
            img.hAlign = 'CENTER'
            return img
        except Exception as e:
            logger.warning(f"Failed to load local image {source}: {e}")
            try:
                with open(source, 'rb') as f:
                    bio = BytesIO(f.read())
                return _bytesio_to_reportlab_image(bio, width, height)
            except Exception:
                return Paragraph(f'<font size="8">Image Error</font>', styles['SmallText'])

    return Paragraph(f'<font size="8">Image Not Available</font>', styles['SmallText'])

def get_sig_image_from_source(source, name):
    """Return an Image flowable sized for signatures, or a Paragraph if missing."""
    if source and (isinstance(source, str) and (source.startswith('http://') or source.startswith('https://'))):
        bio = _fetch_image_bytes(source)
        if bio:
            try:
                return _bytesio_to_reportlab_image(bio, width=2.5 * inch, height=0.7 * inch)
            except Exception:
                pass
    if source and isinstance(source, str) and os.path.exists(source):
        try:
            img = Image(source)
            img.drawWidth = 2.5 * inch
            img.drawHeight = 0.7 * inch
            img.hAlign = 'LEFT'
            return img
        except Exception:
            pass
    if isinstance(source, BytesIO):
        return _bytesio_to_reportlab_image(source, width=2.5 * inch, height=0.7 * inch)

    return Paragraph(f'Unsigned: {name}', styles['Normal'])

FOOTER_TEXT = "PO BOX, 3456 Ajman, UAE | Tel +971 6 7489813 | Fax +971 6 711 6701 | www.injaaz.ae | Member of Ajman Holding group"

def page_layout_template(canvas, doc):
    """Draw footer on each page."""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#666666'))
    footer_y = doc.bottomMargin - 0.25 * inch
    canvas.drawCentredString(A4[0] / 2, footer_y, FOOTER_TEXT)
    canvas.setStrokeColor(GRID_COLOR)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, footer_y + 0.15 * inch, A4[0] - doc.rightMargin, footer_y + 0.15 * inch)
    canvas.drawRightString(A4[0] - doc.rightMargin, footer_y, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()

def create_signature_table(visit_info):
    """Create signature block using signature sources in visit_info."""
    sig_story = []
    sig_story.append(Spacer(1, 0.15 * inch))
    sig_story.append(Paragraph('4. Signatures', styles['BoldTitle']))
    sig_story.append(Spacer(1, 0.05 * inch))

    # Accept either local path keys or cloudinary url keys
    tech_sig_source = visit_info.get('tech_signature_path') or visit_info.get('tech_signature_url')
    opman_sig_source = visit_info.get('opMan_signature_path') or visit_info.get('opMan_signature_url')

    tech_sig = get_sig_image_from_source(tech_sig_source, 'Technician')
    opman_sig = get_sig_image_from_source(opman_sig_source, 'Operation Manager')

    tech_name = visit_info.get('technician_name', 'N/A')
    opman_name = visit_info.get('opMan_name', 'N/A')

    signature_data = [
        [tech_sig, opman_sig],
        [Paragraph('<font size="10">_________________________</font>', styles['Normal']),
         Paragraph('<font size="10">_________________________</font>', styles['Normal'])],
        [Paragraph(f"<font size='10'><b>Technician:</b> {tech_name}</font>", styles['Normal']),
         Paragraph(f"<font size='10'><b>Operation Manager:</b> {opman_name}</font>", styles['Normal'])]
    ]

    signature_table = Table(signature_data, colWidths=[3.75 * inch, 3.75 * inch],
                            rowHeights=[0.8 * inch, 0.12 * inch, 0.22 * inch])
    TEXT_SHIFT_PADDING = 15
    signature_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 1), (-1, -1), TEXT_SHIFT_PADDING),
    ]))

    sig_story.append(signature_table)
    return sig_story

def build_report_story(visit_info, processed_items):
    """Assemble the Platypus story for the PDF."""
    story = []

    # Header and logo
    title_text = f"Site Visit Report - {visit_info.get('building_name', 'N/A')}"
    title_paragraph = Paragraph(title_text, styles['BoldTitle'])

    logo = Paragraph('', styles['Normal'])
    try:
        if os.path.exists(LOGO_PATH):
            logo = Image(LOGO_PATH)
            logo.drawWidth = 0.8 * inch
            logo.drawHeight = 0.7 * inch
            logo.hAlign = 'RIGHT'
    except Exception as e:
        logger.warning(f"Logo load failed: {e}")

    PAGE_WIDTH = 7.27 * inch
    header_data = [[title_paragraph, logo]]
    header_table = Table(header_data, colWidths=[PAGE_WIDTH - 1.0 * inch, 1.0 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.12 * inch))

    # 1. Visit details
    story.append(Paragraph('1. Visit & Contact Details', styles['BoldTitle']))
    story.append(Spacer(1, 0.05 * inch))

    details_data = [
        [Paragraph('<b>Building Name:</b>', styles['Question']), visit_info.get('building_name', 'N/A'),
         Paragraph('<b>Date of Visit:</b>', styles['Question']), datetime.now().strftime('%Y-%m-%d')],
        [Paragraph('<b>Site Address:</b>', styles['Question']), visit_info.get('building_address', 'N/A'),
         Paragraph('<b>Technician:</b>', styles['Question']), visit_info.get('technician_name', 'N/A')],
        [Paragraph('<b>Contact Person:</b>', styles['Question']), visit_info.get('contact_person', 'N/A'),
         Paragraph('<b>Operation Manager:</b>', styles['Question']), visit_info.get('opMan_name', 'N/A')],
        [Paragraph('<b>Contact Number:</b>', styles['Question']), visit_info.get('contact_number', 'N/A'),
         Paragraph('<b>Email:</b>', styles['Question']), visit_info.get('email', 'N/A')]
    ]
    details_table = Table(details_data, colWidths=[1.5 * inch, 2.135 * inch, 1.5 * inch, 2.135 * inch])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), ACCENT_BG_COLOR),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, GRID_COLOR),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 0.12 * inch))

    # 2. Report Items
    story.append(Paragraph('2. Report Items', styles['BoldTitle']))
    story.append(Spacer(1, 0.05 * inch))

    if processed_items:
        for i, item in enumerate(processed_items):
            # Item header
            asset = item.get('asset', 'N/A')
            system = item.get('system', 'N/A')
            desc = item.get('description', 'N/A')
            story.append(Paragraph(f"<b>Item {i + 1}:</b> {asset} / {system}", styles['Question']))
            story.append(Spacer(1, 0.04 * inch))

            item_details = [
                ['Description:', desc, 'Quantity:', item.get('quantity', 'N/A')],
                ['Brand/Model:', item.get('brand', 'N/A') or 'N/A', 'Comments:', item.get('comments', 'N/A') or 'N/A']
            ]
            item_table = Table(item_details, colWidths=[1.5 * inch, 2.135 * inch, 1.5 * inch, 2.135 * inch])
            item_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('TEXTCOLOR', (0, 0), (0, -1), BRAND_COLOR),
                ('TEXTCOLOR', (2, 0), (2, -1), BRAND_COLOR),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(item_table)
            story.append(Spacer(1, 0.06 * inch))

            # Photos: accept either 'image_paths' (local) or 'image_urls' (remote)
            image_sources = item.get('image_paths') or item.get('image_urls') or []
            if image_sources:
                photo_label_table = Table([[Paragraph('<b>Photos:</b>', styles['Question'])]], colWidths=[PAGE_WIDTH])
                photo_label_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F9F9F9')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(photo_label_table)
                story.append(Spacer(1, 0.04 * inch))

                image_elements = []
                img_w = 2.2 * inch
                img_h = 1.7 * inch
                for src in image_sources:
                    try:
                        el = get_image_element(src, img_w, img_h, placeholder_text="Photo N/A")
                    except Exception as e:
                        logger.warning(f"Failed preparing image element for {src}: {e}")
                        el = Paragraph('<font size="8">Image Error</font>', styles['SmallText'])
                    image_elements.append(el)

                # build rows with up to 3 columns
                num_cols = 3
                rows = [image_elements[k:k + num_cols] for k in range(0, len(image_elements), num_cols)]
                if rows and len(rows[-1]) < num_cols:
                    rows[-1].extend([Paragraph('', styles['SmallText'])] * (num_cols - len(rows[-1])))

                if rows:
                    photo_table = Table(rows, colWidths=[PAGE_WIDTH / num_cols] * num_cols)
                    photo_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ]))
                    story.append(photo_table)
                story.append(Spacer(1, 0.2 * inch))

            story.append(Spacer(1, 0.2 * inch))
    else:
        story.append(Paragraph("No report items were added to this visit.", styles['Normal']))

    # 3. General Notes
    story.append(Paragraph('3. General Notes', styles['BoldTitle']))
    story.append(Spacer(1, 0.05 * inch))
    notes_text = visit_info.get('general_notes') or 'No general notes provided.'
    notes_table = Table([[Paragraph(notes_text, styles['Answer'])]], colWidths=[PAGE_WIDTH], rowHeights=[0.8 * inch])
    notes_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, GRID_COLOR),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(notes_table)
    story.append(Spacer(1, 0.12 * inch))

    # 4. Signatures
    story.extend(create_signature_table(visit_info))

    return story

def generate_visit_pdf(visit_info, processed_items, output_dir, upload_to_cloudinary=False, cloudinary_folder='site_reports', public_id_prefix=None, **kwargs):
    """
    Generate formatted PDF using Platypus. Returns:
      - (pdf_path, pdf_filename) if upload_to_cloudinary is False
      - (pdf_path, pdf_filename, signed_pdf_url_or_None) if upload_to_cloudinary is True

    The extra kwargs are accepted for backward compatibility with older callers.
    """
    building_name = (visit_info.get('building_name') if isinstance(visit_info, dict) else None) or 'Unknown'
    building_name = str(building_name).replace(' ', '_')
    ts = int(time.time())
    pdf_filename = f"Site_Visit_Report_{building_name}_{ts}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)

    # Ensure directory exists
    os.makedirs(output_dir, exist_ok=True)

    PAGE_WIDTH = 7.27 * inch  # used by inner functions; defined here for closure
    story = build_report_story(visit_info or {}, processed_items or [])

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=0.5 * inch, leftMargin=0.5 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.75 * inch)

    try:
        doc.build(story, onFirstPage=page_layout_template, onLaterPages=page_layout_template)
        logger.info(f"PDF written to {pdf_path}")
    except Exception as e:
        logger.exception(f"Failed to build PDF: {e}")
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass
        raise

    signed_pdf_url = None

    # Optionally upload to Cloudinary (backwards compatible behavior)
    if upload_to_cloudinary:
        if not _HAS_CLOUDINARY:
            logger.warning("upload_to_cloudinary requested but cloudinary package/config is unavailable.")
            signed_pdf_url = None
        else:
            try:
                pid_prefix = public_id_prefix or f"report-{ts}"
                public_id = f"{pid_prefix}_{int(time.time())}"
                upload_result = cloudinary.uploader.upload(
                    pdf_path,
                    resource_type='raw',
                    folder=cloudinary_folder,
                    public_id=public_id,
                    overwrite=True
                )
                pdf_public_id = upload_result.get('public_id') or public_id
                try:
                    # use SDK download_url if available, otherwise fallback
                    if _HAS_DOWNLOAD_URL:
                        signed_pdf_url = download_url(pdf_public_id, resource_type='raw', sign_url=True, attachment=True)
                    else:
                        signed_pdf_url = _download_url_fallback(pdf_public_id, resource_type='raw', sign_url=True, attachment=True)
                except Exception as e:
                    logger.warning(f"Failed to build signed download URL for {pdf_public_id}: {e}")
                    signed_pdf_url = upload_result.get('secure_url') or None
            except Exception as e:
                logger.exception(f"Cloudinary upload of PDF failed: {e}")
                signed_pdf_url = None

    if upload_to_cloudinary:
        return pdf_path, pdf_filename, signed_pdf_url
    else:
        return pdf_path, pdf_filename