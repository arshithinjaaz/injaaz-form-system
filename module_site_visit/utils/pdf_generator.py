import os
import io
import requests
from PIL import Image

# Import reportlab components
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RImage
from reportlab.lib.units import inch
from datetime import datetime

# --- Configuration ---
# You may need to adjust this path based on your main Flask app structure.
def get_logo_path():
    # Assumes INJAAZ.png is in 'module_site_visit/static/'
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(current_dir, '..', 'static', 'INJAAZ.png')
    return logo_path


def get_image_from_url(url, max_width=500, max_height=300):
    """Downloads an image from a URL and returns a ReportLab Image object."""
    try:
        # 1. Download the image data
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status() # Raise exception for bad status codes

        # 2. Use Pillow to open the image from the stream
        img_data = io.BytesIO(response.content)
        img = Image.open(img_data)

        # 3. Determine scaling for ReportLab
        width, height = img.size
        ratio = min(max_width / width, max_height / height)
        
        # 4. Return the ReportLab Image object
        # Use a BytesIO object to pass image data directly to RImage
        return RImage(img_data, width * ratio, height * ratio)
    
    except requests.exceptions.RequestException as e:
        print(f"Error downloading image {url}: {e}")
        # Return a placeholder or skip the image
        return Paragraph(f"<i>[Image failed to load: {url}]</i>", getSampleStyleSheet()['Normal'])
    except Exception as e:
        print(f"Error processing image {url}: {e}")
        return Paragraph(f"<i>[Image failed to process]</i>", getSampleStyleSheet()['Normal'])


def generate_visit_pdf(visit_info, report_items, output_dir):
    """Generates the Site Visit PDF report."""
    
    building_name = visit_info.get('building_name', 'N/A')
    report_date = datetime.now().strftime('%Y-%m-%d')
    pdf_filename = f"Site_Visit_Report_{building_name}_{report_date}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleStyle', fontSize=18, spaceAfter=20, alignment=1))
    styles.add(ParagraphStyle(name='Heading2', fontSize=14, spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name='BodyText', fontSize=10, spaceAfter=5))
    styles.add(ParagraphStyle(name='SignatureText', fontSize=10, spaceBefore=5))

    doc = SimpleDocTemplate(pdf_path, pagesize=letter,
                            leftMargin=inch/2, rightMargin=inch/2,
                            topMargin=inch/2, bottomMargin=inch/2)
    story = []

    # --- Header and Title ---
    try:
        logo_path = get_logo_path()
        if os.path.exists(logo_path):
            logo = RImage(logo_path, width=1.5*inch, height=0.5*inch)
            logo.hAlign = 'LEFT'
            story.append(logo)
    except Exception as e:
        print(f"Logo error: {e}")
        pass
        
    story.append(Paragraph("INJAAZ Site Visit Report", styles['TitleStyle']))
    
    # --- Visit Info Table ---
    info_data = [
        ['Building Name:', building_name, 'Engineer:', visit_info.get('engineer_name', 'N/A')],
        ['Date:', report_date, 'Email:', visit_info.get('email', 'N/A')],
        ['Location:', visit_info.get('location', 'N/A'), 'Ref No:', visit_info.get('reference_number', 'N/A')]
    ]
    info_table = Table(info_data, colWidths=[1.5*inch, 2.5*inch, 1.5*inch, 2.5*inch])
    info_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('BACKGROUND', (2,0), (2,-1), colors.lightgrey),
    ]))
    story.append(Paragraph("<b>Visit Details</b>", styles['Heading2']))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))

    # --- Report Items ---
    story.append(Paragraph("<b>Report Items & Observations</b>", styles['Heading2']))
    
    for item in report_items:
        story.append(Paragraph(f"<b>Asset:</b> {item.get('asset', 'N/A')} | <b>System:</b> {item.get('system', 'N/A')} | <b>Description:</b> {item.get('description', 'N/A')}", styles['BodyText']))
        story.append(Paragraph(f"<b>Observation:</b> {item.get('observation', 'N/A')}", styles['BodyText']))
        story.append(Paragraph(f"<b>Action:</b> {item.get('action', 'N/A')}", styles['BodyText']))
        story.append(Spacer(1, 0.1*inch))
        
        # Images (Horizontal Layout)
        image_elements = []
        for url in item.get('image_urls', []):
            img_obj = get_image_from_url(url, max_width=2.5*inch, max_height=2*inch)
            image_elements.append(img_obj)
            
        if image_elements:
            # Arrange images in a table to float them horizontally
            img_table = Table([image_elements])
            story.append(img_table)
        
        story.append(Spacer(1, 0.3*inch))
        
    # --- Signatures ---
    story.append(Paragraph("<b>Signatures</b>", styles['Heading2']))
    
    tech_sig_url = visit_info.get('tech_signature_url')
    opman_sig_url = visit_info.get('opMan_signature_url')
    
    sig_elements = []
    
    # Technician Signature
    tech_sig_data = [Paragraph("Technician Signature:", styles['SignatureText'])]
    if tech_sig_url:
        tech_sig_img = get_image_from_url(tech_sig_url, max_width=2*inch, max_height=1*inch)
        tech_sig_data.append(tech_sig_img)
    sig_elements.append(tech_sig_data)

    # Op Manager Signature
    opman_sig_data = [Paragraph("Operations Manager Signature:", styles['SignatureText'])]
    if opman_sig_url:
        opman_sig_img = get_image_from_url(opman_sig_url, max_width=2*inch, max_height=1*inch)
        opman_sig_data.append(opman_sig_img)
    sig_elements.append(opman_sig_data)

    # Create a table for signatures to keep them side-by-side
    sig_table = Table([sig_elements], colWidths=[4*inch, 4*inch])
    story.append(sig_table)
    
    # --- Build Document ---
    doc.build(story)
    
    return pdf_path, pdf_filename