import os
import time
import io # CRITICAL IMPORT for in-memory file handling
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import logging
from PIL import Image as PilImage, ImageStat, ImageDraw # Keep PIL import
import tempfile 
import shutil 

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION & BRANDING ---
BRAND_COLOR = colors.HexColor('#198754') 
ACCENT_BG_COLOR = colors.HexColor('#F2FBF8') 
GRID_COLOR = colors.HexColor('#CCCCCC')

# Initialize styles
styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name='BoldTitle', 
    fontName='Helvetica-Bold', 
    fontSize=14, 
    leading=16, 
    textColor=BRAND_COLOR,
    spaceAfter=0.1*inch
))
styles.add(ParagraphStyle(name='Question', fontName='Helvetica-Bold', fontSize=10, leading=12))
styles.add(ParagraphStyle(name='Answer', fontName='Helvetica', fontSize=10, leading=12))
styles.add(ParagraphStyle(name='SmallText', fontName='Helvetica', fontSize=8, leading=10))

# --------------------------------------------------------------------------------------
# --- CRITICAL REVISION: IN-MEMORY IMAGE HANDLING (NO TEMP FILES) ---
# --------------------------------------------------------------------------------------

def resize_image_to_bytes(file_path, max_dimension=800):
    """
    Resizes the image using Pillow and returns the image data as a BytesIO object.
    This avoids writing temporary files to the disk.
    Returns: (io.BytesIO object, original format string) or (None, None)
    """
    if not os.path.exists(file_path):
        logger.warning(f"Original file not found: {file_path}")
        return None, None

    try:
        img = PilImage.open(file_path)
        
        # Determine format for saving - ReportLab prefers PNG/JPEG
        img_format = img.format if img.format in ['JPEG', 'PNG'] else 'PNG'
        
        img_width, img_height = img.size
        
        # Calculate ratio to maintain aspect ratio and fit within max_dimension
        ratio = min(max_dimension / img_width, max_dimension / img_height)

        # Use the correct constant for resampling
        resample_filter = PilImage.Resampling.LANCZOS if hasattr(PilImage, 'Resampling') else PilImage.LANCZOS

        if ratio < 1: # Only resize if it's currently too big
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            # Ensure mode compatibility before resizing (e.g., convert RGBA to RGB if saving as JPEG)
            if img_format == 'JPEG' and img.mode == 'RGBA':
                img = img.convert('RGB')
                
            img = img.resize((new_width, new_height), resample_filter)
        
        # Save the resized image to an in-memory stream
        img_byte_arr = io.BytesIO()
        # Set format explicitly for the stream
        img.save(img_byte_arr, format=img_format, quality=85)
        
        # Explicitly close the PIL image and release resources
        img.close()
        
        # Rewind the stream to the beginning
        img_byte_arr.seek(0)
        
        return img_byte_arr, img_format

    except Exception as e:
        logger.error(f"Pillow resize/save to bytes failed for {file_path}. Error: {e}")
        return None, None


def get_image_from_path(file_path, width, height, placeholder_text="No Photo"):
    """
    Loads a ReportLab Image object using an in-memory stream after resizing.
    Returns the ReportLab Image object. No temporary file cleanup is needed.
    """
    img_stream = None
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"Image file not found for PDF: {file_path}")
        return Paragraph(f'<font size="8">{placeholder_text}</font>', styles['SmallText'])

    # CRITICAL STEP: Resize the image data and get an in-memory stream
    img_stream, img_format = resize_image_to_bytes(file_path) 
    
    if img_stream is None:
        return Paragraph(f'<font size="8">Image Load Error</font>', styles['SmallText'])
        
    try:
        # ReportLab's Image constructor can take a file-like object (BytesIO)
        img = Image(img_stream)
        img.drawWidth = width
        img.drawHeight = height
        img.hAlign = 'CENTER'
        # Return the image object. 
        return img
        
    except Exception as e:
        logger.error(f"ReportLab Image load error from stream for path {file_path}: {e}")
        return Paragraph(f'<font size="8">Image Load Error</font>', styles['SmallText'])
        
    finally:
        # IMPORTANT: Close the BytesIO stream to free up memory
        if img_stream:
            img_stream.close()


def get_sig_image_from_path(file_path, name):
    """Loads signature from a file path using in-memory stream."""
    img_stream = None
    if file_path and os.path.exists(file_path):
        try:
            # Signatures are small, use a smaller max dimension
            img_stream, img_format = resize_image_to_bytes(file_path, max_dimension=400) 
            
            if img_stream:
                sig_img = Image(img_stream)
                sig_img.drawHeight = 0.7 * inch
                sig_img.drawWidth = 2.5 * inch
                sig_img.hAlign = 'LEFT' 
                return sig_img
            
        except Exception as e:
            logger.error(f"Failed to load signature image for {name} from {file_path}: {e}")
            return Paragraph(f'Image Load Failed: {name}', styles['Normal'])
        finally:
            # Close the stream immediately after ReportLab consumes it
            if img_stream:
                img_stream.close()
            
    return Paragraph(f'Unsigned: {name}', styles['Normal']) 


