import os
import time
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import logging
from PIL import Image as PilImage, ImageStat, ImageDraw
import tempfile 
import shutil 

# --- Logging Configuration ---
# Set up a basic logger to track file operations
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

# --- MEMORY OPTIMIZATION HELPER (REVISED TO USE TEMPFILE) ---

def resize_image_for_pdf(file_path, max_dimension=800):
    """
    Resizes the image using Pillow and saves it to a secure, unique temporary file.
    Returns the path to the temporary, resized file.
    """
    if not os.path.exists(file_path):
        logger.warning(f"Original file not found: {file_path}")
        return file_path

    try:
        img = PilImage.open(file_path)
        img_width, img_height = img.size
        
        # Calculate ratio to maintain aspect ratio and fit within max_dimension
        ratio = min(max_dimension / img_width, max_dimension / img_height)

        # Use the correct constant for resampling
        resample_filter = PilImage.Resampling.LANCZOS if hasattr(PilImage, 'Resampling') else PilImage.LANCZOS

        if ratio < 1: # Only resize if it's currently too big
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            img = img.resize((new_width, new_height), resample_filter)
        
        # Use tempfile to create a secure, auto-cleaned file object
        suffix = os.path.splitext(file_path)[1]
        if not suffix: suffix = '.jpg' # Fallback suffix
        
        # Create a named temp file that we can read from later
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            temp_path = tmp.name 
            # Save the resized image to the unique temporary path
            img.save(temp_path, quality=85)
        
        # Explicitly close the PIL image and release resources
        img.close()
        
        return temp_path

    except Exception as e:
        logger.error(f"Pillow resize/save failed for {file_path}. Error: {e}")
        # Return original path if resize fails
        return file_path

def cleanup_temp_file(temp_path, original_path):
    """Safely cleans up a temporary file if it exists and is not the original file."""
    if temp_path and temp_path != original_path and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
            logger.debug(f"Successfully cleaned up temp file: {temp_path}")
        except OSError as e:
            logger.warning(f"Failed to clean up temp file {temp_path}: {e}")

def get_image_from_path(file_path, width, height, placeholder_text="No Photo"):
    """
    Loads a ReportLab Image object after resizing the source file for memory optimization.
    Returns the ReportLab Image object and the path of the temporary file for cleanup.
    """
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"Image file not found for PDF: {file_path}")
        return Paragraph(f'<font size="8">{placeholder_text}</font>', styles['SmallText']), None

    # CRITICAL STEP: Resize the image data (returns original path if it fails)
    temp_file_path = resize_image_for_pdf(file_path) 
    
    try:
        # ReportLab now loads the smaller, temporary file (or original file if resize failed)
        img = Image(temp_file_path)
        img.drawWidth = width
        img.drawHeight = height
        img.hAlign = 'CENTER'
        # Return the image object and the temp path for cleanup in the calling function
        return img, temp_file_path
    except Exception as e:
        logger.error(f"ReportLab Image load error for path {temp_file_path}: {e}")
        # If loading the image fails, return a placeholder and the temp_file_path for attempted cleanup
        return Paragraph(f'<font size="8">Image Load Error</font>', styles['SmallText']), temp_file_path


def get_sig_image_from_path(file_path, name):
    """Loads signature from a file path and handles cleanup internally."""
    temp_path = file_path # Initialize temp_path to file_path for safety
    
    if file_path and os.path.exists(file_path):
        try:
            # Signatures are small, so we use a smaller max dimension for optimization
            temp_path = resize_image_for_pdf(file_path, max_dimension=400) 
            
            sig_img = Image(temp_path)
            sig_img.drawHeight = 0.7 * inch
            sig_img.drawWidth = 2.5 * inch
            sig_img.hAlign = 'LEFT' 
            return sig_img
        except Exception as e:
            logger.error(f"Failed to load signature image for {name} from {file_path}: {e}")
            return Paragraph(f'Image Load Failed: {name}', styles['Normal'])
        finally:
            # Clean up the signature temp file immediately
            cleanup_temp_file(temp_path, file_path)
            
    return Paragraph(f'Unsigned: {name}', styles['Normal']) 


