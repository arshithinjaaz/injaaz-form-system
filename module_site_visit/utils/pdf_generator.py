import os
import time
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import logging
import io # Included for modern Python standards, though not used for image streams here
from PIL import Image as PilImage # Included if image processing/resizing is ever needed

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

# --- IMAGE HANDLERS (Direct File Access) ---

def get_sig_image_from_path(file_path, name):
    """Loads signature from a file path into a ReportLab Image object."""
    if file_path and os.path.exists(file_path):
        try:
            sig_img = Image(file_path)
            sig_img.drawHeight = 0.7 * inch
            sig_img.drawWidth = 2.5 * inch
            sig_img.hAlign = 'LEFT' 
            return sig_img
        except Exception as e:
            logger.error(f"Failed to load signature image for {name} from {file_path}: {e}")
            return Paragraph(f'Image Load Failed: {name}', styles['Normal'])
        
    return Paragraph(f'Unsigned: {name}', styles['Normal']) 

def get_image_from_path(file_path, width, height, placeholder_text="No Photo"):
    """Loads a photo from a file path into a ReportLab Image object."""
    if not file_path or not os.path.exists(file_path):
        # Fallback to text placeholder if file is missing
        return Paragraph(f'<font size="8">{placeholder_text}</font>', styles['SmallText'])
    try:
        # Check image dimensions to resize before ReportLab consumes it (Good practice for large uploads)
        # We rely on ReportLab's built-in handling if PIL is not used for resizing.
        img = Image(file_path)
        img.drawWidth = width
        img.drawHeight = height
        img.hAlign = 'CENTER' 
        return img
    except Exception as e:
        logger.error(f"Image load error for path {file_path}: {e}")
        return Paragraph(f'<font size="8">Image Load Error</font>', styles['SmallText'])

# --- TEMPLATE HANDLER FOR FOOTER ---
FOOTER_TEXT = "PO BOX, 3456 Ajman, UAE | Tel +971 6 7489813 | Fax +971 6 711 6701 | www.injaaz.ae | Member of Ajman Holding group"

def page_layout_template(canvas, doc):
    """Function to draw the custom footer on every page."""
    canvas.saveState()
    
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#666666'))
    
    # Calculate the footer position 
    footer_y = doc.bottomMargin - 0.25 * inch 
    canvas.drawCentredString(A4[0] / 2, footer_y, FOOTER_TEXT)
    
    canvas.setStrokeColor(GRID_COLOR)
    canvas.setLineWidth(0.5)
    # Draw the line slightly above the footer text
    canvas.line(doc.leftMargin, footer_y + 0.15 * inch, A4[0] - doc.rightMargin, footer_y + 0.15 * inch)
    
    # Draw page number next to the footer text
    canvas.drawRightString(A4[0] - doc.rightMargin, footer_y, f"Page {canvas.getPageNumber()}")

    canvas.restoreState()

# --- MAIN REPORT STRUCTURE ---

def create_signature_table(visit_info):
    """Creates the signature block (Section 4)."""
    sig_story = []
    
    sig_story.append(Spacer(1, 0.3*inch))
    sig_story.append(Paragraph('4. Signatures', styles['BoldTitle'])) 
    sig_story.append(Spacer(1, 0.1*inch)) 

    # Retrieve file paths saved in app.py
    tech_sig_path = visit_info.get('tech_signature_path')
    opMan_sig_path = visit_info.get('opMan_signature_path')

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

