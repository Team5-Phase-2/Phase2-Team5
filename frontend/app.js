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

async function searchArtifacts(query) {
    const modelsGrid = document.getElementById('modelsGrid');
    const searchButton = document.getElementById('searchButton');
    const searchInput = document.getElementById('searchInput');

    // 💡 CHANGE 2: Handle empty query immediately (Before API call)
    if (!query || query.trim() === '') {
        console.log('Empty search query. Redirecting to home (init).');
        
        // Reset loading state if it somehow got set
        searchButton.disabled = false; 
        searchInput.disabled = false;
        searchButton.innerHTML = searchButton.originalButtonContent || '<i class="fas fa-search"></i> Search';

        // Call your initialization function to reload the full artifact list
        init(); 
        
        return; // <--- Terminates the function
    }

    // 💡 We must define originalButtonContent globally or before the loading state begins
    const originalButtonContent = searchButton.innerHTML;

    // --- Loading State START ---
    searchButton.disabled = true; 
    searchInput.disabled = true;
    modelsGrid.innerHTML = '<div class="model-card placeholder"><i class="fas fa-spinner fa-spin"></i> Searching artifacts...</div>';
    searchButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Searching';
    // --- Loading State END ---

    try {
        const fullUrl = `${API_BASE_URL}/artifact/byRegEx`;
        
        const requestBody = { 
            'regex': query
        };

        const response = await fetch(fullUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody), 
        });

        
        // 💡 CHANGE 1: Explicitly check for 404 status before throwing a generic error
        if (!response.ok) {
            if (response.status === 404) {
                 // Display the "No artifacts found" message and then exit the try block cleanly
                 modelsGrid.innerHTML = `<div class="model-card placeholder">No artifacts found matching: <strong>${escapeHtml(query)}</strong>.</div>`;
                 return; // <--- Exit try block to skip rendering logic below
            }
            // For any other error (400, 500, etc.), throw the standard error
            throw new Error(`Search API Request Failed: ${response.status} ${response.statusText}`);
        }

        const artifacts = await response.json();
        
        // --- Rendering Search Results (This section is now only reached if response.ok is true) ---
        modelsGrid.innerHTML = ''; // Clear loading message

        if (artifacts.length === 0) {
            modelsGrid.innerHTML = `<div class="model-card placeholder">No artifacts found matching: <strong>${escapeHtml(query)}</strong>.</div>`;
        } else {
            artifacts.forEach((model) => {
            const placeholderCard = createModelCard(model, { rating: 'N/A', cost: 'N/A', isLicensed: false });
            // mark clickable and attach model reference for later use
            placeholderCard.classList.add('clickable');
            placeholderCard._model = model;

            // click on card -> open/fetch details (but ignore clicks on the Details button itself)
            placeholderCard.addEventListener('click', async (e) => {
                if (e.target.closest('.btn-details')) return; // let the details button handler handle it
                const id = model.id;
                console.log('Card clicked, model ID:', id); // DEBUG
                if (!id) {
                    alert('Model ID not available for this artifact.');
                    return;
                }

                // use cache if available
                if (modelDetailsCache.has(id)) {
                    console.log('Using cached details for', id); // DEBUG
                    openModelModal(model, modelDetailsCache.get(id));
                    return;
                }

                // fetch details once, cache, then open modal
                placeholderCard.classList.add('loading');
                console.log('Fetching details for', id); // DEBUG
                try {
                    const details = await fetchModelDetails(id, model.type);
                    console.log('Fetched details:', details); // DEBUG
                    modelDetailsCache.set(id, details);
                    openModelModal(model, details);
                } catch (err) {
                    console.error(`Failed to load details for ${id}:`, err);
                    alert('Failed to load artifact details. See console for details.');
                } finally {
                    placeholderCard.classList.remove('loading');
                }
            });

            modelsGrid.appendChild(placeholderCard);
        });
        }

    } catch (error) {
        modelsGrid.innerHTML = `<div class="model-card placeholder" style="background-color: var(--danger-color); color: white;">Search Error: Invalid Query Input</div>`;
        console.error("Search failed:", error);
    } finally {
        // --- Revert State ---
        searchButton.disabled = false;
        searchInput.disabled = false;
        searchButton.innerHTML = originalButtonContent;
    }
}



async function fetchModelDetails(id, model_type) {
    try {
        const [ratingResponse, costResponse, licenseResponse] = await Promise.all([
            fetch(`${API_BASE_URL}/artifact/model/${id}/rate`).then(res => res.json()),
            fetch(`${API_BASE_URL}/artifact/${model_type}/${id}/cost`).then(res => res.json()), // Artifact type assumed to be handled by backend
            //fetch(`${API_BASE_URL}/artifact/model/${id}/license-check`).then(res => res.json()),
        ]);

        const cost = Object.values(costResponse)[0]?.total_cost ?? 'N/A';

        return {
            rating: ratingResponse?.net_score ?? 'N/A',
            cost: `${cost} MB`,
        };

    } catch (error) {
        console.error(`Error fetching details for model ${id}:`, error);
        return { rating: 'N/A', cost: 'N/A' };
    }
}

