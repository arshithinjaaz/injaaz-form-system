"""
generate_visit_pdf.py
Robust PDF generator that streams images by URL (Cloudinary) one-by-one, resizes to fit A4,
and writes pages sequentially to avoid high memory usage.

Dependencies: reportlab, Pillow (PIL), requests
"""
import os
import time
import requests
from io import BytesIO
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from PIL import Image

# Timeout for HTTP requests when fetching images
HTTP_TIMEOUT = 20  # seconds

def _fetch_image_bytes(url):
    """Fetch image bytes from URL with a timeout and return a BytesIO or None on failure."""
    try:
        resp = requests.get(url, stream=True, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        buf = BytesIO(resp.content)
        return buf
    except Exception as e:
        print(f"WARNING: Failed to fetch image {url}: {e}")
        return None

def _fit_image_to_page(img, max_w_pts, max_h_pts, dpi=72):
    """
    Resize PIL Image to fit within a width & height in reportlab points (1 pt = 1/72 inch).
    Convert result to a BytesIO JPEG for ImageReader.
    """
    # Convert points to approximate pixels using dpi
    max_px_w = int(max_w_pts * dpi / 72)
    max_px_h = int(max_h_pts * dpi / 72)

    img.thumbnail((max_px_w, max_px_h), Image.LANCZOS)
    out = BytesIO()
    # Save as JPEG to reduce size and ensure compatibility
    img.convert('RGB').save(out, format='JPEG', quality=85)
    out.seek(0)
    return out

def generate_visit_pdf(visit_info, items, output_dir):
    """
    Generates a PDF report for the visit using Cloudinary image URLs in items[*]['image_urls'].

    Returns (pdf_path, pdf_filename)
    """
    timestamp = int(time.time())
    filename = f"site_visit_report_{timestamp}.pdf"
    pdf_path = os.path.join(output_dir, filename)

    try:
        c = canvas.Canvas(pdf_path, pagesize=A4)
        page_w, page_h = A4
        # margins
        left_margin = 40
        right_margin = 40
        top_margin = 60
        bottom_margin = 60

        # Add a cover page with basic info
        c.setFont("Helvetica-Bold", 16)
        title = f"Site Visit Report - {visit_info.get('building_name', 'Unknown')}"
        c.drawString(left_margin, page_h - top_margin, title)
        c.setFont("Helvetica", 10)
        c.drawString(left_margin, page_h - top_margin - 20, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if visit_info.get('client_name'):
            c.drawString(left_margin, page_h - top_margin - 35, f"Client: {visit_info.get('client_name')}")
        c.showPage()

        # Iterate items and their images. Process each image sequentially to limit memory.
        for item_index, item in enumerate(items):
            item_title = item.get('title', f"Item {item_index}")
            c.setFont("Helvetica-Bold", 14)
            c.drawString(left_margin, page_h - top_margin, item_title)
            c.setFont("Helvetica", 10)
            # Optionally include item details (adjust keys as needed)
            details_y = page_h - top_margin - 20
            for key in ('description', 'remarks'):
                if item.get(key):
                    c.drawString(left_margin, details_y, f"{key.capitalize()}: {item.get(key)}")
                    details_y -= 15
            # If no images, create an empty page for item details and continue
            image_urls = item.get('image_urls', []) or []
            if not image_urls:
                c.showPage()
                continue

            # For each image, fetch, resize, and add one page per image (or multiple per page if desired)
            for img_url in image_urls:
                img_buf = _fetch_image_bytes(img_url)
                if not img_buf:
                    # draw a placeholder text for failed image
                    c.setFont("Helvetica", 12)
                    c.drawString(left_margin, page_h - top_margin - 40, f"Image could not be loaded: {img_url}")
                    c.showPage()
                    continue

                # Use PIL to open & resize image to fit the printable area
                try:
                    pil_img = Image.open(img_buf)
                except Exception as e:
                    print(f"WARNING: Pillow failed to open image: {e}")
                    c.setFont("Helvetica", 12)
                    c.drawString(left_margin, page_h - top_margin - 40, f"Invalid image data for: {img_url}")
                    c.showPage()
                    continue

                # Available space on page for image:
                avail_w = page_w - left_margin - right_margin
                avail_h = page_h - top_margin - bottom_margin

                fitted_buf = _fit_image_to_page(pil_img, avail_w, avail_h)
                img_reader = ImageReader(fitted_buf)

                # Compute draw dims based on fitted image size (we saved as JPEG; get size via PIL)
                fitted_img = Image.open(fitted_buf)
                # Convert pixel dims to points: assume 72 DPI for simplicity
                img_px_w, img_px_h = fitted_img.size
                # Place image on page (centered)
                draw_w = min(avail_w, img_px_w * 72.0 / 72.0)
                draw_h = min(avail_h, img_px_h * 72.0 / 72.0)
                x = left_margin + (avail_w - draw_w) / 2
                y = (page_h - bottom_margin) - draw_h - 10  # leave small margin from top

                c.drawImage(img_reader, x, y, width=draw_w, height=draw_h)
                c.showPage()

        c.save()
        return pdf_path, filename
    except Exception as e:
        print(f"ERROR: Failed to generate PDF: {e}")
        # If generation failed, ensure no incomplete file is left
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass
        raise