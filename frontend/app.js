/**
 * app.js - Conceptual Logic for Fan-Out Data Loading
 */

const API_BASE_URL = 'https://moy7eewxxe.execute-api.us-east-2.amazonaws.com/main';

// --- 1. Helper Function to Fetch All Details ---
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function fetchModelDetails(id, model_type) {
    try {
        const [ratingResponse, costResponse, licenseResponse] = await Promise.all([
            fetch(`${API_BASE_URL}/artifact/model/${id}/rate`).then(res => res.json()),
            fetch(`${API_BASE_URL}/artifact/${model_type}/${id}/cost`).then(res => res.json()), // Artifact type assumed to be handled by backend
            //fetch(`${API_BASE_URL}/artifact/model/${id}/license-check`).then(res => res.json()),
        ]);

        return {
            rating: ratingResponse, // e.g., 4.5
            cost: costResponse,      // e.g., 0 or 1.99
            isLicensed: licenseResponse // e.g., true/false
        };
    } catch (error) {
        console.error(`Error fetching details for model ${id}:`, error);
        return { rating: 'N/A', cost: 'N/A', isLicensed: false }; // Return safe defaults
    }
}

// --- 2. Function to Render a Model Card ---
function createModelCard(model, details = { rating: 'N/A', cost: 0, isLicensed: false }) {
    const card = document.createElement('div');
    card.className = 'model-card';
    card.dataset.modelId = model.id || '';

    const typeKey = (model.type || 'model').toLowerCase();
    const iconMap = { model: 'fa-robot', dataset: 'fa-database', source: 'fa-code-branch' };
    const typeIcon = iconMap[typeKey] || 'fa-box';

    const isVetted = details.isLicensed === true;
    const vettedBadge = isVetted
        ? `<span class="badge badge-vetted"><i class="fas fa-shield-alt"></i> VETTED</span>`
        : `<span class="badge badge-risk"><i class="fas fa-exclamation-triangle"></i> RISK</span>`;

    const costDisplay = (typeof details.cost === 'number' && details.cost > 0) ? `$${details.cost.toFixed(2)}` : 'FREE';
    const ratingNum = (typeof details.rating === 'number') ? Math.round(details.rating) : null;
    const ratingStars = ratingNum ? '⭐'.repeat(Math.max(1, Math.min(5, ratingNum))) : 'N/A';

    card.innerHTML = `
        <div class="card-header">
            <h3 class="model-name truncated-name" title="${escapeHtml(model.name || '')}">${escapeHtml(model.name || 'Untitled')}</h3>
            <code class="model-id">ID:${escapeHtml(model.id || '')}</code>
            <span class="type-badge type-${escapeHtml(typeKey)}">${escapeHtml(typeKey).toUpperCase()}</span>
        </div>

        <div class="card-actions">
            <button class="btn btn-ghost btn-details" data-id="${escapeHtml(model.id || '')}">Details</button>
        </div>
    `;

    return card;
}

// --- 3. Main Initialization Function ---

// Function to fetch the initial list of all artifacts
async function init() {
    const modelsGrid = document.getElementById('modelsGrid');
    
    // Initial loading state
    modelsGrid.innerHTML = '<div class="model-card placeholder">Fetching core artifact list...</div>';

    try {
        // Construct the full URL for the /artifacts endpoint
        const fullUrl = `${API_BASE_URL}/artifacts`; 

        const response = await fetch(fullUrl, {
            method: 'POST', 
            
            body: JSON.stringify([{ 
                'name': '*', 
                'types': [] 
            }]),
        });
        
        // --- Essential HTTP Status Check (remains the same) ---
        if (!response.ok) {
            throw new Error(`API Request Failed: ${response.status} ${response.statusText}`);
        }

const artifacts = await response.json();
        
        // --- Rendering Logic ---
        modelsGrid.innerHTML = ''; // Clear loading message
        
        if (artifacts.length === 0) {
            modelsGrid.innerHTML = '<div class="model-card placeholder">No artifacts found in the registry.</div>';
        } else {
            // Step 2: Render initial cards and trigger the fan-out for details
            artifacts.forEach((model) => {
            // create a lightweight placeholder card (fast)
            const placeholderDetails = { rating: 0, cost: 0, isLicensed: false };
            const placeholderCard = createModelCard(model, placeholderDetails);
            placeholderCard.classList.add('loading');
            modelsGrid.appendChild(placeholderCard);

            // fan-out to fetch details and replace the card when done
            fetchModelDetails(model.id, model.type).then((details) => {
                const fullCard = createModelCard(model, details);
                modelsGrid.replaceChild(fullCard, placeholderCard);
            }).catch((err) => {
                // keep placeholder but show error text
                placeholderCard.classList.remove('loading');
                const desc = placeholderCard.querySelector('.model-desc');
                if (desc) desc.textContent = 'Failed to load details';
                console.error(`Details error for ${model.id}:`, err);
            });
        });
        }

    } catch (error) {
        // Display the error in the UI if the fetch itself or the JSON parsing failed
        modelsGrid.innerHTML = `<div class="model-card placeholder" style="background-color: var(--danger-color); color: white;">Error: ${error.message}. Check your API_BASE_URL.</div>`;
        console.error("Initialization failed:", error);
    }
}

// Attach event listener to the search button (mapping to /artifact/byRegEx)
document.getElementById('searchButton').addEventListener('click', () => {
    const query = document.getElementById('searchInput').value;
    // In a real app, this would trigger a function to call the /artifact/byRegEx endpoint
    console.log(`Searching with RegEx: ${query}`);
    // TODO: Implement the fetch logic for search results here.
});


// Initialize the homepage on load
document.addEventListener('DOMContentLoaded', init);


document.getElementById('modelsGrid').addEventListener('click', (ev) => {
    const copyBtn = ev.target.closest('.btn-copy');
    if (copyBtn) {
        const id = copyBtn.dataset.id;
        navigator.clipboard?.writeText(id).then(() => {
            const old = copyBtn.textContent;
            copyBtn.textContent = 'Copied';
            setTimeout(() => copyBtn.textContent = old, 1200);
        }).catch(() => alert(`ID: ${id}`));
        return;
    }
    const detailsBtn = ev.target.closest('.btn-details');
    if (detailsBtn) {
        const id = detailsBtn.dataset.id;
        console.log('Open details for', id);
        // placeholder: wire to a modal/route as needed
        alert(`Open details for ${id}`);
    }
});