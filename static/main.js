// main.js (FULL CODE OPTIMIZED FOR SUBMISSION SPEED)

// Declare global variables attached to the window object for universal access
window.dropdownData = DROPDOWN_DATA; 
window.pendingItems = []; // Array to hold all report items, including the (now resized) file objects
window.techPad = null;
window.opManPad = null;
const MAX_PHOTOS = 10; // Limit for photos per item

// Retrieve the main form and pending list container
const form = document.getElementById('visitForm');
const pendingItemsList = document.getElementById('pendingItemsList');


// ---------------------------------------------------------------
// 1. Initialization, Data Loading, and Utility Functions
// ---------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Signature Pads
    const techCanvas = document.getElementById('techSignaturePad');
    const opManCanvas = document.getElementById('opManSignaturePad');
    
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
    initDropdowns(); 
    
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
    const modalElement = document.getElementById('customAlertModal');
    const titleElement = document.getElementById('customAlertTitle');
    const bodyElement = document.getElementById('customAlertBody');
    const iconElement = document.getElementById('customAlertIcon');

    if (!modalElement || typeof bootstrap === 'undefined' || !titleElement || !bodyElement || !iconElement) { 
        console.error("Modal elements or Bootstrap JS not found. Displaying standard alert.");
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
    bodyElement.innerHTML = body;
    
    if (dialogElement) {
        dialogElement.className = `modal-content border-start border-5 ${colorClass}`;
    }
    
    iconElement.className = `fas fa-2x me-3 ${iconClass}`;

    const modal = new bootstrap.Modal(modalElement);
    modal.show();

    if (type !== 'error') {
        setTimeout(() => {
            modal.hide();
        }, 5000);
    }
}

// --- Image Resizing and Compression Function (Core Logic) ---
function resizeImage(file, maxWidth, maxHeight, quality) {
    return new Promise((resolve) => {
        // Skip non-image files gracefully
        if (!file || !file.type.startsWith('image/')) {
            resolve(file); 
            return;
        }

        const reader = new FileReader();
        reader.onload = function(e) {
            const img = new Image();
            img.onload = function() {
                let width = img.width;
                let height = img.height;

                // If image is already small, skip canvas resizing
                if (width <= maxWidth && height <= maxHeight) {
                    resolve(file);
                    return;
                }

                // Calculate new dimensions to fit within maxWidth/maxHeight
                if (width > height) {
                    if (width > maxWidth) {
                        height *= maxWidth / width;
                        width = maxWidth;
                    }
                } else {
                    if (height > maxHeight) {
                        width *= maxHeight / height;
                        height = maxHeight;
                    }
                }

                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;

                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                // Convert canvas content to a compressed image Blob
                canvas.toBlob((blob) => {
                    if (!blob) {
                        console.error("Failed to create Blob from canvas.");
                        resolve(file); 
                        return;
                    }

                    // Create a new File object from the compressed Blob
                    const resizedFile = new File([blob], file.name.replace(/\.[^/.]+$/, ".jpg"), {
                        type: 'image/jpeg', 
                        lastModified: Date.now()
                    });
                    
                    resolve(resizedFile);
                }, 'image/jpeg', quality); // Use JPEG compression with specified quality
            };
            img.onerror = function() {
                resolve(file); 
            };
            reader.readAsDataURL(file); // Load the file as a data URL for the Image object
        };
        reader.onerror = function() {
            resolve(file); 
        };
    });
}


// ---------------------------------------------------------------
// 2. Dropdown Population and Cascading Logic 
// ---------------------------------------------------------------