def create_signature_table(visit_info):
    """Creates the signature block."""
    sig_story = []
    
    sig_story.append(Spacer(1, 0.3*inch))
    sig_story.append(Paragraph('4. Signatures', styles['BoldTitle'])) 
    sig_story.append(Spacer(1, 0.1*inch)) 

    # Retrieve file paths saved in routes.py
    tech_sig_path = visit_info.get('tech_signature_path')
    opMan_sig_path = visit_info.get('opMan_signature_path')

    # Load images (get_sig_image_from_path handles its own temp cleanup)
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
    temp_files_to_clean = []
    
    PHOTO_WIDTH = 1.5 * inch
    PHOTO_HEIGHT = 1.2 * inch 
    
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("<font size='10'><b>Additional Photos:</b></font>", styles['Question']))
    story.append(Spacer(1, 0.05 * inch))
    
    photo_elements = []
    
    try:
        for img_path in extra_image_paths:
            # Load image and get temp path for cleanup
            photo, temp_path = get_image_from_path(img_path, PHOTO_WIDTH, PHOTO_HEIGHT, placeholder_text="Image Missing")
            
            # CRITICAL: Only clean up temporary resized files
            if temp_path and temp_path != img_path: 
                temp_files_to_clean.append(temp_path)
            
            photo.hAlign = 'CENTER' # Changed from RIGHT for better grid alignment
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
                photo_grid_table = Table(rows, colWidths=[COL_WIDTH] * MAX_COLS, rowHeights=[PHOTO_HEIGHT + 0.1*inch] * len(rows)) # Fixed row height
                
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
            
    finally:
        # CRITICAL: Clean up all temporary files created during this process
        for tmp_file in temp_files_to_clean:
            cleanup_temp_file(tmp_file, None)
            
    return story


# FUNCTION: Creates the table for user-selected photos/items (Section 3)
def create_report_photo_items_table(visit_info, processed_items):
    story = []
    story.append(Paragraph('3. Report photo items', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))
    
    IMG_COL_WIDTH = 1.75 * inch
    IMG_WIDTH = 1.6 * inch # Slightly smaller than column
    IMG_HEIGHT = 1.3 * inch 
    PAGE_WIDTH = 7.27 * inch 
    DETAILS_COL_WIDTH = PAGE_WIDTH - IMG_COL_WIDTH
    
    for i, item in enumerate(processed_items):
        
        # List to track temp files for this item
        temp_files_to_clean = []
        
        # Only process items that have at least one valid photo path
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
            
            # Load image (calls Pillow resize internally)
            item_image, temp_path = get_image_from_path(img_path, IMG_WIDTH, IMG_HEIGHT, placeholder_text="No Image")
            
            # CRITICAL: Only clean up if a new temporary file was created
            if temp_path and temp_path != img_path:
                temp_files_to_clean.append(temp_path)
            
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
                ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'), # Ensure image and text are centered vertically
                ('ALIGN', (0, 1), (0, 1), 'CENTER'), # Center image in its column
            ]
            
            item_summary_table.setStyle(TableStyle(header_style_commands))
            story.append(item_summary_table)
            
            # --- ADD EXTRA PHOTOS BELOW THE TABLE ---
            if len(item['image_paths']) > 1:
                extra_image_paths = item['image_paths'][1:]
                # create_extra_photo_grid handles its own temp file cleanup
                story.extend(create_extra_photo_grid(extra_image_paths)) 

            story.append(Spacer(1, 0.1 * inch))

            # Aggressive cleanup: Manually delete the objects after they are added
            del item_image
            del item_summary_table
            
        except Exception as e:
            logger.error(f"Error processing item {i+1} for photo table: {e}")
            story.append(Paragraph(f"**Error rendering item {i+1}: {e}**", styles['Answer']))
            
        finally:
            # Clean up temporary files created just for the first image of the current item
            for tmp_file in temp_files_to_clean:
                cleanup_temp_file(tmp_file, img_path)
            
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
    temp_logo_path = None # Initialize temp path for cleanup

    try:
        if logo_path and os.path.exists(logo_path):
            logo_img, temp_logo_path = get_image_from_path(logo_path, 1.0 * inch, 0.9 * inch, placeholder_text="No Logo")
            logo_img.hAlign = 'RIGHT'
            logo_image = logo_img
        else:
            logger.warning(f"Logo file not found at: {logo_path}")
    except Exception as e:
        logger.error(f"Failed to load logo image: {e}")

    finally:
        # Clean up temp logo file immediately after ReportLab loads it
        cleanup_temp_file(temp_logo_path, logo_path)

    
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
    # Use microseconds or a random component for greater uniqueness
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

