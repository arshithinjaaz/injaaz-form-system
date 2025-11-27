import os
import time
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import logging

# --- Logging Configuration ---
logger = logging.getLogger(__name__)

# --- CONFIGURATION & BRANDING ---
# Brand Color: #198754 (Dark Green/Teal)
BRAND_COLOR = colors.HexColor('#198754') 
ACCENT_BG_COLOR = colors.HexColor('#F2FBF8') # Lighter shade for table headers
GRID_COLOR = colors.HexColor('#CCCCCC')

# NOTE: The logo path must be accessible from where this script runs.
# We assume 'static/INJAAZ.png' is at the root level relative to the utils folder.
# Adjusted path relative to the script's location (assuming utils is one level down)
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'INJAAZ.png')


# Initialize styles
styles = getSampleStyleSheet()

# BoldTitle is used for section headings like "1. Visit & Contact Details"
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

# --- HELPER FUNCTIONS ---

def get_sig_image_from_path(file_path, name):
    """Loads signature from a temporary file path into a ReportLab Image object."""
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

def create_signature_table(visit_info):
    """Creates the signature block."""
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
    
    # Matching the column width from your template
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

def get_image_from_path(file_path, width, height, placeholder_text="No Photo"):
    """Loads image from a temporary file path into a ReportLab Image object."""
    if not file_path or not os.path.exists(file_path):
        return Paragraph(f'<font size="8">{placeholder_text}</font>', styles['SmallText'])
    try:
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

# --- MAIN GENERATOR FUNCTION ---

def generate_visit_pdf(visit_info, processed_items, output_dir):
    
    building_name = visit_info.get('building_name', 'Unknown').replace(' ', '_')
    # Using time.time() for unique filename timestamp
    ts = int(time.time())
    pdf_filename = f"Site_Visit_Report_{building_name}_{ts}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    # Adjust margins slightly for A4 and custom layout
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=0.5 * inch, leftMargin=0.5 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.75 * inch)
                            
    Story = build_report_story(visit_info, processed_items)
    
    doc.build(
        Story, 
        onFirstPage=page_layout_template, 
        onLaterPages=page_layout_template
    )
    
    return pdf_path, pdf_filename


def build_report_story(visit_info, processed_items):
    story = []
    
    # --- 1. Header and Title with Logo ---
    title_text = f"Site Visit Report - {visit_info.get('building_name', 'N/A')}"
    title_paragraph = Paragraph(title_text, styles['BoldTitle'])

    logo = Paragraph('', styles['Normal'])
    try:
        if os.path.exists(LOGO_PATH):
            logo = Image(LOGO_PATH)
            # Adjusted size for A4 width
            logo.drawWidth = 0.8 * inch 
            logo.drawHeight = 0.7 * inch 
            logo.hAlign = 'RIGHT' 
    except Exception as e:
        logger.warning(f"Logo not found or failed to load: {e}")

    # Use A4 width (8.27 inches) minus margins (0.5 + 0.5 = 1.0 inch) gives 7.27 inch for table width
    PAGE_WIDTH = 7.27 * inch 
    
    header_data = [[title_paragraph, logo]]
    header_table = Table(header_data, colWidths=[PAGE_WIDTH - 1.0 * inch, 1.0 * inch]) 
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 0.2*inch))


    # --- 2. Visit & Contact Details (Based on your template Block 1) ---
    story.append(Paragraph('1. Visit & Contact Details', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))
    
    details_data = [
        [Paragraph('<b>Building Name:</b>', styles['Question']), visit_info.get('building_name', 'N/A'), Paragraph('<b>Date of Visit:</b>', styles['Question']), datetime.now().strftime('%Y-%m-%d')],
        [Paragraph('<b>Site Address:</b>', styles['Question']), visit_info.get('building_address', 'N/A'), Paragraph('<b>Technician:</b>', styles['Question']), visit_info.get('technician_name', 'N/A')],
        [Paragraph('<b>Contact Person:</b>', styles['Question']), visit_info.get('contact_person', 'N/A'), Paragraph('<b>Operation Manager:</b>', styles['Question']), visit_info.get('opMan_name', 'N/A')],
        [Paragraph('<b>Contact Number:</b>', styles['Question']), visit_info.get('contact_number', 'N/A'), Paragraph('<b>Email:</b>', styles['Question']), visit_info.get('email', 'N/A')]
    ]

    details_table = Table(details_data, colWidths=[1.5*inch, 2.135*inch, 1.5*inch, 2.135*inch]) # Total width 7.27 inch
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), ACCENT_BG_COLOR), # Light accent background
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, GRID_COLOR),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 0.2*inch))


    # --- 3. Report Items ---
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
            
            # Reusing the column widths from the details table
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
            if item.get('image_paths'):
                
                # Use a smaller table for photos with a light background
                photo_label_data = [[Paragraph('<b>Photos:</b>', styles['Question'])]]
                photo_label_table = Table(photo_label_data, colWidths=[PAGE_WIDTH])
                photo_label_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9F9F9')),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                ]))
                story.append(photo_label_table)

                image_elements = []
                for path in item['image_paths']:
                    img = get_image_from_path(path, 2.2 * inch, 1.7 * inch, placeholder_text="Photo N/A")
                    image_elements.append(img)

                # Arrange images into rows of 3 (adjusting width for 3 columns on A4)
                num_cols = 3
                col_width = PAGE_WIDTH / num_cols # ~2.42 inch
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

    # --- BLOCK 4: Notes and Observation (Used as a general comments block) ---
    story.append(Paragraph('3. General Notes', styles['BoldTitle']))
    story.append(Spacer(1, 0.1*inch))

    notes_text = "No general notes provided." # Placeholder if no dedicated notes field exists 
    
    # We will use the 'comments' from the main report items if they exist, or just leave this space.
    # Since your old template had a dedicated 'Notes' block, we'll keep this structure.
    # If the user only provides notes in the item's 'comments', they appear under the item.
    notes_data = [[Paragraph(notes_text, styles['Answer'])]]
    notes_table = Table(notes_data, colWidths=[PAGE_WIDTH], rowHeights=[0.8*inch])
    notes_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, GRID_COLOR),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(notes_table)
    
    # --- BLOCK 5: Signatures (Now section 4) ---
    story.extend(create_signature_table(visit_info))
    
    return story