function initDropdowns() {
    const assetSelect = document.getElementById('assetSelect');
    
    assetSelect.innerHTML = '<option value="" selected disabled>Select Asset</option>';
    
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
        systemSelect.innerHTML = '<option value="" selected disabled>Select System</option>';
        descriptionSelect.innerHTML = '<option value="" selected disabled>Select Description</option>';
        systemSelect.disabled = true;
        descriptionSelect.disabled = true;

        assetSelect.classList.remove('is-invalid'); 

        const selectedAsset = assetSelect.value;
        if (selectedAsset && window.dropdownData[selectedAsset]) {
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
        descriptionSelect.innerHTML = '<option value="" selected disabled>Select Description</option>';
        descriptionSelect.disabled = true;
        
        systemSelect.classList.remove('is-invalid');

        const selectedAsset = assetSelect.value;
        const selectedSystem = systemSelect.value;
        
        if (selectedAsset && selectedSystem && window.dropdownData[selectedAsset] && window.dropdownData[selectedAsset][selectedSystem]) {
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
        descriptionSelect.classList.remove('is-invalid');
    });
}

// ---------------------------------------------------------------
// 3. Pending Items Rendering & Removal 
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

window.removeItem = function(index) {
    if (index >= 0 && index < window.pendingItems.length) {
        window.pendingItems.splice(index, 1);
        renderPendingItems();
        showNotification('info', 'Item Removed', `Report item ${index + 1} has been removed from the list.`);
    }
}

// ---------------------------------------------------------------
// 4. New Item Addition Logic - OPTIMIZED FOR SUBMISSION SPEED
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
    const rawFiles = Array.from(photoInput.files);

    // --- Input Validation ---
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
        return; 
    }
    
    // --- Photo Limit Check ---
    if (rawFiles.length > MAX_PHOTOS) {
        showNotification('warning', 'Photo Limit Exceeded', `Please upload a maximum of ${MAX_PHOTOS} photos per item. You selected ${rawFiles.length}.`);
        return; // Exit before starting processing
    }

    // Disable button and show processing status
    if (addItemButton) {
        addItemButton.disabled = true; 
        addItemButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing Photos (0/${rawFiles.length})...`; 
    }
    
    // --- CRITICAL STEP: Resize all photos using Promises ---
    let processedCount = 0;
    
    // 🔥🔥 RE-APPLYING SPEED OPTIMIZATION: Max 600px wide/tall, 40% JPEG quality 🔥🔥
    const resizePromises = rawFiles.map(file => {
        // Target: Max 600px wide/tall, 40% JPEG quality
        return resizeImage(file, 600, 600, 0.4).then(resizedFile => {
            processedCount++;
            // Update the status text after each photo
            if (addItemButton) {
                addItemButton.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Processing Photos (${processedCount}/${rawFiles.length})...`;
            }
            return resizedFile;
        });
    });
    
    let resizedPhotos = [];
    
    try {
        // Wait for ALL promises to resolve (photos to be resized/compressed)
        resizedPhotos = await Promise.all(resizePromises); 

        // 1. Create the new item object
        const newItem = {
            asset: assetSelect.value,
            system: systemSelect.value,
            description: descriptionSelect.value,
            quantity: parseInt(quantityInput.value) || 1, 
            brand: brandInput.value.trim(),
            comments: commentsTextarea.value.trim(),
            photos: resizedPhotos // Store the new, smaller File objects
        };

        // 2. Add to the pending list
        window.pendingItems.push(newItem);

        // 3. Update the UI
        renderPendingItems();
        showNotification('success', 'Item Added', `Successfully added 1 item: ${newItem.asset} / ${newItem.system} / ${newItem.description} with ${resizedPhotos.length} photo(s).`); 

        // 4. Reset the "Add Item" form fields (keep Asset selection)
        systemSelect.value = '';
        systemSelect.disabled = true;
        descriptionSelect.value = '';
        descriptionSelect.disabled = true;
        quantityInput.value = '1';
        brandInput.value = '';
        commentsTextarea.value = '';
        photoInput.value = ''; // Clear file input
        
    } catch (e) {
        showNotification('error', 'Item Processing Error', `Failed to process/resize photos. Details: ${e.message}`);
    } finally {
        if (addItemButton) {
            addItemButton.disabled = false; // Re-enable button
            addItemButton.innerHTML = '<i class="fas fa-plus me-2"></i>Add Item'; // Restore button text
        }
    }
}


// ---------------------------------------------------------------
// 5. Form Submission Logic 
// ---------------------------------------------------------------

