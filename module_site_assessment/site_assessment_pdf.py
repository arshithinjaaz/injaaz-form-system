import os
import io
import base64
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus.flowables import HRFlowable
import logging

# --- Logging Configuration ---
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# The logic to navigate up one directory to reach the 'static' folder
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOGO_PATH = os.path.join(BASE_DIR, 'static', 'INJAAZ.png') # Assumes static/INJAAZ.png exists

CHECKBOX_CHAR = u'\u2610' # Unicode for empty checkbox
CHECKED_CHAR = u'\u2611' # Unicode for checked box (Used for output)

# --- STYLE DEFINITIONS ---
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='SmallText', fontName='Helvetica', fontSize=8, leading=10))
styles.add(ParagraphStyle(name='BoldTitle', fontName='Helvetica-Bold', fontSize=14, leading=16, textColor=colors.HexColor('#125435')))
styles.add(ParagraphStyle(name='Question', fontName='Helvetica-Bold', fontSize=10, leading=12))
styles.add(ParagraphStyle(name='Answer', fontName='Helvetica', fontSize=10, leading=12))
styles.add(ParagraphStyle(name='ReportHeader', fontName='Helvetica-Bold', fontSize=18, leading=22, alignment=1, textColor=colors.HexColor('#125435')))
styles.add(ParagraphStyle(name='SectionHeader', fontName='Helvetica-Bold', fontSize=12, leading=14, textColor=colors.HexColor('#125435'), spaceBefore=10, spaceAfter=5))


# --- UTILITY FUNCTIONS ---

def get_checkbox_state(value):
    """Converts form string value to a unicode checkbox character."""
    if isinstance(value, str) and value.lower() in ['true', 'yes', '1']:
        return CHECKED_CHAR
    return CHECKBOX_CHAR

def format_value(key, value):
    """Formats the value for display in the PDF."""
    if key in ['date_of_visit'] and value:
        try:
            return datetime.strptime(value, '%Y-%m-%d').strftime('%d %b %Y')
        except ValueError:
            return value 
    if not value:
        return "N/A"
    return str(value)

def decode_image_from_base64(b64_string):
    """Decodes a base64 image string into a BytesIO object."""
    try:
        if b64_string.startswith('data:image'):
            # Strip the data URL header (e.g., 'data:image/png;base64,')
            header, encoded = b64_string.split(',', 1)
        else:
            encoded = b64_string
            
        img_data = base64.b64decode(encoded)
        return io.BytesIO(img_data)
    except Exception as e:
        logger.error(f"Failed to decode base64 image: {e}")
        return None

# --- REPORT STRUCTURE DEFINITION ---

# Define the structure and display names based on your HTML form fields
DATA_MAPPING = {
    "1. Project & Client Details": {
        "client_name": "Client Name",
        "project_name": "Project Name",
        "site_address": "Site Address",
        "date_of_visit": "Date of Visit",
        "key_person_name": "Key Person/Contact Name",
        "contact_number": "Contact Number",
    },
    "2. Site Count & Operations": {
        "room_count": "Room Count (Units)",
        "current_team_size": "Current Team Size (Count)",
        "lift_count_total": "Total Lift Count",
        "current_team_desc": "Current Team Description/Notes",
    },
    "3. Facility Checklist": {
        "facility_floor": "Floors",
        "facility_ground_parking": "Ground/Parking Area",
        "facility_basement": "Basement",
        "facility_podium": "Podium",
        "facility_gym_room": "Gym/Fitness Room",
        "facility_washroom_male": "Male Washroom",
        "facility_washroom_female": "Female Washroom",
        "facility_changing_room": "Changing/Locker Room",
        "facility_play_kids_place": "Kids Play Area",
        "facility_garbage_room": "Garbage/Waste Room",
    },
    "4. Maintenance & Equipment Assessment": {
        "facility_equipment_condition": "Equipment Condition (General)",
        "facility_maintenance_notes": "General Maintenance Notes (Water leaks, damage, etc.)",
        "facility_equipment_notes": "Equipment Specific Notes",
    }
}


