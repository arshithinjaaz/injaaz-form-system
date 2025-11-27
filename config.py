# config.py

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- GLOBAL PATH CONFIGURATION ---
GENERATED_DIR_NAME = "generated"
GENERATED_DIR = os.path.join(BASE_DIR, GENERATED_DIR_NAME)

# Path for data (Used by the form module to read JSON)
DROPDOWN_DATA_PATH = os.path.join(BASE_DIR, 'data', 'dropdown_data.json')