// Helper function to trigger a programmatic download
const triggerDownload = (url) => {
    const a = document.createElement('a');
    a.href = url;
    a.download = ''; 
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
};

window.onSubmit = async function(event) {
    event.preventDefault(); 

    const submitButton = document.getElementById('nextButton'); 
    const technicianNameInput = document.getElementById('technician_name');
    const opManNameInput = document.getElementById('opMan_name'); // Get OpMan input for name reset UX
    
    if (submitButton) {
        submitButton.disabled = true; 
    }
    
    const alertDiv = document.getElementById('submission-alert');
    const statusText = document.getElementById('status'); 

    if (alertDiv) alertDiv.className = 'alert d-none';
    if (alertDiv) alertDiv.textContent = '';
    if (statusText) statusText.textContent = 'Submitting...';

    // --- 1. Collect Form Data (Non-file fields) ---
    const formData = new FormData(form); 
    const visitInfo = {};
    formData.forEach((value, key) => {
        if (key !== 'tech_signature' && key !== 'opMan_signature' && form.elements[key].type !== 'file') { 
            visitInfo[key] = value;
        }
    });

    const technicianNameBeforeReset = technicianNameInput ? technicianNameInput.value : '';
    const opManNameBeforeReset = opManNameInput ? opManNameInput.value : ''; // Preserve OpMan name

    // --- 2. Collect Signatures (Still Base64 for small data) ---
    const techSignatureData = window.techPad ? window.techPad.toDataURL() : '';
    const opManSignatureData = window.opManPad ? window.opManPad.toDataURL() : '';
    
    // --- 3. Create JSON Data Structure (without the actual file objects) ---
    const cleanItems = window.pendingItems.map(item => {
        const { photos, ...itemDetails } = item; 
        itemDetails.photo_count = item.photos.length; 
        return itemDetails;
    });

    const payloadData = {
        visit_info: visitInfo,
        report_items: cleanItems,
        signatures: {
            tech_signature: techSignatureData,
            opMan_signature: opManSignatureData
        }
    };
    
    // --- 4. Validation for Submission ---
    const technicianName = payloadData.visit_info.technician_name;
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
    
    if (payloadData.report_items.length === 0) {
        showNotification('error', 'Submission Failed', 'At least one Report Item is required (Tab 2).');
        if (submitButton) submitButton.disabled = false;
        return;
    }

    // --- 5. CRITICAL: Assemble Final FormData for Submission ---
    const finalFormData = new FormData();
    
    // 5a. Append the main data payload as a JSON string under the key 'data'
    finalFormData.append('data', JSON.stringify(payloadData)); 
    
    // 5b. Append the actual File objects (photos)
    window.pendingItems.forEach((item, itemIndex) => {
        item.photos.forEach((file, photoIndex) => {
            const key = `photo-item-${itemIndex}-${photoIndex}`;
            finalFormData.append(key, file, file.name); 
        });
    });
    
    if (statusText) statusText.textContent = 'Uploading data and photos...';

    // --- 6. AJAX Submission with FormData ---
    try {
        const response = await fetch('/site-visit/submit', {
            method: 'POST',
            body: finalFormData 
        });

        const result = await response.json();

        if (response.ok) {
            // Success State
            triggerDownload(result.pdf_url);
            triggerDownload(result.excel_url);
            
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
            // 🐛 FIX: Corrected typo (was window.opPad)
            if (window.opManPad) window.opManPad.clear(); 
            
            // Reset the form fields
            if (form) form.reset();
            
            // Preserve and restore technician name after reset
            if (technicianNameInput) {
                technicianNameInput.value = technicianNameBeforeReset;
                technicianNameInput.dispatchEvent(new Event('input'));
                
                // ✨ FIX: Update the signature name displays after form reset
                document.getElementById("techNameDisplay").innerText = technicianNameBeforeReset || "Technician Name";
                document.getElementById("opManNameDisplay").innerText = opManNameBeforeReset || "Operation Manager Name";
            }

            // Re-initialize dropdowns
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
}``