# --- MAIN GENERATION FUNCTION ---

def generate_assessment_pdf(assessment_info: dict, photos_data: list):
    """
    Generates the Site Assessment Report PDF.
    
    Args:
        assessment_info (dict): Key-value pairs of all form data.
        photos_data (list): List of base64 photo strings.

    Returns:
        tuple: (BytesIO stream of the PDF, suggested filename string)
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            topMargin=0.5*inch, bottomMargin=0.5*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    Story = []

    # --- 1. HEADER & LOGO ---

    try:
        # Check if the logo file exists and load it
        if os.path.exists(LOGO_PATH):
            logo = Image(LOGO_PATH, width=1.5*inch, height=0.5*inch)
        else:
            logo = Paragraph("INJAAZ", styles['ReportHeader']) # Fallback text
    except Exception as e:
        logger.warning(f"Error loading logo from {LOGO_PATH}: {e}")
        logo = Paragraph("INJAAZ", styles['ReportHeader']) # Fallback text

    # Header Table structure: [Logo] [Report Title] [Date]
    header_data = [
        [logo, Paragraph("<b>SITE ASSESSMENT REPORT</b>", styles['ReportHeader'])]
    ]
    
    header_table = Table(header_data, colWidths=[2.5*inch, 5.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    Story.append(header_table)
    Story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#125435'), spaceBefore=5, spaceAfter=10))


    # --- 2. GENERAL ASSESSMENT DATA ---
    
    for section_name, fields in DATA_MAPPING.items():
        Story.append(Paragraph(section_name, styles['BoldTitle']))
        Story.append(Spacer(1, 0.1 * inch))
        
        table_data = []
        is_checklist_section = "Facility Checklist" in section_name
        
        # Determine columns for this section
        if is_checklist_section:
            # 2 columns for checklist items: [Checkbox + Label] [Spacer]
            col_widths = [3.8*inch, 3.8*inch]
            items = list(fields.items())
            
            # Arrange items into two columns
            col1 = items[:len(items)//2 + (len(items)%2)]
            col2 = items[len(items)//2 + (len(items)%2):]
            
            for (k1, v1), (k2, v2) in zip(col1, col2 + [('', '')] * (len(col1) - len(col2))):
                state1 = get_checkbox_state(assessment_info.get(k1, 'false'))
                state2 = get_checkbox_state(assessment_info.get(k2, 'false'))
                
                p1 = Paragraph(f'<font face="ZapfDingbats">{state1}</font> <b>{v1}</b>', styles['Answer'])
                p2 = Paragraph(f'<font face="ZapfDingbats">{state2}</font> <b>{v2}</b>', styles['Answer'])
                
                # Use empty text as filler if k2 is empty
                table_data.append([p1, p2 if k2 else ''])
                
            
        else:
            # Two columns: [Question] [Answer]
            col_widths = [2.0*inch, 5.6*inch]
            for key, display_name in fields.items():
                value = format_value(key, assessment_info.get(key, ''))
                
                # For multi-line notes, increase the cell height
                if key in ['site_address', 'current_team_desc', 'facility_maintenance_notes', 'facility_equipment_notes']:
                    height_style = [('LEFTPADDING', (0, -1), (-1, -1), 5),
                                    ('TOPPADDING', (0, -1), (-1, -1), 5),
                                    ('BOTTOMPADDING', (0, -1), (-1, -1), 10), # Extra space for notes
                                    ('VALIGN', (0, 0), (-1, -1), 'TOP')]
                else:
                    height_style = [('TOPPADDING', (0, -1), (-1, -1), 2),
                                    ('BOTTOMPADDING', (0, -1), (-1, -1), 2)]
                                    
                table_data.append([
                    Paragraph(f'<b>{display_name}:</b>', styles['Answer']),
                    Paragraph(value, styles['Answer'])
                ])
        
        # Create and style the table
        if table_data:
            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8F8F8')), # Shading for question column
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ] + height_style))
            Story.append(table)
            Story.append(Spacer(1, 0.25 * inch))

    # Force a page break before signatures and photos if necessary, but keep them together
    Story.append(PageBreak()) 
    

    # --- 3. VISUAL EVIDENCE (PHOTOS) ---
    Story.append(Paragraph("5. Visual Evidence and Signatures", styles['BoldTitle']))
    Story.append(Spacer(1, 0.1 * inch))

    # --- Photo Grid ---
    all_photos_data = []

    # Calculate image size: 7.75 inches total width / 2 columns = 3.875 inches per column.
    # We will use max 3.5 inches width per image to allow for padding/spacing.
    img_width = 3.5 * inch
    img_height = 2.5 * inch

    for i in range(0, len(photos_data), 2):
        row = []
        for j in range(2):
            photo_idx = i + j
            if photo_idx < len(photos_data):
                b64_string = photos_data[photo_idx]
                image_stream = decode_image_from_base64(b64_string)
                
                if image_stream:
                    try:
                        # Use a temporary Image flowable to scale and display the image
                        img = Image(image_stream, width=img_width, height=img_height, kind='bound')
                        
                        # Add image and a caption below it
                        caption = Paragraph(f'Photo {photo_idx + 1}', styles['SmallText'])
                        
                        photo_group = [img, Spacer(0, 0.05 * inch), caption, Spacer(0, 0.15 * inch)]
                        row.append(photo_group)
                    except Exception:
                        row.append(Paragraph(f'Image {photo_idx + 1} Failed to Load', styles['Normal']))
                else:
                    row.append(Paragraph(f'Photo {photo_idx + 1} (N/A or Error)', styles['SmallText']))
            else:
                row.append('') # Empty cell for layout balance

        all_photos_data.append(row)
        
    if all_photos_data:
        # 2-column table layout for photos
        photo_table = Table(all_photos_data, colWidths=[3.8*inch, 3.8*inch])
        photo_table.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        Story.append(photo_table)
    else:
        Story.append(Paragraph("No visual evidence (photos) provided for this assessment.", styles['Answer']))


    # --- 4. SIGNATURES (Hardcoded, assuming signature data is base64) ---
    
    Story.append(Spacer(1, 0.5 * inch))
    Story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey, spaceBefore=5, spaceAfter=15))
    Story.append(Paragraph("<b>Signatures</b>", styles['SectionHeader']))

    # Signature fields are currently not in your HTML, so using placeholder/N/A
    # You will need to add hidden inputs for 'tech_signature' and 'contact_signature'
    tech_sig_b64 = assessment_info.get('tech_signature', None)
    contact_sig_b64 = assessment_info.get('contact_signature', None)

    signature_data = []

    # Helper function to create a signature cell
    def create_signature_cell(b64_sig, label):
        if b64_sig:
            image_stream = decode_image_from_base64(b64_sig)
            if image_stream:
                try:
                    img = Image(image_stream, width=2.0*inch, height=0.75*inch, kind='bound')
                    return [img, Paragraph(f'<font size="8">Signed by: <b>{label}</b></font>', styles['SmallText'])]
                except Exception:
                    return [Spacer(1, 0.75*inch), Paragraph(f'<font size="8">Error Loading Signature for <b>{label}</b></font>', styles['SmallText'])]
        
        # Placeholder/N/A
        return [Spacer(1, 0.75*inch), Paragraph(f'<font size="8">Signature Area ({label})</font>', styles['SmallText'])]

    signature_data.append([
        create_signature_cell(tech_sig_b64, "INJAAZ Technician"),
        create_signature_cell(contact_sig_b64, "Client Key Person"),
    ])

    signature_table = Table(signature_data, colWidths=[3.8*inch, 3.8*inch])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    Story.append(signature_table)
    

    # --- 5. BUILD DOCUMENT ---
    doc.build(Story)
    
    # Generate filename
    client_name = assessment_info.get('client_name', 'Client').replace(' ', '_')
    date_of_visit = assessment_info.get('date_of_visit', datetime.now().strftime('%Y%m%d'))
    pdf_filename = f"Site_Assessment_Report_{client_name}_{date_of_visit}.pdf"
    
    buffer.seek(0)
    return buffer, pdf_filename