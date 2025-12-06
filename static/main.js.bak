// main.js (UPDATED FOR CLOUDINARY DIRECT UPLOAD + BACKGROUND JOB POLLING)

// Declare global variables attached to the window object for universal access
window.dropdownData = typeof DROPDOWN_DATA !== 'undefined' ? DROPDOWN_DATA : {}; // safe fallback
window.pendingItems = [];
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
    const addBtn = document.getElementById('addItemButton');
    if (addBtn) addBtn.addEventListener('click', addItem);

    // Live update of names on signature canvas
    const techNameEl = document.getElementById("technician_name");
    const opManNameEl = document.getElementById("opMan_name");
    if (techNameEl) techNameEl.addEventListener("input", function () {
        const el = document.getElementById("techNameDisplay");
        if (el) el.innerText = this.value || "Technician Name";
    });
    if (opManNameEl) opManNameEl.addEventListener("input", function () {
        const el = document.getElementById("opManNameDisplay");
        if (el) el.innerText = this.value || "Operation Manager Name";
    });

    // Attach form submission listener to the form element
    if (form) form.addEventListener('submit', window.onSubmit);

    // 5. Setup Cascading Dropdowns
    setupCascadingDropdowns();
});

// Helper function to show a custom modal notification (UNMODIFIED)
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

// --- Image Resizing and Compression Function (UNMODIFIED) ---
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
// 2. Dropdown Population and Cascading Logic (UNMODIFIED)
// ---------------------------------------------------------------

