// main.js (CRITICAL UPDATE: Switched to FormData for File Uploads)

// Declare global variables attached to the window object for universal access
window.dropdownData = DROPDOWN_DATA; 
// CRITICAL CHANGE: 'photos' inside each item will now store File objects, NOT Base64 strings.
window.pendingItems = []; 
window.techPad = null;
window.opManPad = null;

const form = document.getElementById('visitForm');
const pendingItemsList = document.getElementById('pendingItemsList');

// ... (Initialization, Data Loading, Dropdown Logic, Notification function remain the same) ...

// ---------------------------------------------------------------
// 3. Pending Items Rendering (Minor Update for File Count)
// ---------------------------------------------------------------

function renderPendingItems() {
    if (!pendingItemsList) return; 
    
    pendingItemsList.innerHTML = '';
    
    if (window.pendingItems.length === 0) {
        pendingItemsList.innerHTML = '<p class="text-muted text-center" id="emptyListMessage">No report items added yet.</p>';
        return;
    }

    window.pendingItems.forEach((item, index) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'report-item';
        // Note: item.photos is now an array of File objects. item.photos.length is correct.
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

// ... (Remove Item Logic remains the same) ...


// ---------------------------------------------------------------
// 5. New Item Addition Logic - CRITICAL CHANGE FOR FILES
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
    // Disable button to prevent double-click
    if (addItemButton) addItemButton.disabled = true; 

    // --- Input Validation: Manually check validity on required dropdowns ---
    
    let isValid = true;
    const requiredSelects = [assetSelect, systemSelect, descriptionSelect];

    requiredSelects.forEach(select => {
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

    // CRITICAL CHANGE: Do NOT convert files to Base64. Store the raw File objects.
    const photos = Array.from(photoInput.files);
    
    try {
        // 1. Create the new item object
        const newItem = {
            asset: assetSelect.value,
            system: systemSelect.value,
            description: descriptionSelect.value,
            quantity: parseInt(quantityInput.value) || 1, 
            brand: brandInput.value.trim(),
            comments: commentsTextarea.value.trim(),
            // Store raw File objects
            photos: photos 
        };

        // 2. Add to the pending list
        window.pendingItems.push(newItem);

        // 3. Update the UI
        renderPendingItems();
        showNotification('success', 'Item Added', `Successfully added 1 item with ${photos.length} photo(s).`); 

        // 4. Reset the "Add Item" form fields
        systemSelect.value = '';
        systemSelect.disabled = true;
        descriptionSelect.value = '';
        descriptionSelect.disabled = true;
        quantityInput.value = '1';
        brandInput.value = '';
        commentsTextarea.value = '';
        photoInput.value = ''; // Clear file input
        
    } catch (e) {
        showNotification('error', 'Item Creation Error', `Failed to process item details. Details: ${e.message}`);
    } finally {
        if (addItemButton) addItemButton.disabled = false; // Re-enable button
    }
}


// ---------------------------------------------------------------
// 6. Form Submission Logic - CRITICAL CHANGE FOR FormData
// ---------------------------------------------------------------

// ... (triggerDownload helper function remains the same) ...

window.onSubmit = async function(event) {
    event.preventDefault(); // Stop default form submission

    const submitButton = document.getElementById('nextButton'); 

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

    // --- 1. Collect Visit Info (Text Fields) ---
    const formBaseData = new FormData(form);
    const visitInfo = {};
    formBaseData.forEach((value, key) => {
        // Exclude signatures from the initial loop, but include all other text fields
        if (key !== 'tech_signature' && key !== 'opMan_signature') { 
            visitInfo[key] = value;
        }
    });

    const technicianNameBeforeReset = technicianNameInput ? technicianNameInput.value : '';

    // --- 2. Collect Signatures (Still Base64 for simplicity as they are small) ---
    const techSignatureData = window.techPad ? window.techPad.toDataURL() : '';
    const opManSignatureData = window.opManPad ? window.opManPad.toDataURL() : '';
    
    // --- 3. Build the core JSON payload (WITHOUT photos) ---
    const payloadDataOnly = {
        visit_info: visitInfo,
        // CRITICAL: We pass the list of items, but replace the 'photos' array of Files 
        // with a placeholder, as the actual files are sent separately.
        report_items: window.pendingItems.map(item => {
            const { photos, ...itemDetails } = item;
            // The itemDetails object now contains all fields *except* the File objects.
            // We can add an empty 'photos' array here, or remove it, as the backend will ignore it anyway.
            return itemDetails;
        }),
        signatures: {
            tech_signature: techSignatureData,
            opMan_signature: opManSignatureData
        }
    };
    
    // --- 4. Validation for Submission (Remains the same) ---
    const technicianName = payloadDataOnly.visit_info.technician_name;
    const techSignatureLength = techSignatureData.length;

    if (!technicianName) {
        showNotification('error', 'Submission Failed', 'Technician Name is required (Tab 1).');
        if (submitButton) submitButton.disabled = false;
        return;
    }
    
    if (!techSignatureData || techSignatureLength < 100) { 
        showNotification('error', 'Submission Failed', 'Technician signature is required (Tab 3).');
        if (submitButton) submitButton.disabled = false;
        return;
    }
    
    if (window.pendingItems.length === 0) {
        showNotification('error', 'Submission Failed', 'At least one Report Item is required (Tab 2).');
        if (submitButton) submitButton.disabled = false;
        return;
    }
    
    // --- 5. Create Final FormData for Transmission ---
    const finalFormData = new FormData();
    
    // CRITICAL 1: Append the entire JSON payload as a single string field named 'data'
    finalFormData.append('data', JSON.stringify(payloadDataOnly)); 
    
    // CRITICAL 2: Iterate through all pending items and append raw files
    let photoIndex = 0;
    window.pendingItems.forEach((item, itemIndex) => {
        item.photos.forEach((file) => {
            // Append the actual File object. Name it uniquely: 'photo-item-INDEX-COUNT'
            // The itemIndex is critical for the server to match the file to the correct item.
            const fileKey = `photo-item-${itemIndex}-${photoIndex}`;
            finalFormData.append(fileKey, file, file.name);
            photoIndex++;
        });
    });

    // --- 6. AJAX Submission (using FormData) ---
    try {
        const response = await fetch('/site-visit/submit', {
            method: 'POST',
            // CRITICAL: DO NOT set Content-Type header when sending FormData! 
            // The browser must set it automatically with the correct boundary.
            // headers: { 'Content-Type': 'multipart/form-data' } <-- REMOVED!
            body: finalFormData
        });

        const result = await response.json();

        if (response.ok) {
            
            // --- Success Logic (Remains the same) ---
            triggerDownload(result.pdf_url);
            triggerDownload(result.excel_url);
            
            if (statusText) statusText.textContent = 'Report Submitted Successfully!';
            if (alertDiv) {
                alertDiv.classList.add('alert-success', 'd-block');
                alertDiv.innerHTML = `...`; 
            }

            // Clear data after successful submission
            window.pendingItems = [];
            renderPendingItems();
            if (window.techPad) window.techPad.clear();
            if (window.opManPad) window.opManPad.clear();
            
            if (form) form.reset();
            
            if (technicianNameInput) {
                technicianNameInput.value = technicianNameBeforeReset;
                technicianNameInput.dispatchEvent(new Event('input'));
            }

            initDropdowns();
            
        } else {
            // Error State from Server
            if (statusText) statusText.textContent = 'Submission Failed!';
            if (alertDiv) {
                alertDiv.classList.add('alert-danger', 'd-block');
                const errorMsg = result.error || response.statusText;
                alertDiv.textContent = `Server Error: ${errorMsg}`;
            }
            showNotification('error', 'Submission Failed', `The server reported an error: **${result.error || response.statusText}**`);
        }

    } catch (error) {
        // Network/Catch Error State (This is where the old 'Unexpected end of JSON input' occurred)
        if (statusText) statusText.textContent = 'Submission Failed!';
        if (alertDiv) {
            alertDiv.classList.add('alert-danger', 'd-block');
            alertDiv.textContent = `Network Error: Could not connect to the server or process the request. ${error.message}`;
        }
        showNotification('error', 'Network Error', `Could not connect to the server or process the request. Details: **${error.message}**`);
    } finally {
        if (submitButton) {
            submitButton.disabled = false;
        }
    }
}