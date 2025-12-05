import os
import time
import logging
import tempfile
from datetime import datetime
import requests
from io import BytesIO # Required by requests, though not directly used for file I/O

# --- REMOVED S3/Boto3 IMPORTS AND CLIENT SETUP ---
# Removed: import boto3
# Removed: from botocore.exceptions import ClientError
# Removed: S3_BUCKET_NAME, AWS_REGION, s3_client_download initialization

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# --- Logging Configuration ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- CONFIGURATION & BRANDING ---
BRAND_COLOR = colors.HexColor('#198754') 
ACCENT_BG_COLOR = colors.HexColor('#F2FBF8')
GRID_COLOR = colors.HexColor('#CCCCCC')

try:
    LOGO_PATH = os.path.join('/app', 'module_site_visit', 'static', 'INJAAZ.png')
    if not os.path.exists(LOGO_PATH):
        LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'INJAAZ.png')
except NameError:
    LOGO_PATH = os.path.join(os.getcwd(), 'static', 'INJAAZ.png')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='BoldTitle', fontName='Helvetica-Bold', fontSize=14, leading=16, textColor=BRAND_COLOR, spaceAfter=0.1*inch))
styles.add(ParagraphStyle(name='Question', fontName='Helvetica-Bold', fontSize=10, leading=12))
styles.add(ParagraphStyle(name='Answer', fontName='Helvetica', fontSize=10, leading=12))
styles.add(ParagraphStyle(name='SmallText', fontName='Helvetica', fontSize=8, leading=10))


# =================================================================
# --- CLOUDINARY DOWNLOAD IMPLEMENTATION (FOR PHOTOS AND SIGNATURES) ---
# =================================================================

def download_cloudinary_image_to_temp(url):
    """
    Fetches image content from a public URL and saves it to a temporary local file.
    Used for ALL external images (Report Photos and Signatures).
    """
    if not url:
        return None
        
    file_path = None
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        # Create a named temporary file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            file_path = tmp.name
            # Save the downloaded binary content to the temporary file
            tmp.write(response.content)

        logger.info(f"Successfully downloaded image from URL to {file_path}")
        return file_path
        
    except requests.exceptions.RequestException as e:
        logger.error(f"ERROR: Failed to download image from {url}: {e}")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return None
    except Exception as e:
        logger.error(f"Unexpected error during image save: {e}")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return None

# =================================================================
# --- NEW SIGNATURE DOWNLOAD IMPLEMENTATION (URL-BASED) ---
# This REPLACES the old get_sig_image_from_s3 logic.
# =================================================================

def get_sig_image_from_url(url, name):
    """
    Loads signature image from a Cloudinary URL.
    """
    if not url:
        return Paragraph(f'Unsigned: {name}', styles['Normal'])
        
    temp_file_path = None
    try:
        # Use the common download function
        temp_file_path = download_cloudinary_image_to_temp(url)
        
        if not temp_file_path or not os.path.exists(temp_file_path):
            return Paragraph(f'Image Fetch Failed: {name}', styles['Normal'])

        sig_img = Image(temp_file_path)
        sig_img.drawHeight = 0.7 * inch
        sig_img.drawWidth = 2.5 * inch
        sig_img.hAlign = 'LEFT' 
        return sig_img
    except Exception as e:
        logger.error(f"Failed to load signature image for {name} ({url}): {e}")
        return Paragraph(f'Image Process Failed: {name}', styles['Normal'])
    finally:
        # CRITICAL: Delete the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def get_image_from_cloudinary(url, width, height, placeholder_text="No Photo"):
    """
    Loads report photo image from a Cloudinary URL.
    """
    if not url:
        return Paragraph(f'<font size="8">{placeholder_text}</font>', styles['SmallText'])
        
    temp_file_path = None
    try:
        # 1. Download file from URL to a temporary local path
        temp_file_path = download_cloudinary_image_to_temp(url)

        if not temp_file_path or not os.path.exists(temp_file_path):
            return Paragraph(f'<font size="8">Image Fetch Failed</font>', styles['SmallText'])

        # 2. Use ReportLab to read the image from the temporary path
        img = Image(temp_file_path) 
        img.drawWidth = width
        img.drawHeight = height
        img.hAlign = 'CENTER' 
        return img
    except Exception as e:
        logger.error(f"Image load error for URL {url}: {e}")
        return Paragraph(f'<font size="8">Image Process Error</font>', styles['SmallText'])
    finally:
        # 3. CRITICAL: DELETE THE TEMPORARY FILE IMMEDIATELY
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# =================================================================
# --- REPORT COMPONENTS ---
# =================================================================