function initDropdowns() {
    const assetSelect = document.getElementById('assetSelect');
    if (!assetSelect) return;

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

    if (!assetSelect || !systemSelect || !descriptionSelect) return;

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
// 3. Pending Items Rendering & Removal (UNMODIFIED)
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
// 4. New Item Addition Logic (UNMODIFIED)
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
    const rawFiles = photoInput ? Array.from(photoInput.files) : [];

    // --- Input Validation ---
    let isValid = true;
    const requiredSelects = [assetSelect, systemSelect, descriptionSelect];

    requiredSelects.forEach(select => {
        if (!select || !select.checkValidity()) {
            if (select) select.classList.add('is-invalid');
            isValid = false;
        } else {
            if (select) select.classList.remove('is-invalid');
        }
    });

    if (!isValid) {
        showNotification('error', 'Validation Error', 'Please ensure Asset, System, and Description are selected before adding an item.');
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

    // Max 600px wide/tall, 40% JPEG quality
    const resizePromises = rawFiles.map(file => {
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
            brand: brandInput ? brandInput.value.trim() : '',
            comments: commentsTextarea ? commentsTextarea.value.trim() : '',
            photos: resizedPhotos // Store the new, smaller File objects
        };

        // 2. Add to the pending list
        window.pendingItems.push(newItem);

        // 3. Update the UI
        renderPendingItems();
        showNotification('success', 'Item Added', `Successfully added 1 item: ${newItem.asset} / ${newItem.system} / ${newItem.description} with ${resizedPhotos.length} photo(s).`);

        // 4. Reset the "Add Item" form fields (keep Asset selection)
        if (systemSelect) { systemSelect.value = ''; systemSelect.disabled = true; }
        if (descriptionSelect) { descriptionSelect.value = ''; descriptionSelect.disabled = true; }
        if (quantityInput) quantityInput.value = '1';
        if (brandInput) brandInput.value = '';
        if (commentsTextarea) commentsTextarea.value = '';
        if (photoInput) photoInput.value = ''; // Clear file input

    } catch (e) {
        showNotification('error', 'Item Processing Error', `Failed to process/resize photos. Details: ${e.message || e}`);
    } finally {
        if (addItemButton) {
            addItemButton.disabled = false; // Re-enable button
            addItemButton.innerHTML = '<i class="fas fa-plus me-2"></i>Add Item'; // Restore button text
        }
    }
}


// ---------------------------------------------------------------
// 5. Form Submission Logic - REWRITTEN FOR CLOUDINARY DIRECT UPLOAD
// ---------------------------------------------------------------

// Helper function to trigger a programmatic download (UNMODIFIED)
const triggerDownload = (url) => {
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
};

/**
 * PHASE 2: Uploads photos directly to Cloudinary and sends the final URLs to the server.
 * Uses Promise.allSettled to allow partial failures to be handled.
 * @param {string} visitId - The report ID received from the server.
 * @param {string} cloudName - The Cloudinary Cloud Name.
 * @param {string} uploadPreset - The Cloudinary Upload Preset.
 */
async function uploadPhotosToCloudinary(visitId, cloudName, uploadPreset) {
    const finalPhotoUrls = [];
    let successfulUploads = 0;
    const allPhotosEntries = []; // { item_index, photo_index, file }

    // Build file list mapped to item/photo indices
    window.pendingItems.forEach((item, item_index) => {
        (item.photos || []).forEach((fileToUpload, photo_index) => {
            if (fileToUpload && fileToUpload.type && fileToUpload.type.startsWith('image/')) {
                allPhotosEntries.push({ item_index, photo_index, file: fileToUpload });
            }
        });
    });

    const totalPhotos = allPhotosEntries.length;
    if (totalPhotos === 0) {
        // If there are no photos, inform the server of an empty array (Phase 2 still needs to run)
        const updateResponse = await fetch(`/api/submit/update-photos?visit_id=${visitId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ photo_urls: [] })
        });
        const updateResult = await updateResponse.json();
        if (!updateResponse.ok || updateResult.status !== 'success') {
            throw new Error('Server failed to update photo URLs (no photos case).');
        }
        return; // Nothing else to upload
    }

    const statusText = document.getElementById('status');
    if (statusText) statusText.textContent = `Uploading 0/${totalPhotos} photos directly to Cloudinary...`;

    // Create upload tasks
    const uploadPromises = allPhotosEntries.map(entry => {
        return (async () => {
            const { item_index, photo_index, file } = entry;
            const formData = new FormData();
            formData.append('file', file);
            formData.append('upload_preset', uploadPreset);

            // Optionally add metadata tags
            // formData.append('context', `item_index=${item_index}|photo_index=${photo_index}`);

            const CLOUDINARY_URL = `https://api.cloudinary.com/v1_1/${cloudName}/image/upload`;

            try {
                const resp = await fetch(CLOUDINARY_URL, { method: 'POST', body: formData });
                if (!resp.ok) {
                    // try to parse JSON error body
                    let errBody = '';
                    try { errBody = JSON.stringify(await resp.json()); } catch (_) { errBody = resp.statusText; }
                    throw new Error(`Cloudinary upload failed (status ${resp.status}): ${errBody}`);
                }
                const uploadResult = await resp.json();
                if (uploadResult && uploadResult.secure_url) {
                    successfulUploads++;
                    if (statusText) statusText.textContent = `Uploading ${successfulUploads}/${totalPhotos} photos directly to Cloudinary...`;
                    // push mapping for server
                    finalPhotoUrls.push({
                        item_index,
                        photo_index,
                        photo_url: uploadResult.secure_url
                    });
                    return { status: 'fulfilled', value: uploadResult.secure_url };
                } else {
                    const errMsg = (uploadResult && uploadResult.error && uploadResult.error.message) || 'Unknown Cloudinary response';
                    throw new Error(errMsg);
                }
            } catch (err) {
                console.error("Cloudinary Upload Error:", err);
                return { status: 'rejected', reason: err, entry };
            }
        })();
    });

    // Wait for all uploads to settle
    const settled = await Promise.all(uploadPromises);

    // Check for failures
    const failures = settled.filter(r => r && r.status === 'rejected');
    if (failures.length > 0) {
        // Build a friendly message
        const failCount = failures.length;
        const msg = `${failCount} photo upload(s) failed. Please retry uploading those photos.`;
        console.error(msg, failures);
        showNotification('error', 'Upload Error', `${msg} Check console for details.`);
        throw new Error(msg);
    }

    // Sort finalPhotoUrls for consistent ordering (optional)
    finalPhotoUrls.sort((a, b) => {
        if (a.item_index !== b.item_index) return a.item_index - b.item_index;
        return a.photo_index - b.photo_index;
    });

    // --- PHASE 2b: SEND FINAL URLS TO SERVER ---
    if (statusText) statusText.textContent = 'All photos uploaded. Notifying server of final URLs...';

    const updateResponse = await fetch(`/api/submit/update-photos?visit_id=${visitId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ photo_urls: finalPhotoUrls })
    });

    const updateResult = await updateResponse.json();

    if (!updateResponse.ok || updateResult.status !== 'success') {
        throw new Error('Server failed to update photo URLs after Cloudinary upload.');
    }
}

// Polling helper for background job status (used after finalize returns 202 Accepted)
function pollReportStatus(statusUrl, onProgress, onDone, intervalMs = 4000, timeoutMs = 1000 * 60 * 15) {
    const start = Date.now();
    const timer = setInterval(async () => {
        try {
            const res = await fetch(statusUrl);
            if (!res.ok) {
                // 404 or other codes are possible; inform progress callback
                const text = await res.text();
                console.warn('Status check failed:', res.status, text);
                if (onProgress) onProgress({ status: 'unknown' });
                return;
            }
            const data = await res.json();
            const report = data.report || data;
            if (onProgress) onProgress(report);

            if (report && (report.status === 'done' || report.status === 'failed')) {
                clearInterval(timer);
                onDone(null, report);
                return;
            }
        } catch (err) {
            console.error('Polling error', err);
            if (onProgress) onProgress({ status: 'error', error: err.message || err });
        }

        // Timeout handling
        if (Date.now() - start > timeoutMs) {
            clearInterval(timer);
            onDone(new Error('Report generation timed out'), null);
        }
    }, intervalMs);

    return () => clearInterval(timer); // returns a cancel function
}

window.onSubmit = async function(event) {
    event.preventDefault();

    const submitButton = document.getElementById('nextButton');
    const technicianNameInput = document.getElementById('technician_name');
    const opManNameInput = document.getElementById('opMan_name');

    if (submitButton) submitButton.disabled = true;

    const alertDiv = document.getElementById('submission-alert');
    const statusText = document.getElementById('status');

    if (alertDiv) alertDiv.className = 'alert d-none';
    if (statusText) statusText.textContent = 'Preparing submission...';

    // --- 1. Collect Metadata and Signatures ---
    const formData = new FormData(form);
    const visitInfo = {};
    formData.forEach((value, key) => {
        // Skip signature fields and file fields
        const el = form.elements[key];
        if (key !== 'tech_signature' && key !== 'opMan_signature' && !(el && el.type === 'file')) {
            visitInfo[key] = value;
        }
    });

    const technicianNameBeforeReset = technicianNameInput ? technicianNameInput.value : '';
    const opManNameBeforeReset = opManNameInput ? opManNameInput.value : '';

    const techSignatureData = window.techPad ? window.techPad.toDataURL() : '';
    const opManSignatureData = window.opManPad ? window.opManPad.toDataURL() : '';

    // --- Prepare Metadata Payload (Without File Objects) ---
    const metadataItems = window.pendingItems.map(item => {
        const { photos, ...itemDetails } = item;
        itemDetails.photo_count = (item.photos || []).length;
        return itemDetails;
    });

    const payloadData = {
        visit_info: visitInfo,
        report_items: metadataItems,
        signatures: {
            tech_signature: techSignatureData,
            opMan_signature: opManSignatureData
        }
    };

    // --- 2. Validation ---
    const technicianName = payloadData.visit_info.technician_name;
    if (!technicianName || !techSignatureData || techSignatureData.length < 100 || payloadData.report_items.length === 0) {
        showNotification('error', 'Submission Failed', 'Please ensure Name, Signature, and at least one Report Item are present.');
        if (submitButton) submitButton.disabled = false;
        return;
    }

    let visitId = null;

    try {
        // --- 3. PHASE 1: Submit Metadata to Server & Get CLOUDINARY CONFIG ---
        if (statusText) statusText.textContent = 'Submitting metadata and requesting Cloudinary configuration...';
        const metadataResponse = await fetch('/api/submit/metadata', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payloadData)
        });

        const metadataResult = await metadataResponse.json();

        if (!metadataResponse.ok || metadataResult.status !== 'success') {
            throw new Error(metadataResult.error || `Server error: ${metadataResponse.status}`);
        }

        // --- CRITICAL: Get Cloudinary details from server ---
        const CLOUDINARY_CLOUD_NAME = metadataResult.cloudinary_cloud_name;
        const CLOUDINARY_UPLOAD_PRESET = metadataResult.cloudinary_upload_preset;
        visitId = metadataResult.visit_id;

        if (!CLOUDINARY_CLOUD_NAME || !CLOUDINARY_UPLOAD_PRESET || !visitId) {
             throw new Error("Missing Cloudinary configuration or visit_id from server. Check server environment variables and response.");
        }

        // --- 4. PHASE 2: Upload Photos Directly to CLOUDINARY & Save URLs to Server ---
        if (statusText) statusText.textContent = 'Uploading photos to Cloudinary...';
        await uploadPhotosToCloudinary(visitId, CLOUDINARY_CLOUD_NAME, CLOUDINARY_UPLOAD_PRESET);

        // --- 5. PHASE 3: Finalize Report & Enqueue PDF Generation on Server ---
        if (statusText) statusText.textContent = 'All photos uploaded. Finalizing report and generating documents...';

        const finalizeResponse = await fetch(`/api/submit/finalize?visit_id=${visitId}`, { method: 'GET' });
        const finalizeResult = await finalizeResponse.json();

        if (!finalizeResponse.ok && finalizeResponse.status !== 202) {
            // Some servers return 200 with error structure; account for that
            throw new Error(finalizeResult.error || `Finalize failed with status ${finalizeResponse.status}`);
        }

        // If server accepted background job
        if (finalizeResponse.status === 202 || finalizeResult.status === 'accepted') {
            const statusUrl = finalizeResult.status_url || finalizeResult.status_url || `/api/report-status?visit_id=${visitId}`;
            showNotification('info', 'Report Queued', 'Report generation is running in the background. We will notify when it is ready.');

            // Poll the status URL
            pollReportStatus(statusUrl,
                (progressObj) => {
                    // onProgress - update UI
                    if (statusText) {
                        const p = progressObj.progress || progressObj.status || JSON.stringify(progressObj);
                        statusText.textContent = `Processing: ${p}`;
                    }
                },
                (err, report) => {
                    if (err) {
                        showNotification('error', 'Report Failed', `Report generation failed or timed out. Details: ${err.message || err}`);
                        if (submitButton) submitButton.disabled = false;
                        return;
                    }
                    if (report.status === 'done') {
                        if (report.pdf_url) {
                            // trigger downloads for PDF (and Excel if provided)
                            triggerDownload(report.pdf_url);
                        }
                        // If server returned excel/other URLs inside report, handle them
                        if (report.excel_url) {
                            triggerDownload(report.excel_url);
                        }
                        // Show success and clear UI
                        showNotification('success', 'Report Ready', 'Your report has been generated.');
                        if (statusText) statusText.textContent = 'Report generation complete.';
                        // Clear data
                        window.pendingItems = [];
                        renderPendingItems();
                        if (window.techPad) window.techPad.clear();
                        if (window.opManPad) window.opManPad.clear();
                        if (form) form.reset();
                        // Restore names if needed
                        if (technicianNameInput) {
                            technicianNameInput.value = technicianNameBeforeReset;
                            technicianNameInput.dispatchEvent(new Event('input'));
                            const el = document.getElementById("opManNameDisplay");
                            if (el) el.innerText = opManNameBeforeReset || "Operation Manager Name";
                        }
                        initDropdowns();
                        if (submitButton) submitButton.disabled = false;
                    } else if (report.status === 'failed') {
                        showNotification('error', 'Report Failed', report.error || 'Unknown error occurred while generating report.');
                        if (submitButton) submitButton.disabled = false;
                    } else {
                        // unexpected final-state: show info
                        showNotification('warning', 'Report Status', `Final report state: ${JSON.stringify(report)}`);
                        if (submitButton) submitButton.disabled = false;
                    }
                },
                4000,
                1000 * 60 * 15 // 15 minute timeout
            );

        } else {
            // Server returned synchronous success (older path). Download returned URLs.
            if (finalizeResult.pdf_url) {
                triggerDownload(finalizeResult.pdf_url);
            }
            if (finalizeResult.excel_url) {
                triggerDownload(finalizeResult.excel_url);
            }
            showNotification('success', 'Report Submitted', 'Report generated synchronously.');
            // Clear UI (same as above)
            window.pendingItems = [];
            renderPendingItems();
            if (window.techPad) window.techPad.clear();
            if (window.opManPad) window.opManPad.clear();
            if (form) form.reset();
            if (technicianNameInput) {
                technicianNameInput.value = technicianNameBeforeReset;
                technicianNameInput.dispatchEvent(new Event('input'));
                const el = document.getElementById("opManNameDisplay");
                if (el) el.innerText = opManNameBeforeReset || "Operation Manager Name";
            }
            initDropdowns();
            if (submitButton) submitButton.disabled = false;
        }

    } catch (error) {
        // Catch any network or process error (metadata or upload)
        console.error("Submission Error:", error);
        showNotification('error', 'Submission Interrupted', `A critical step failed. Details: ${error.message || error}`);
        if (submitButton) submitButton.disabled = false;
        if (statusText) statusText.textContent = 'Submission failed.';
    }
}