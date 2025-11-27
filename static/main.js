// main.js (MODIFIED)

// Declare global variables attached to the window object for universal access
// We initialize window.dropdownData by referencing the global constant DROPDOWN_DATA,
// which must be loaded by the 'dropdown_data.js' script *before* this file runs.
window.dropdownData = DROPDOWN_DATA; // CRITICAL CHANGE: Assign the global constant here
window.pendingItems = []; // Array to hold all report items, including photos
window.techPad = null;
window.opManPad = null;

// Retrieve the main form and pending list container
const form = document.getElementById('visitForm');
const pendingItemsList = document.getElementById('pendingItemsList');


// --- HARDCODED DROPDOWN DATA (REMOVED) ---
// The large hardcoded data block has been REMOVED.
// The data is now expected to be provided by the separate 'dropdown_data.js' file.


// ---------------------------------------------------------------
// 1. Initialization and Data Loading
// ---------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Signature Pads
    const techCanvas = document.getElementById('techSignaturePad');
    const opManCanvas = document.getElementById('opManSignaturePad');
    
    // Check if SignaturePad library is available before initializing
    if (typeof SignaturePad !== 'undefined') {
        if (techCanvas) {
            window.techPad = new SignaturePad(techCanvas, {
                backgroundColor: 'rgb(255, 255, 255)'
            });
        }
        if (opManCanvas) {
            window.opManPad = new SignaturePad(opManCanvas, {
                backgroundColor: 'rgb(255, 255, 255)'
            });
        }
    } else {
        console.error("SignaturePad library is not loaded. Signatures will not work.");
    }
    
    // 2. Initialize Dropdowns (Asset)
    initDropdowns(); // This function now uses the global window.dropdownData
    
    // 3. Render any items that might have been preserved
    renderPendingItems(); 
    
    // 4. Attach event listeners
    document.getElementById('addItemButton').addEventListener('click', addItem);
    
    // Live update of names on signature canvas
    document.getElementById("technician_name").addEventListener("input", function () {
        document.getElementById("techNameDisplay").innerText = this.value || "Technician Name";
    });
    document.getElementById("opMan_name").addEventListener("input", function () {
        document.getElementById("opManNameDisplay").innerText = this.value || "Operation Manager Name";
    });

    // Attach form submission listener to the form element
    form.addEventListener('submit', window.onSubmit); 

    // 5. Setup Cascading Dropdowns
    setupCascadingDropdowns();
});

// Helper function to show a custom modal notification
window.showNotification = function(type, title, body) {
    // Check for the existence of all critical elements before using them.
    const modalElement = document.getElementById('customAlertModal');
    const titleElement = document.getElementById('customAlertTitle');
    const bodyElement = document.getElementById('customAlertBody');
    const iconElement = document.getElementById('customAlertIcon');

    if (!modalElement || typeof bootstrap === 'undefined' || !titleElement || !bodyElement || !iconElement) { 
        console.error("Modal elements or Bootstrap JS not found. Displaying standard alert.");
        // Fallback to standard alert
        alert(`${title}: ${body}`); 
        return;
    }

    const dialogElement = modalElement.querySelector('.modal-content');

    let iconClass = 'fa-circle-info text-info';
    let colorClass = 'border-info';

    switch (type) {
        case 'success':
            iconClass = 'fa-circle-check text-success';
            colorClass = 'border-success';
            break;
        case 'error':
            iconClass = 'fa-circle-xmark text-danger';
            colorClass = 'border-danger';
            break;
        case 'warning':
            iconClass = 'fa-triangle-exclamation text-warning';
            colorClass = 'border-warning';
            break;
    }

    titleElement.textContent = title;
    bodyElement.innerHTML = body; // Use innerHTML to support markdown formatting like **bold**
    
    // Ensure dialogElement is not null before setting its className
    if (dialogElement) {
        dialogElement.className = `modal-content border-start border-5 ${colorClass}`;
    }
    
    iconElement.className = `fas fa-2x me-3 ${iconClass}`;

    // Show the modal using Bootstrap's JS API
    const modal = new bootstrap.Modal(modalElement);
    modal.show();

    // Optionally auto-hide after 5 seconds for success/info messages
    if (type !== 'error') {
        setTimeout(() => {
            modal.hide();
        }, 5000);
    }
}


// ---------------------------------------------------------------
// 2. Dropdown Population and Cascading Logic
// ---------------------------------------------------------------

