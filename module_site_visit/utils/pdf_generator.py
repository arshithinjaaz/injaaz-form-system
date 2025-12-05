import os
import time
import logging
import tempfile # For creating temporary files
from datetime import datetime

# --- S3 IMPORTS AND CLIENT SETUP ---
import boto3
from botocore.exceptions import ClientError

# Configuration from environment variables
# CRITICAL: Reads AWS_REGION and S3_BUCKET_NAME from your Render environment
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

try:
    # Boto3 automatically uses AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from env
    s3_client_download = boto3.client('s3', region_name=AWS_REGION)
except ClientError as e:
    # This will log an error if AWS access is configured incorrectly
    logging.error(f"S3 Client initialization failed: {e}")
    s3_client_download = None

# -----------------------------------

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# --- Logging Configuration (Kept) ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- CONFIGURATION & BRANDING (Kept) ---
BRAND_COLOR = colors.HexColor('#198754') 
ACCENT_BG_COLOR = colors.HexColor('#F2FBF8')
GRID_COLOR = colors.HexColor('#CCCCCC')

# NOTE: Logo path remains local since it's a static app file
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
# --- NEW S3 DOWNLOAD IMPLEMENTATION ---
# This function is now fully self-contained and uses Boto3
# =================================================================

def download_s3_file_to_temp(s3_key):
    """
    Downloads a file from S3 to a temporary local file and returns the path.
    The caller (get_image_from_s3) is responsible for deleting the temporary file.
    """
    if not s3_client_download or not s3_key or not S3_BUCKET_NAME:
        logger.warning("S3 client not initialized or missing key/bucket name for download.")
        return None
        
    file_path = None
    try:
        # Create a named temporary file that won't be deleted immediately
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = tmp.name
            
        # Download the S3 object to the temporary file path
        s3_client_download.download_file(S3_BUCKET_NAME, s3_key, file_path)
        
        logger.info(f"Successfully downloaded {s3_key} to {file_path}")
        return file_path
        
    except ClientError as e:
        logger.error(f"Error downloading S3 file {s3_key}: {e}")
        # If an error occurs, clean up the temp file if created
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return None
    except Exception as e:
        logger.error(f"Unexpected error during download for {s3_key}: {e}")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return None

# =================================================================
# --- HELPER FUNCTIONS FOR S3 ACCESS (UPDATED) ---
# The logic inside these functions is correct for temp file handling.
# =================================================================

def get_sig_image_from_s3(s3_key, name):
    """
    Loads signature image from S3. Requires S3_key as input.
    """
    if not s3_key:
        return Paragraph(f'Unsigned: {name}', styles['Normal'])
        
    temp_file_path = None
    try:
        # 1. Download file to a temporary local path
        temp_file_path = download_s3_file_to_temp(s3_key) # <-- NOW CALLS THE BOTO3 IMPLEMENTATION
        
        if not temp_file_path or not os.path.exists(temp_file_path):
            return Paragraph(f'Image Fetch Failed: {name}', styles['Normal'])

        # 2. Use ReportLab to read the image from the temporary path
        sig_img = Image(temp_file_path)
        sig_img.drawHeight = 0.7 * inch
        sig_img.drawWidth = 2.5 * inch
        sig_img.hAlign = 'LEFT' 
        return sig_img
    except Exception as e:
        logger.error(f"Failed to load S3 signature image for {name} ({s3_key}): {e}")
        return Paragraph(f'Image Process Failed: {name}', styles['Normal'])
    finally:
        # 3. CRITICAL: DELETE THE TEMPORARY FILE IMMEDIATELY
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def get_image_from_s3(s3_key, width, height, placeholder_text="No Photo"):
    """
    Loads report photo image from S3. Requires S3_key as input.
    """
    if not s3_key:
        return Paragraph(f'<font size="8">{placeholder_text}</font>', styles['SmallText'])
        
    temp_file_path = None
    try:
        # 1. Download file to a temporary local path
        temp_file_path = download_s3_file_to_temp(s3_key) # <-- NOW CALLS THE BOTO3 IMPLEMENTATION

        if not temp_file_path or not os.path.exists(temp_file_path):
            return Paragraph(f'<font size="8">Image Fetch Failed</font>', styles['SmallText'])

        # 2. Use ReportLab to read the image from the temporary path
        img = Image(temp_file_path) 
        img.drawWidth = width
        img.drawHeight = height
        img.hAlign = 'CENTER' 
        return img
    except Exception as e:
        logger.error(f"Image load error for S3 key {s3_key}: {e}")
        return Paragraph(f'<font size="8">Image Process Error</font>', styles['SmallText'])
    finally:
        # 3. CRITICAL: DELETE THE TEMPORARY FILE IMMEDIATELY
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# --- The rest of the code is unchanged as it correctly uses the new S3 functions ---

def create_signature_table(visit_info):
# ... unchanged ...
    sig_story = []
    
    sig_story.append(Spacer(1, 0.3*inch))
    sig_story.append(Paragraph('4. Signatures', styles['BoldTitle'])) 
    sig_story.append(Spacer(1, 0.1*inch)) 

    tech_sig_key = visit_info.get('tech_signature_key')
    opMan_sig_key = visit_info.get('opMan_signature_key')

    tech_sig = get_sig_image_from_s3(tech_sig_key, 'Technician')
    opMan_sig = get_sig_image_from_s3(opMan_sig_key, 'Operation Manager')

    # Get names for display
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
    
    start_time = time.time() # Start timer
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
    logger.info(f"PDF build finished in {end_time - start_time:.2f} seconds.") # End timer

    return pdf_path, pdf_filename


def build_report_story(visit_info, processed_items):
# ... unchanged ...
    story = []
    
    # --- 1. Header and Title with Logo (Unchanged) ---
    title_text = f"Site Visit Report - {visit_info.get('building_name', 'N/A')}"
    title_paragraph = Paragraph(title_text, styles['BoldTitle'])

    logo = Paragraph('', styles['Normal'])
    
    # Attempt to load the Logo (Remains local)
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


    # --- 3. Report Items (Section 2 - Updated) ---
    story.append(Paragraph('2. Report Items', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))
    
    if processed_items:
        for i, item in enumerate(processed_items):
            # Item Details
            story.append(Paragraph(f"<b>Item {i + 1}:</b> {item['asset']} / {item['system']} / {item['description']}", styles['Question']))
            story.append(Spacer(1, 0.05*inch))
            
            # Details Table for each item (Unchanged)
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
            
            # Photos for this item (if available)
            # NOTE: 'image_paths' must now contain S3 keys (e.g., 'site-visit-photos/uuid.jpg')
            if item.get('image_keys'): 
                
                photo_label_data = [[Paragraph('<b>Photos:</b>', styles['Question'])]]
                photo_label_table = Table(photo_label_data, colWidths=[PAGE_WIDTH])
                photo_label_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9F9F9')),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                ]))
                story.append(photo_label_table)

                image_elements = []
                # item['image_keys'] is the new list of S3 keys
                for key in item['image_keys']:
                    # UPDATED: Use the S3 image loading function
                    img = get_image_from_s3(key, 2.2 * inch, 1.7 * inch, placeholder_text="Photo N/A")
                    image_elements.append(img)

                # Arrange images into rows of 3 (Unchanged)
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

    # --- BLOCK 4 & 5 (Unchanged) ---
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
    
    story.extend(create_signature_table(visit_info))
    
    return story