// --- 2. Function to Render a Model Card ---
function createModelCard(model, details = { rating: 'N/A', cost: 0, isLicensed: false }) {
    const card = document.createElement('div');
    card.className = 'model-card';
    card.dataset.modelId = model.id || '';

    const typeKey = (model.type || 'model').toLowerCase();

    const ratingNum = (typeof details.rating === 'number') ? Math.round(details.rating) : null;

    card.innerHTML = `
        <div class="card-header">
            <h3 class="model-name truncated-name" title="${escapeHtml(model.name || '')}">${escapeHtml(model.name || 'Untitled')}</h3>
            <code class="model-id">ID:${escapeHtml(model.id || '')}</code>
            <span class="type-badge type-${escapeHtml(typeKey)}">${escapeHtml(typeKey).toUpperCase()}</span>
        </div>

        <div class="card-actions">
            <button class="btn btn-ghost btn-details" data-id="${escapeHtml(model.id || '')}">Details</button>

            <button class="btn btn-primary btn-artifact" 
                onclick="window.location.href='artifact.html?id=${escapeHtml(model.id)}&type=${escapeHtml(typeKey)}'">
                View Artifact
            </button>
        </div>
    `;

    return card;
}
const modelDetailsCache = new Map();

function openModelModal(model, details) {
    // create overlay
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal-content">
            <header class="modal-header">
                <h2 class="modal-title">${escapeHtml(model.name || 'Untitled')}</h2>
                <button class="close-btn" aria-label="Close">&times;</button>
            </header>
            <section class="modal-body">
                <p><strong>ID:</strong> <code class="modal-id">${escapeHtml(model.id || '')}</code></p>
                <p><strong>Type:</strong> <span class="modal-type type-${escapeHtml((model.type||'model').toLowerCase())}">${escapeHtml(model.type || 'model')}</span></p>
                <p><strong>Rating:</strong> ${escapeHtml((typeof details.rating === 'number') ? details.rating.toString() : String(details.rating))}</p>
                <p><strong>Cost:</strong> ${escapeHtml((typeof details.cost === 'number') ? `$${details.cost.toFixed(2)}` : String(details.cost))}</p>
            </section>
        </div>
    `;

    // close handler
    overlay.querySelector('.close-btn').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });

    document.body.appendChild(overlay);
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
            const placeholderCard = createModelCard(model, { rating: 'N/A', cost: 'N/A', isLicensed: false });
            // mark clickable and attach model reference for later use
            placeholderCard.classList.add('clickable');
            placeholderCard._model = model;

            // click on card -> open/fetch details (but ignore clicks on the Details button itself)
            placeholderCard.addEventListener('click', async (e) => {
                if (e.target.closest('.btn-details')) return; // let the details button handler handle it
                const id = model.id;
                console.log('Card clicked, model ID:', id); // DEBUG
                if (!id) {
                    alert('Model ID not available for this artifact.');
                    return;
                }

                // use cache if available
                if (modelDetailsCache.has(id)) {
                    console.log('Using cached details for', id); // DEBUG
                    openModelModal(model, modelDetailsCache.get(id));
                    return;
                }

                // fetch details once, cache, then open modal
                placeholderCard.classList.add('loading');
                console.log('Fetching details for', id); // DEBUG
                try {
                    const details = await fetchModelDetails(id, model.type);
                    console.log('Fetched details:', details); // DEBUG
                    modelDetailsCache.set(id, details);
                    openModelModal(model, details);
                } catch (err) {
                    console.error(`Failed to load details for ${id}:`, err);
                    alert('Failed to load artifact details. See console for details.');
                } finally {
                    placeholderCard.classList.remove('loading');
                }
            });

            modelsGrid.appendChild(placeholderCard);
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
    searchArtifacts(query);
});


// Initialize the homepage on load
document.addEventListener('DOMContentLoaded', init);


document.getElementById('modelsGrid').addEventListener('click', async (ev) => {
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
        ev.stopPropagation();
        const card = detailsBtn.closest('.model-card');
        if (!card || !card._model) { alert('Model info not available'); return; }

        const model = card._model;
        const id = model.id;

        if (modelDetailsCache.has(id)) {
            openModelModal(model, modelDetailsCache.get(id));
            return;
        }

        // fetch once and open
        card.classList.add('loading');
        try {
            const details = await fetchModelDetails(id, model.type); 
            modelDetailsCache.set(id, details);
            openModelModal(model, details);
        } catch (err) {
            console.error(err);
            alert('Failed to load details.');
        } finally {
            card.classList.remove('loading');
        }
    }
});