function initDropdowns() {
    const assetSelect = document.getElementById('assetSelect');
    
    // Clear existing options, but keep a blank option for validation
    assetSelect.innerHTML = '<option value="" selected disabled>Select Asset</option>';
    
    // Populate Asset dropdown using the global window.dropdownData
    Object.keys(window.dropdownData).forEach(asset => {
        const option = document.createElement('option');
        option.value = asset;
        option.textContent = asset;
        assetSelect.appendChild(option);
    });
}

function setupCascadingDropdowns() {
    const assetSelect = document.getElementById('assetSelect');
    const systemSelect = document.getElementById('systemSelect');
    const descriptionSelect = document.getElementById('descriptionSelect');

    assetSelect.addEventListener('change', () => {
        // Clear and reset dependent dropdowns
        systemSelect.innerHTML = '<option value="" selected disabled>Select System</option>';
        descriptionSelect.innerHTML = '<option value="" selected disabled>Select Description</option>';
        systemSelect.disabled = true;
        descriptionSelect.disabled = true;

        // Clear invalid status when a change is made
        assetSelect.classList.remove('is-invalid'); 

        const selectedAsset = assetSelect.value;
        // Use window.dropdownData
        if (selectedAsset && window.dropdownData[selectedAsset]) {
            // Populate System dropdown
            Object.keys(window.dropdownData[selectedAsset]).forEach(system => {
                const option = document.createElement('option');
                option.value = system;
                option.textContent = system;
                systemSelect.appendChild(option);
            });
            systemSelect.disabled = false;
        }
    });

    systemSelect.addEventListener('change', () => {
        // Clear and reset Description dropdown
        descriptionSelect.innerHTML = '<option value="" selected disabled>Select Description</option>';
        descriptionSelect.disabled = true;
        
        // Clear invalid status when a change is made
        systemSelect.classList.remove('is-invalid');

        const selectedAsset = assetSelect.value;
        const selectedSystem = systemSelect.value;
        
        // Use window.dropdownData
        if (selectedAsset && selectedSystem && window.dropdownData[selectedAsset] && window.dropdownData[selectedAsset][selectedSystem]) {
            // Populate Description dropdown
            window.dropdownData[selectedAsset][selectedSystem].forEach(description => {
                const option = document.createElement('option');
                option.value = description;
                option.textContent = description;
                descriptionSelect.appendChild(option);
            });
            descriptionSelect.disabled = false;
        }
    });

    descriptionSelect.addEventListener('change', () => {
        // Clear invalid status when a change is made
        descriptionSelect.classList.remove('is-invalid');
    });
}

// ---------------------------------------------------------------
// 3. Pending Items Rendering
// ---------------------------------------------------------------

function renderPendingItems() {
    if (!pendingItemsList) return; // Add check for pendingItemsList existence
    
    pendingItemsList.innerHTML = '';
    
    if (window.pendingItems.length === 0) {
        pendingItemsList.innerHTML = '<p class="text-muted text-center" id="emptyListMessage">No report items added yet.</p>';
        return;
    }

    window.pendingItems.forEach((item, index) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'report-item';
        itemDiv.innerHTML = `
            <div class="item-details">
                <strong>Item ${index + 1}:</strong> ${item.asset} / ${item.system} / ${item.description}
                ${item.brand ? ` | Brand: ${item.brand}` : ''}
                ${item.quantity > 1 ? ` | Qty: ${item.quantity}` : ''}
                <div class="text-muted small">
                    ${item.comments ? `Comment: ${item.comments}` : 'No Comments.'} 
                    (${item.photos.length} Photo${item.photos.length !== 1 ? 's' : ''})
            </div>
            </div>
            <div class="item-actions">
                <button type="button" class="btn btn-sm btn-danger" onclick="removeItem(${index})">
                    <i class="fas fa-trash"></i> Remove
                </button>
            </div>
        `;
        pendingItemsList.appendChild(itemDiv);
    });
}

// ---------------------------------------------------------------
// 4. Remove Item Logic
// ---------------------------------------------------------------

window.removeItem = function(index) {
    if (index >= 0 && index < window.pendingItems.length) {
        window.pendingItems.splice(index, 1);
        renderPendingItems();
        showNotification('info', 'Item Removed', `Report item ${index + 1} has been removed from the list.`);
    }
}