# --------------------------------------------------------------------------------------
# --- EXECUTION BLOCK FOR TESTING ---
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    
    # ----------------------------------------------------------------------------------
    # !!! IMPORTANT: REPLACE THESE PATHS WITH ACTUAL, VALID FILES IN YOUR SYSTEM !!!
    # ----------------------------------------------------------------------------------
    
    # 1. Configuration and Paths
    # Ensure this directory exists and your script has write permissions
    OUTPUT_DIRECTORY = os.path.join(os.getcwd(), "generated_reports") 
    
    # Create the output directory if it doesn't exist
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True) 
    
    # --- Mock Image Creation (to ensure the code runs without actual images) ---
    # In a real environment, you would use existing image files.
    # We create small placeholder images here so the code executes successfully.
    
    def create_mock_image(filepath, size, color):
        """Creates a simple colored placeholder image if the file doesn't exist."""
        if not os.path.exists(filepath):
            try:
                img = PilImage.new('RGB', size, color=color)
                # Add text to make it clear what it is
                d = ImageDraw.Draw(img)
                d.text((10, 10), os.path.basename(filepath), fill=(0,0,0))
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                img.save(filepath)
            except Exception as e:
                logger.error(f"Could not create mock image at {filepath}: {e}")
                
    IMAGE_DIR = os.path.join(os.getcwd(), "test_images")
    
    LOGO_PATH_MOCK = os.path.join(IMAGE_DIR, "logo.png")
    SIG_TECH_PATH_MOCK = os.path.join(IMAGE_DIR, "signature_tech.png")
    SIG_OPMAN_PATH_MOCK = os.path.join(IMAGE_DIR, "signature_opman.png")
    PHOTO_A_1_MOCK = os.path.join(IMAGE_DIR, "photo_a_1.jpg")
    PHOTO_A_2_MOCK = os.path.join(IMAGE_DIR, "photo_a_2.jpg")
    PHOTO_A_3_MOCK = os.path.join(IMAGE_DIR, "photo_a_3.jpg")
    PHOTO_B_1_MOCK = os.path.join(IMAGE_DIR, "photo_b_1.jpg")

    # Create the mock images
    create_mock_image(LOGO_PATH_MOCK, (300, 200), 'green')
    create_mock_image(SIG_TECH_PATH_MOCK, (400, 150), 'lightgray')
    create_mock_image(SIG_OPMAN_PATH_MOCK, (400, 150), 'lightgray')
    create_mock_image(PHOTO_A_1_MOCK, (1000, 800), 'lightblue') # Large image to test resizing
    create_mock_image(PHOTO_A_2_MOCK, (400, 300), 'lightcoral')
    create_mock_image(PHOTO_A_3_MOCK, (400, 300), 'lightyellow')
    create_mock_image(PHOTO_B_1_MOCK, (800, 600), 'lightgreen')


    # 2. Example Data Structures (Using mock paths)
    VISIT_INFO_DATA = {
        'building_name': 'Al-Subaygha Cafeteria',
        'building_address': 'Masfout Park, Ajman',
        'technician_name': 'Saleh Al Marzooqi',
        'opMan_name': 'Omar Abdullah',
        'contact_person': 'Fahad Al Ali',
        'contact_number': '+971 50 XXX XXXX',
        'email': 'client@injaaz.ae',
        'tech_signature_path': SIG_TECH_PATH_MOCK, 
        'opMan_signature_path': SIG_OPMAN_PATH_MOCK, 
    }

    PROCESSED_ITEMS_DATA = [
        {
            'asset': 'Exterior Wall',
            'system': 'Finishes',
            'description': 'Repairs and Shield Top Coat painting works required.',
            'quantity': '114',
            'brand': 'National Paints',
            'comments': 'Cracks observed near window frame.',
            'image_paths': [
                PHOTO_A_1_MOCK, 
                PHOTO_A_2_MOCK,
                PHOTO_A_3_MOCK, 
                # Add a dummy non-existent file path to test error handling and cleanup
                # os.path.join(IMAGE_DIR, "non_existent_photo.jpg") 
            ]
        },
        {
            'asset': 'Sanitary Fixtures',
            'system': 'Plumbing',
            'description': 'Supply and installation of RAK water mixer and angle valves.',
            'quantity': '2 sets',
            'brand': 'RAK Ceramics',
            'comments': 'Leakage reported at the previous mixer.',
            'image_paths': [
                PHOTO_B_1_MOCK,
            ]
        },
        {
            'asset': 'Electrical Fan',
            'system': 'HVAC/Ventilation',
            'description': 'Supply and fix 6" EXHAUST FAN (AS).',
            'quantity': '1',
            'brand': 'XPLARE',
            'comments': 'Old unit is seized. Replacement required.',
            'image_paths': [] # Item without photos
        }
    ]

    # 3. Execution
    logger.info("Starting PDF generation...")
    try:
        pdf_path, pdf_filename = generate_visit_pdf(
            VISIT_INFO_DATA, 
            PROCESSED_ITEMS_DATA, 
            OUTPUT_DIRECTORY, 
            LOGO_PATH_MOCK
        )
        logger.info(f"SUCCESS: PDF created at: {pdf_path}")
        print(f"\n--- PDF successfully generated ---")
        print(f"File: {pdf_filename}")
        print(f"Path: {pdf_path}")
        print(f"----------------------------------")

    except Exception as e:
        logger.error(f"Execution failed. Check the error above and ensure all image paths are correct: {e}")