def create_signature_table(visit_info):
    sig_story = []
    
    sig_story.append(Spacer(1, 0.3*inch))
    sig_story.append(Paragraph('4. Signatures', styles['BoldTitle'])) 
    sig_story.append(Spacer(1, 0.1*inch)) 

    # *** CRITICAL CHANGE: Retrieve URL keys instead of S3 keys ***
    tech_sig_url = visit_info.get('tech_signature_url')
    opMan_sig_url = visit_info.get('opMan_signature_url')

    # *** CRITICAL CHANGE: Call the new URL-based function ***
    tech_sig = get_sig_image_from_url(tech_sig_url, 'Technician')
    opMan_sig = get_sig_image_from_url(opMan_sig_url, 'Operation Manager')

    # Get names for display (Unchanged)
    tech_name = visit_info.get('technician_name', 'N/A')
    opMan_name = visit_info.get('opMan_name', 'N/A')

    signature_data = [
        [tech_sig, opMan_sig],
        [Paragraph('<font size="10">_________________________</font>', styles['Normal']), 
         Paragraph('<font size="10">_________________________</font>', styles['Normal'])],
        [Paragraph(f"<font size='10'><b>Technician:</b> {tech_name}</font>", styles['Normal']), 
         Paragraph(f"<font size='10'><b>Operation Manager:</b> {opMan_name}</font>", styles['Normal'])]
    ]
    
    signature_table = Table(signature_data, colWidths=[3.75*inch, 3.75*inch], rowHeights=[0.8*inch, 0.1*inch, 0.2*inch]) 
    TEXT_SHIFT_PADDING = 15 

    signature_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'), 
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0, 1), (-1,-1), TEXT_SHIFT_PADDING), 
    ]))
    
    sig_story.append(signature_table)
    return sig_story

# --- TEMPLATE HANDLER FOR FOOTER (Unchanged) ---
FOOTER_TEXT = "PO BOX, 3456 Ajman, UAE | Tel +971 6 7489813 | Fax +971 6 711 6701 | www.injaaz.ae | Member of Ajman Holding group"

def page_layout_template(canvas, doc):
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

# --- MAIN GENERATOR FUNCTION (Unchanged) ---
def generate_visit_pdf(visit_info, processed_items, output_dir):
    
    start_time = time.time() 
    logger.info(f"PDF generation started for {visit_info.get('building_name', 'N/A')} at {datetime.now()}")

    building_name = visit_info.get('building_name', 'Unknown').replace(' ', '_')
    ts = int(time.time())
    pdf_filename = f"Site_Visit_Report_{building_name}_{ts}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=0.5 * inch, leftMargin=0.5 * inch, topMargin=0.5 * inch, bottomMargin=0.75 * inch)
                        
    Story = build_report_story(visit_info, processed_items)
    
    doc.build(
        Story, 
        onFirstPage=page_layout_template, 
        onLaterPages=page_layout_template
    )
    
    end_time = time.time()
    logger.info(f"PDF build finished in {end_time - start_time:.2f} seconds.") 

    return pdf_path, pdf_filename