// ---------------------------------------------------------------
// 5. New Item Addition Logic 
// ---------------------------------------------------------------

window.addItem = async function() {
    const assetSelect = document.getElementById('assetSelect');
    const systemSelect = document.getElementById('systemSelect');
    const descriptionSelect = document.getElementById('descriptionSelect');
    const photoInput = document.getElementById('photoInput');
    const quantityInput = document.getElementById('quantityInput');
    const brandInput = document.getElementById('brandInput');
    const commentsTextarea = document.getElementById('commentsTextarea');
    
    const addItemButton = document.getElementById('addItemButton');
    // Disable button to prevent double-click during photo processing
    if (addItemButton) addItemButton.disabled = true; 

    // --- Input Validation: Manually check validity on required dropdowns ---
    
    let isValid = true;
    const requiredSelects = [assetSelect, systemSelect, descriptionSelect];

    requiredSelects.forEach(select => {
        // Use checkValidity() to leverage the HTML 'required' attribute validation messages/state
        if (!select.checkValidity()) {
            select.classList.add('is-invalid');
            isValid = false;
        } else {
            select.classList.remove('is-invalid');
        }
    });
    
    if (!isValid) {
        showNotification('error', 'Validation Error', 'Please select **Asset**, **System**, and **Description** before adding an item.');
        if (addItemButton) addItemButton.disabled = false;
        return;
    }
    
    // -------------------------------------------------------------------------

    // 1. Process Photos asynchronously: Convert File objects to Base64 strings
    const photoPromises = Array.from(photoInput.files).map(file => {
        return new Promise((resolve, reject) => { 
            const reader = new FileReader();
            reader.onload = (e) => resolve({
                fileName: file.name,
                mimeType: file.type,
                // Extract base64 data part (after the comma)
                base64Data: e.target.result.split(',')[1] 
            });
            reader.onerror = reject; 
            reader.readAsDataURL(file);
        });
    });

    try {
        const photos = await Promise.all(photoPromises);

        // 2. Create the new item object
        const newItem = {
            asset: assetSelect.value,
            system: systemSelect.value,
            description: descriptionSelect.value,
            quantity: parseInt(quantityInput.value) || 1, // Default to 1 if not a valid number
            brand: brandInput.value.trim(),
            comments: commentsTextarea.value.trim(),
            photos: photos
        };

        // 3. Add to the pending list
        window.pendingItems.push(newItem);

        // 4. Update the UI
        renderPendingItems();
        showNotification('success', 'Item Added', `Successfully added 1 item: ${newItem.asset} / ${newItem.system} / ${newItem.description}.`); 

        // 5. Reset the "Add Item" form fields (keep Asset selection)
        // Note: Keeping the asset selection for quick entry of multiple items on the same asset.
        systemSelect.value = '';
        systemSelect.disabled = true;
        descriptionSelect.value = '';
        descriptionSelect.disabled = true;
        quantityInput.value = '1';
        brandInput.value = '';
        commentsTextarea.value = '';
        photoInput.value = ''; // Clear file input
        
    } catch (e) {
        showNotification('error', 'Photo Processing Error', `Failed to read photo files. Details: ${e.message}`);
    } finally {
        if (addItemButton) addItemButton.disabled = false; // Re-enable button
    }
}


// ---------------------------------------------------------------
// 6. Form Submission Logic 
// ---------------------------------------------------------------

// Helper function to trigger a programmatic download (New)
const triggerDownload = (url) => {
    const a = document.createElement('a');
    a.href = url;
    a.download = ''; // This tells the browser to download the file
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
};

