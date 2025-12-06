import os
import json
import logging
import xlsxwriter
import requests
import time
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- CONFIGURATION ---
CELL_BG_COLOR = '#F2FBF8'
HEADER_COLOR = '#198754'

def create_report_workbook(output_dir, visit_info, processed_items):
    """
    Creates an Excel report (.xlsx) for the site visit and returns the path and filename.
    Signature: (output_dir, visit_info, processed_items)
    This function is defensive: accepts visit_info as dict or JSON string.
    """
    start_time = time.time()

    # Normalize visit_info if it was passed as a JSON string
    if isinstance(visit_info, str):
        try:
            visit_info = json.loads(visit_info)
        except Exception:
            # fallback to empty dict (or keep raw under a key if desired)
            visit_info = {"raw_visit_info": visit_info}
    if visit_info is None:
        visit_info = {}

    # Safe extraction for building_name
    building_name_raw = visit_info.get('building_name') if isinstance(visit_info, dict) else None
    building_name = (building_name_raw or 'Unknown').replace(' ', '_')

    ts = int(time.time())
    excel_filename = f"Site_Visit_Report_{building_name}_{ts}.xlsx"
    excel_path = os.path.join(output_dir, excel_filename)

    try:
        workbook = xlsxwriter.Workbook(excel_path)
    except Exception as e:
        logger.error(f"Failed to create workbook at {excel_path}: {e}")
        return None, None

    worksheet = workbook.add_worksheet('Site Visit Report')

    # --- Define Formats ---
    header_format = workbook.add_format({
        'bold': True, 'font_color': 'white', 'bg_color': HEADER_COLOR,
        'align': 'center', 'valign': 'vcenter', 'border': 1
    })
    title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'left', 'font_color': HEADER_COLOR})
    label_format = workbook.add_format({'bold': True, 'bg_color': CELL_BG_COLOR, 'align': 'left', 'valign': 'top', 'border': 1})
    value_format = workbook.add_format({'align': 'left', 'valign': 'top', 'text_wrap': True, 'border': 1})

    # --- Setup Columns ---
    worksheet.set_column('A:A', 30) # Labels
    worksheet.set_column('B:B', 40) # Values
    worksheet.set_column('C:C', 30) # Secondary Labels
    worksheet.set_column('D:D', 40) # Secondary Values
    worksheet.set_default_row(15)

    row = 0

    # =================================================================
    # 1. Report Header and Details
    # =================================================================
    worksheet.write(row, 0, f"Site Visit Report - {visit_info.get('building_name', 'N/A')}", title_format)
    row += 2

    worksheet.write(row, 0, "1. Visit & Contact Details", title_format)
    row += 1

    details_data = [
        ('Building Name:', visit_info.get('building_name', 'N/A'), 'Date of Visit:', datetime.now().strftime('%Y-%m-%d')),
        ('Site Address:', visit_info.get('building_address', 'N/A'), 'Technician:', visit_info.get('technician_name', 'N/A')),
        ('Contact Person:', visit_info.get('contact_person', 'N/A'), 'Operation Manager:', visit_info.get('opMan_name', 'N/A')),
        ('Contact Number:', visit_info.get('contact_number', 'N/A'), 'Email:', visit_info.get('email', 'N/A')),
    ]

    for label1, value1, label2, value2 in details_data:
        worksheet.write(row, 0, label1, label_format)
        worksheet.write(row, 1, value1, value_format)
        worksheet.write(row, 2, label2, label_format)
        worksheet.write(row, 3, value2, value_format)
        row += 1

    row += 1

    # =================================================================
    # 2. Report Items
    # =================================================================
    worksheet.write(row, 0, "2. Report Items", title_format)
    row += 1

    # Define Item Table Headers
    item_headers = ['Item #', 'Asset', 'System', 'Description', 'Quantity', 'Brand/Model', 'Comments', 'Photo URL']
    worksheet.write_row(row, 0, item_headers, header_format)
    row += 1

    # Define Item Row Column Widths
    worksheet.set_column('A:A', 8) # Item #
    worksheet.set_column('B:B', 25) # Asset
    worksheet.set_column('C:C', 25) # System
    worksheet.set_column('D:D', 30) # Description
    worksheet.set_column('E:E', 10) # Quantity
    worksheet.set_column('F:F', 20) # Brand
    worksheet.set_column('G:G', 50) # Comments
    worksheet.set_column('H:H', 60) # Photo URL (Very wide for links)

    if processed_items:
        for i, item in enumerate(processed_items):
            # Ensure item is dict-like
            if not isinstance(item, dict):
                item = {}

            # Concatenate URLs for the Photo URL column
            image_urls = item.get('image_urls', []) if isinstance(item, dict) else []
            photo_url_string = '\n'.join(image_urls) if image_urls else 'N/A'

            item_row_data = [
                i + 1,
                item.get('asset', 'N/A'),
                item.get('system', 'N/A'),
                item.get('description', 'N/A'),
                item.get('quantity', 'N/A'),
                item.get('brand', 'N/A') or 'N/A',
                item.get('comments', 'N/A') or 'N/A',
                photo_url_string
            ]

            # Write data row. Apply value format with text wrap.
            worksheet.write_row(row, 0, item_row_data, value_format)
            row += 1
    else:
        worksheet.write(row, 0, "No report items were added to this visit.", value_format)
        row += 1

    row += 1

    # =================================================================
    # 3. General Notes
    # =================================================================
    worksheet.write(row, 0, "3. General Notes", title_format)
    row += 1

    notes_text = visit_info.get('general_notes', "No general notes provided.")
    worksheet.write(row, 0, "General Notes:", label_format)
    worksheet.write(row, 1, notes_text, value_format)
    worksheet.set_row(row, 80) # Give the notes row some height
    row += 1

    # =================================================================
    # 4. Signatures (URL Only)
    # =================================================================
    row += 1
    worksheet.write(row, 0, "4. Signatures (Cloudinary URLs)", title_format)
    row += 1

    sig_data = [
        ('Technician Name:', visit_info.get('technician_name', 'N/A'), 'Technician Signature URL:', visit_info.get('tech_signature_url', 'Unsigned')),
        ('Operation Manager Name:', visit_info.get('opMan_name', 'N/A'), 'Operation Manager Signature URL:', visit_info.get('opMan_signature_url', 'Unsigned')),
    ]

    for label1, value1, label2, value2 in sig_data:
        worksheet.write(row, 0, label1, label_format)
        worksheet.write(row, 1, value1, value_format)
        worksheet.write(row, 2, label2, label_format)

        # Write the full URL as a clickable hyperlink
        if value2 and value2 != 'Unsigned':
             try:
                 worksheet.write_url(row, 3, value2, string='Link', tip='Click to view signature image')
             except Exception:
                 worksheet.write(row, 3, value2, value_format)
        else:
             worksheet.write(row, 3, value2, value_format)

        row += 1

    # Close the workbook
    try:
        workbook.close()
        logger.info(f"Excel report finished in {time.time() - start_time:.2f} seconds.")
        return excel_path, excel_filename
    except xlsxwriter.exceptions.FileCreateError as e:
        logger.error(f"Error creating Excel file: {e}")
        return None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Excel generation: {e}")
        return None, None