def build_report_story(visit_info, processed_items, logo_path):
    """Generates the platypus story (content) for the PDF."""
    story = []
    PAGE_WIDTH = 7.27 * inch # A4 width (8.27 in) - margins (1.0 in)
    
    # --- 1. Header and Title with Logo ---
    title_text = f"Site Visit Report - {visit_info.get('building_name', 'N/A')}"
    title_paragraph = Paragraph(f"<b>{title_text}</b>", styles['BoldTitle'])

    logo = Paragraph('', styles['Normal'])
    try:
        if os.path.exists(logo_path):
            logo_img = Image(logo_path)
            logo_img.drawWidth = 0.8 * inch 
            logo_img.drawHeight = 0.7 * inch 
            logo_img.hAlign = 'RIGHT' 
            logo = logo_img
        else:
            logger.warning(f"Logo not found at: {logo_path}")
    except Exception as e:
        logger.error(f"Failed to load logo image: {e}")

    header_data = [[title_paragraph, logo]]
    header_table = Table(header_data, colWidths=[PAGE_WIDTH - 1.0 * inch, 1.0 * inch]) 
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 0.2*inch))


    # --- 2. Visit & Contact Details (Section 1) ---
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
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, GRID_COLOR),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 0.2*inch))


    # --- 3. Report Items (Section 2) ---
    story.append(Paragraph('2. Report Items', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))
    
    if processed_items:
        for i, item in enumerate(processed_items):
            # Item Details
            story.append(Paragraph(f"<b>Item {i + 1}:</b> {item['asset']} / {item['system']}", styles['Question']))
            story.append(Spacer(1, 0.05*inch))
            
            # Details Table for each item
            item_details = [
                ['Description:', item['description'], 'Quantity:', item['quantity']],
                ['Brand/Model:', item['brand'] or 'N/A', 'Comments:', item['comments'] or 'N/A']
            ]
            
            item_table = Table(item_details, colWidths=[1.5*inch, 2.135*inch, 1.5*inch, 2.135*inch])
            item_table.setStyle(TableStyle([
                ('TEXTCOLOR', (0, 0), (0, -1), BRAND_COLOR),
                ('TEXTCOLOR', (2, 0), (2, -1), BRAND_COLOR),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(item_table)
            
            # Photos for this item (if available) - Start a new section if photos exist
            if item.get('image_paths'):
                story.append(Spacer(1, 0.1*inch)) # Space above photo section
                
                # Photo Label
                photo_label_data = [[Paragraph('<b>Photos:</b>', styles['Question'])]]
                photo_label_table = Table(photo_label_data, colWidths=[PAGE_WIDTH])
                photo_label_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9F9F9')),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                ]))
                story.append(photo_label_table)

                image_elements = []
                for path in item['image_paths']:
                    # Use smaller dimensions for multi-column layout
                    img = get_image_from_path(path, 2.2 * inch, 1.7 * inch, placeholder_text="Photo N/A")
                    image_elements.append(img)

                # Arrange images into rows of 3 (adjusting width for 3 columns on A4)
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

    # --- 4. General Notes (Section 3) ---
    story.append(Paragraph('3. General Notes', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))

    # Placeholder text since 'General Notes' wasn't explicitly in the input data
    notes_text = visit_info.get('general_notes', "No general notes provided.")
    
    notes_data = [[Paragraph(notes_text, styles['Answer'])]]
    notes_table = Table(notes_data, colWidths=[PAGE_WIDTH], rowHeights=[0.8*inch])
    notes_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, GRID_COLOR),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(notes_table)
    
    # --- 5. Signatures (Section 4) ---
    story.extend(create_signature_table(visit_info))
    
    return story

# --- MAIN GENERATOR FUNCTION ---

def generate_visit_pdf(visit_info, processed_items, output_dir):
    """
    Main function to generate the PDF report.
    NOTE: It uses LOGO_PATH defined globally in this script.
    """
    # NOTE: LOGO_PATH must be accessible. Replicating the logic from your input:
    try:
        current_file_path = os.path.abspath(__file__)
        # Assuming the script is in 'utils' and 'static' is next to 'utils'
        LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(current_file_path)), 'static', 'INJAAZ.png')
    except NameError:
        # Fallback if __file__ is not defined (e.g., in a script runner)
        LOGO_PATH = os.path.join(os.getcwd(), 'static', 'INJAAZ.png') 
        logger.warning("Using current working directory for logo path fallback.")
    
    building_name = visit_info.get('building_name', 'Unknown').replace(' ', '_')
    # Using time.time() for unique filename timestamp
    ts = int(time.time())
    pdf_filename = f"Site_Visit_Report_{building_name}_{ts}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=0.5 * inch, leftMargin=0.5 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.75 * inch)
                            
    Story = build_report_story(visit_info, processed_items, LOGO_PATH)
    
    try:
        doc.build(
            Story, 
            onFirstPage=page_layout_template, 
            onLaterPages=page_layout_template
        )
        return pdf_path, pdf_filename
    except Exception as e:
        logger.error(f"FATAL PDF GENERATION ERROR: {e}")
        raise

if __name__ == "__main__":
    
    # --- EXECUTION BLOCK FOR TESTING ---
    
    # 1. Configuration and Paths
    OUTPUT_DIRECTORY = os.path.join(os.getcwd(), "generated_reports_simple") 
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True) 
    
    IMAGE_DIR = os.path.join(os.getcwd(), "test_images_simple")
    os.makedirs(IMAGE_DIR, exist_ok=True) 
    
    # --- Mock Image Creation (Ensuring it runs locally) ---
    def create_mock_image(filepath, size, color):
        if not os.path.exists(filepath):
            try:
                img = PilImage.new('RGB', size, color=color)
                d = ImageDraw.Draw(img)
                d.text((10, 10), os.path.basename(filepath), fill=(0,0,0))
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                img.save(filepath)
            except Exception as e:
                logger.error(f"Could not create mock image at {filepath}: {e}")
                
    LOGO_PATH_MOCK = os.path.join(IMAGE_DIR, "INJAAZ.png")
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
    create_mock_image(PHOTO_A_1_MOCK, (1000, 800), 'lightblue') 
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
        'general_notes': 'Confirmed all requested inspections and maintenance tasks were completed successfully.',
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
            'image_paths': [] 
        }
    ]

    # 3. Execution
    logger.info("Starting PDF generation...")
    try:
        # Pass the mock logo path to the main function for the test run
        pdf_path, pdf_filename = generate_visit_pdf(
            VISIT_INFO_DATA, 
            PROCESSED_ITEMS_DATA, 
            OUTPUT_DIRECTORY
        )
        logger.info(f"SUCCESS: PDF created at: {pdf_path}")
        print(f"\n--- PDF successfully generated ---")
        print(f"File: {pdf_filename}")
        print(f"Path: {pdf_path}")
        print(f"----------------------------------")

    except Exception as e:
        logger.error(f"Execution failed: {e}")