window.onSubmit = async function(event) {
    event.preventDefault(); // Stop default form submission

    const submitButton = document.getElementById('nextButton'); // CRITICAL: Use 'nextButton' not 'submitButton' for the last step

    // Find the technician name input to preserve its value later
    const technicianNameInput = document.getElementById('technician_name');

    // Disable button during submission
    if (submitButton) {
        submitButton.disabled = true; 
    }
    
    const alertDiv = document.getElementById('submission-alert');
    const statusText = document.getElementById('status'); 

    // Reset status display 
    if (alertDiv) alertDiv.className = 'alert d-none';
    if (alertDiv) alertDiv.textContent = '';
    if (statusText) statusText.textContent = 'Submitting...';

    // --- 1. Collect Form Data ---
    const formData = new FormData(form);
    const visitInfo = {};
    formData.forEach((value, key) => {
        // Exclude signatures (which are handled separately below) from the form data loop
        if (key !== 'tech_signature' && key !== 'opMan_signature') { 
            visitInfo[key] = value;
        }
    });

    // Store the technician name before resetting the form
    const technicianNameBeforeReset = technicianNameInput ? technicianNameInput.value : '';

    // --- 2. Collect Signatures ---
    // Note: Signatures are captured in site_visit_form.html into hidden inputs 
    // before this function is called, but we will rely on the global pad objects
    // for safety, though the form data extraction is technically cleaner.
    const techSignatureData = window.techPad ? window.techPad.toDataURL() : '';
    const opManSignatureData = window.opManPad ? window.opManPad.toDataURL() : '';
    
    const payload = {
        visit_info: visitInfo,
        report_items: window.pendingItems,
        signatures: {
             tech_signature: techSignatureData,
             opMan_signature: opManSignatureData
        }
    };

    // --- 3. Validation for Submission ---
    
    const technicianName = payload.visit_info.technician_name;
    const techSignatureLength = techSignatureData.length;

    if (!technicianName) {
        showNotification('error', 'Submission Failed', 'Technician Name is required (Tab 1).');
        if (submitButton) submitButton.disabled = false;
        return;
    }
    
    // Check if signature data is generated (length > a small threshold)
    if (!techSignatureData || techSignatureLength < 100) { 
        showNotification('error', 'Submission Failed', 'Technician signature is required (Tab 3).');
        if (submitButton) submitButton.disabled = false;
        return;
    }
    
    if (payload.report_items.length === 0) {
        showNotification('error', 'Submission Failed', 'At least one Report Item is required (Tab 2).');
        if (submitButton) submitButton.disabled = false;
        return;
    }

    // --- 4. AJAX Submission ---
    try {
        // FIX: Changed submission URL from '/submit' to '/site-visit/submit' 
        // to match the Flask Blueprint configuration in Injaaz.py
        const response = await fetch('/site-visit/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok) {
            
            // --- NEW: Trigger Automatic Downloads ---
            triggerDownload(result.pdf_url);
            triggerDownload(result.excel_url);
            
            // Success State
            if (statusText) statusText.textContent = 'Report Submitted Successfully!';
            if (alertDiv) {
                alertDiv.classList.add('alert-success', 'd-block');
                alertDiv.innerHTML = `The site visit report has been successfully submitted. Documents should be downloading automatically. You can also download them manually: 
                    <a href="${result.pdf_url}" class="alert-link" target="_blank">PDF</a> | 
                    <a href="${result.excel_url}" class="alert-link" target="_blank">Excel</a>`; 
            }

            // Clear data after successful submission
            window.pendingItems = [];
            renderPendingItems();
            if (window.techPad) window.techPad.clear();
            if (window.opManPad) window.opManPad.clear();
            
            // Reset the form fields
            if (form) form.reset();
            
            // CRITICAL CHANGE: Preserve and restore technician name after reset
            if (technicianNameInput) {
                technicianNameInput.value = technicianNameBeforeReset;
                // Manually trigger the input event handler to update the display name
                technicianNameInput.dispatchEvent(new Event('input'));
            }

            // Re-initialize dropdowns to ensure the Asset dropdown is set back to 'Select Asset'
            initDropdowns();
            
        } else {
            // Error State from Server (status 400 or 500)
            if (statusText) statusText.textContent = 'Submission Failed!';
            if (alertDiv) {
                alertDiv.classList.add('alert-danger', 'd-block');
                const errorMsg = result.error || response.statusText;
                alertDiv.textContent = `Server Error: ${errorMsg}`;
            }
            showNotification('error', 'Submission Failed', `The server reported an error: **${result.error || response.statusText}**`);
        }

    } catch (error) {
        // Network/Catch Error State
        if (statusText) statusText.textContent = 'Submission Failed!';
        if (alertDiv) {
            alertDiv.classList.add('alert-danger', 'd-block');
            alertDiv.textContent = `Network Error: Could not connect to the server or process the request. ${error.message}`;
        }
        showNotification('error', 'Network Error', `Could not connect to the server or process the request. Details: **${error.message}**`);
    } finally {
        // Re-enable the submit button
        if (submitButton) {
            submitButton.disabled = false;
        }
    }
}