def create_signature_table(visit_info):
    """Creates the signature block."""
    sig_story = []
    
    sig_story.append(Spacer(1, 0.3*inch))
    sig_story.append(Paragraph('4. Signatures', styles['BoldTitle'])) 
    sig_story.append(Spacer(1, 0.1*inch)) 

    # Retrieve file paths 
    tech_sig_path = visit_info.get('tech_signature_path')
    opMan_sig_path = visit_info.get('opMan_signature_path')

    # Load images (get_sig_image_from_path handles its own stream closure)
    tech_sig = get_sig_image_from_path(tech_sig_path, 'Technician')
    opMan_sig = get_sig_image_from_path(opMan_sig_path, 'Operation Manager')

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


# Helper function to create the photo grid (used in Section 3 for extra photos)
def create_extra_photo_grid(extra_image_paths):
    if not extra_image_paths:
        return []

    story = []
    
    PHOTO_WIDTH = 1.5 * inch
    PHOTO_HEIGHT = 1.2 * inch 
    
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("<font size='10'><b>Additional Photos:</b></font>", styles['Question']))
    story.append(Spacer(1, 0.05 * inch))
    
    photo_elements = []
    
    for img_path in extra_image_paths:
        # Load image (now returns only the ReportLab image object)
        photo = get_image_from_path(img_path, PHOTO_WIDTH, PHOTO_HEIGHT, placeholder_text="Image Missing")
        
        photo.hAlign = 'CENTER' 
        photo_elements.append(photo)
        
        # Aggressive cleanup: Delete objects immediately
        del photo
    
    # Arrange photos in rows of MAX_COLS
    if photo_elements:
        PAGE_WIDTH = 7.27 * inch
        MAX_COLS = 4
        COL_WIDTH = PAGE_WIDTH / MAX_COLS
        
        num_photos = len(photo_elements)
        rows = []
        
        for i in range(0, num_photos, MAX_COLS):
            row_elements = photo_elements[i:i + MAX_COLS]
            # Pad the last row if necessary
            if len(row_elements) < MAX_COLS:
                 row_elements.extend([Paragraph('', styles['Normal'])] * (MAX_COLS - len(row_elements)))
            rows.append(row_elements)

        if rows:
            photo_grid_table = Table(rows, colWidths=[COL_WIDTH] * MAX_COLS, rowHeights=[PHOTO_HEIGHT + 0.1*inch] * len(rows)) 
            
            photo_grid_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'), 
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10), 
            ]))
            story.append(photo_grid_table)
            del photo_grid_table # Aggressive cleanup
            
    return story


# FUNCTION: Creates the table for user-selected photos/items (Section 3)
def create_report_photo_items_table(visit_info, processed_items):
    story = []
    story.append(Paragraph('3. Report photo items', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))
    
    IMG_COL_WIDTH = 1.75 * inch
    IMG_WIDTH = 1.6 * inch 
    IMG_HEIGHT = 1.3 * inch 
    PAGE_WIDTH = 7.27 * inch 
    DETAILS_COL_WIDTH = PAGE_WIDTH - IMG_COL_WIDTH
    
    for i, item in enumerate(processed_items):
        
        # Only process items that have at least one valid photo path
        # Note: In production, you might want to show items without photos too, but skip here if path is crucial.
        if not item.get('image_paths') or not os.path.exists(item['image_paths'][0]):
            continue 
            
        img_path = item['image_paths'][0] 
        
        try:
            # --- BUILD THE SINGLE-ITEM TABLE ---
            table_data = [
                [
                    Paragraph('<b>Photo</b>', styles['Question']), 
                    Paragraph('<b>Item Details</b>', styles['Question'])
                ]
            ]
            
            # Load image (now returns only the ReportLab image object)
            item_image = get_image_from_path(img_path, IMG_WIDTH, IMG_HEIGHT, placeholder_text="No Image")
            
            details_text = f"<b>Item {i + 1}:</b> {item['asset']} / {item['system']}<br/>"
            details_text += f"<b>Description:</b> {item['description']}<br/>"
            details_text += f"<b>Comments:</b> {item['comments'] or 'N/A'}"
            
            details_para = Paragraph(details_text, styles['Answer'])
            
            table_data.append([item_image, details_para])

            # Define the Table
            item_summary_table = Table(table_data, colWidths=[IMG_COL_WIDTH, DETAILS_COL_WIDTH])
            
            # Style definition
            header_style_commands = [
                ('BACKGROUND', (0, 0), (-1, 0), ACCENT_BG_COLOR),
                ('TEXTCOLOR', (0, 0), (-1, 0), BRAND_COLOR),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, GRID_COLOR),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'), 
                ('ALIGN', (0, 1), (0, 1), 'CENTER'), 
            ]
            
            item_summary_table.setStyle(TableStyle(header_style_commands))
            story.append(item_summary_table)
            
            # --- ADD EXTRA PHOTOS BELOW THE TABLE ---
            if len(item['image_paths']) > 1:
                extra_image_paths = item['image_paths'][1:]
                # create_extra_photo_grid handles its own image stream cleanup
                story.extend(create_extra_photo_grid(extra_image_paths)) 

            story.append(Spacer(1, 0.1 * inch))

            # Aggressive cleanup: Manually delete the objects after they are added
            del item_image
            del item_summary_table
            
        except Exception as e:
            logger.error(f"Error processing item {i+1} for photo table: {e}")
            story.append(Paragraph(f"**Error rendering item {i+1}: {e}**", styles['Answer']))
            
        # No finally block needed here for file cleanup anymore!
            
    if not story:
        story.append(Paragraph('No items with photos were selected for this report section.', styles['Normal']))

    story.append(Spacer(1, 0.2*inch))
    
    return story