def build_report_story(visit_info, processed_items):
    story = []
    
    # --- 1. Header and Title with Logo (Unchanged) ---
    title_text = f"Site Visit Report - {visit_info.get('building_name', 'N/A')}"
    title_paragraph = Paragraph(title_text, styles['BoldTitle'])

    logo = Paragraph('', styles['Normal'])
    
    try:
        if os.path.exists(LOGO_PATH):
            logo_img = Image(LOGO_PATH)
            logo_img.drawWidth = 0.8 * inch 
            logo_img.drawHeight = 0.7 * inch 
            logo_img.hAlign = 'RIGHT' 
            logo = logo_img
        else:
            logger.warning(f"Logo not found or failed to load at path: {LOGO_PATH}")
    except Exception as e:
        logger.error(f"Failed to load logo image: {e}")

    PAGE_WIDTH = 7.27 * inch 
    header_data = [[title_paragraph, logo]]
    header_table = Table(header_data, colWidths=[PAGE_WIDTH - 1.0 * inch, 1.0 * inch]) 
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 0.2*inch))


    # --- 2. Visit & Contact Details (Section 1 - Unchanged) ---
    story.append(Paragraph('1. Visit & Contact Details', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))
    
    details_data = [
        [Paragraph('<b>Building Name:</b>', styles['Question']), visit_info.get('building_name', 'N/A'), Paragraph('<b>Date of Visit:</b>', styles['Question']), datetime.now().strftime('%Y-%m-%d')],
        [Paragraph('<b>Site Address:</b>', styles['Question']), visit_info.get('building_address', 'N/A'), Paragraph('<b>Technician:</b>', styles['Question']), visit_info.get('technician_name', 'N/A')],
        [Paragraph('<b>Contact Person:</b>', styles['Question']), visit_info.get('contact_person', 'N/A'), Paragraph('<b>Operation Manager:</b>', styles['Question']), visit_info.get('opMan_name', 'N/A')],
        [Paragraph('<b>Contact Number:</b>', styles['Question']), visit_info.get('contact_number', 'N/A'), Paragraph('<b>Email:</b>', styles['Question']), visit_info.get('email', 'N/A')]
    ]

    details_table = Table(details_data, colWidths=[1.5*inch, 2.135*inch, 1.5*inch, 2.135*inch]) 
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), ACCENT_BG_COLOR), 
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, GRID_COLOR),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 0.2*inch))


    # --- 3. Report Items (Section 2 - Unchanged) ---
    story.append(Paragraph('2. Report Items', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))
    
    if processed_items:
        for i, item in enumerate(processed_items):
            # Item Details
            story.append(Paragraph(f"<b>Item {i + 1}:</b> {item['asset']} / {item['system']} / {item['description']}", styles['Question']))
            story.append(Spacer(1, 0.05*inch))
            
            # Details Table for each item
            item_details = [
                ['Description:', item['description'], 'Quantity:', item['quantity']],
                ['Brand/Model:', item['brand'] or 'N/A', 'Comments:', item['comments'] or 'N/A']
            ]
            
            item_table = Table(item_details, colWidths=[1.5*inch, 2.135*inch, 1.5*inch, 2.135*inch])
            item_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('TEXTCOLOR', (0, 0), (0, -1), BRAND_COLOR),
                ('TEXTCOLOR', (2, 0), (2, -1), BRAND_COLOR),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(item_table)
            story.append(Spacer(1, 0.1*inch))
            
            # Photos for this item
            image_urls = item.get('image_urls')
            
            if image_urls: 
                
                photo_label_data = [[Paragraph('<b>Photos:</b>', styles['Question'])]]
                photo_label_table = Table(photo_label_data, colWidths=[PAGE_WIDTH])
                photo_label_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9F9F9')),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                ]))
                story.append(photo_label_table)

                image_elements = []
                for url in image_urls:
                    # Uses the CLOUDINARY image loading function
                    img = get_image_from_cloudinary(url, 2.2 * inch, 1.7 * inch, placeholder_text="Photo N/A")
                    image_elements.append(img)

                # Arrange images into rows of 3
                num_cols = 3
                col_width = PAGE_WIDTH / num_cols 
                rows = [image_elements[k:k + num_cols] for k in range(0, len(image_elements), num_cols)]
                
                if rows:
                    photo_table = Table(rows, colWidths=[col_width] * num_cols)
                    photo_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
                    ]))
                    story.append(photo_table)
            
            story.append(Spacer(1, 0.3 * inch))

    else:
        story.append(Paragraph("No report items were added to this visit.", styles['Normal']))

    # --- BLOCK 4 & 5 (General Notes & Signatures) ---
    story.append(Paragraph('3. General Notes', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))

    notes_text = visit_info.get('general_notes', "No general notes provided.")
    
    notes_data = [[Paragraph(notes_text, styles['Answer'])]]
    notes_table = Table(notes_data, colWidths=[PAGE_WIDTH], rowHeights=[0.8*inch])
    notes_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, GRID_COLOR),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(notes_table)
    
    # Calls the UPDATED signature table which uses the URL-based functions
    story.extend(create_signature_table(visit_info))
    
    return story