# --- TEMPLATE HANDLER FOR FOOTER ---
FOOTER_TEXT = "PO BOX, 3456 Ajman, UAE | Tel +971 6 7489813 | Fax +971 6 711 6701 | www.injaaz.ae | Member of Ajman Holding group"

def page_layout_template(canvas, doc):
    """Function to draw the custom footer on every page."""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#666666'))
    footer_y = doc.bottomMargin - 0.25 * inch 
    canvas.drawCentredString(A4[0] / 2, footer_y, FOOTER_TEXT)
    canvas.setStrokeColor(GRID_COLOR)
    canvas.setLineWidth(0.5)
    # Draw horizontal line above the footer text
    canvas.line(doc.leftMargin, footer_y + 0.15 * inch, A4[0] - doc.rightMargin, footer_y + 0.15 * inch)
    canvas.drawRightString(A4[0] - doc.rightMargin, footer_y, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()

# --- MAIN GENERATOR FUNCTION ---

def build_report_story(visit_info, processed_items, logo_path):
    story = []
    
    PAGE_WIDTH = 7.27 * inch 

    # --- 1. Header and Title with Logo ---
    title_text = f"Site Visit Report - {visit_info.get('building_name', 'N/A')}"
    title_paragraph = Paragraph(f"<b>{title_text}</b>", styles['BoldTitle']) 
    
    logo_image = Paragraph('', styles['Normal'])
    logo_img = None

    try:
        if logo_path and os.path.exists(logo_path):
            # No temp path returned anymore
            logo_img = get_image_from_path(logo_path, 1.0 * inch, 0.9 * inch, placeholder_text="No Logo")
            logo_img.hAlign = 'RIGHT'
            logo_image = logo_img
        else:
            logger.warning(f"Logo file not found at: {logo_path}")
    except Exception as e:
        logger.error(f"Failed to load logo image: {e}")

    # No finally block needed for logo cleanup

    
    header_data = [[title_paragraph, logo_image]]
    header_table = Table(header_data, colWidths=[PAGE_WIDTH - 1.5 * inch, 1.5 * inch]) 
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'), 
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'), 
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 0.1*inch))
    del header_table
    
    # Explicitly delete logo image object after use
    if logo_img:
        del logo_img 
        del logo_image

    # --- SECTION 1: Visit & Contact Details ---
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
    del details_table

    # --- SECTION 2: Report Items (Detailed Breakdown) ---
    story.append(Paragraph('2. Report Items (Detailed Breakdown)', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))
    
    if processed_items:
        for i, item in enumerate(processed_items):
            story.append(Paragraph(f"<b>Item {i + 1}:</b> {item['asset']} / {item['system']}", styles['Question']))
            story.append(Spacer(1, 0.05*inch))
            
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
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6), 
            ]))
            story.append(item_table)
            del item_table 
            story.append(Spacer(1, 0.3 * inch))

    story.append(Spacer(1, 0.2*inch))
    # --- SECTION 3: Report Photos ---
    story.extend(create_report_photo_items_table(visit_info, processed_items))

    # --- SECTION 4: Signatures ---
    story.extend(create_signature_table(visit_info))
    
    # Explicitly clear the large variables after they have been processed by ReportLab
    del visit_info
    del processed_items
    
    return story

def generate_visit_pdf(visit_info, processed_items, output_dir, logo_path): 
    
    building_name = visit_info.get('building_name', 'Unknown').replace(' ', '_')
    # Use microseconds for greater uniqueness
    ts = datetime.now().strftime('%Y%m%d%H%M%S%f')
    pdf_filename = f"Site_Visit_Report_{building_name}_{ts}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=0.5 * inch, leftMargin=0.5 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.75 * inch)
                            
    Story = build_report_story(visit_info, processed_items, logo_path)
    
    try:
        doc.build(
            Story, 
            onFirstPage=page_layout_template, 
            onLaterPages=page_layout_template
        )
        return pdf_path, pdf_filename
        
    except Exception as e:
        logger.error(f"FATAL PDF GENERATION ERROR: {e}")
        # Re-raise to be caught by the main route handler
        raise