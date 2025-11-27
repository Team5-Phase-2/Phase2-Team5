/**
 * app.js - Conceptual Logic for Fan-Out Data Loading
 */

const API_BASE_URL = 'http://your-backend-api.com/artifact'; // REPLACE WITH YOUR ACTUAL BACKEND URL

// --- 1. Helper Function to Fetch All Details ---
async function fetchModelDetails(id) {
    try {
        const [ratingResponse, costResponse, licenseResponse] = await Promise.all([
            fetch(`${API_BASE_URL}/model/${id}/rate`).then(res => res.json()),
            fetch(`${API_BASE_URL}/${id}/cost`).then(res => res.json()), // Artifact type assumed to be handled by backend
            fetch(`${API_BASE_URL}/model/${id}/license-check`).then(res => res.json()),
        ]);

        return {
            rating: ratingResponse, // e.g., 4.5
            cost: costResponse,     // e.g., 0 or 1.99
            isLicensed: licenseResponse // e.g., true/false
        };
    } catch (error) {
        console.error(`Error fetching details for model ${id}:`, error);
        return { rating: 'N/A', cost: 'N/A', isLicensed: false }; // Return safe defaults
    }
}

// --- 2. Function to Render a Model Card ---
function createModelCard(model, details) {
    const card = document.createElement('div');
    card.className = 'model-card';

    // Determine visual status based on fetched details
    const isVetted = details.isLicensed === true;
    const vettedBadge = isVetted 
        ? `<span class="badge badge-vetted"><i class="fas fa-shield-alt"></i> VETTED</span>`
        : `<span class="badge badge-risk"><i class="fas fa-exclamation-triangle"></i> RISK</span>`;

    const costDisplay = details.cost > 0 ? `$${details.cost.toFixed(2)}` : 'FREE';
    const ratingStars = '⭐'.repeat(Math.round(details.rating)) || 'N/A';
    
    // HTML structure for the card
    card.innerHTML = `
        <div class="card-header">
            <h3 class="model-name">${model.name}</h3>
            <span class="model-type-tag">${model.type || 'Model'}</span>
        </div>
        <p class="model-desc">${model.description || 'A concise description of the model.'}</p>
        <div class="card-details">
            <div>
                ${ratingStars}
            </div>
            <div>
                <span class="cost-display">${costDisplay}</span>
                ${vettedBadge}
            </div>
        </div>
    `;

    return card;
}

// --- 3. Main Initialization Function ---
async function init() {
    const modelsGrid = document.getElementById('modelsGrid');
    
    // Start with a clean slate
    modelsGrid.innerHTML = '<div class="model-card placeholder">Fetching core artifact list...</div>';

    try {
        // Step 1: Fetch the initial list of all artifacts
        const response = await fetch(`${API_BASE_URL}s`); // Assumed /artifacts endpoint
        const artifacts = await response.json();
        
        // Clear the loading placeholder
        modelsGrid.innerHTML = ''; 

        // Step 2: Render initial cards and trigger the fan-out
        artifacts.forEach(async (model) => {
            // Create a basic card placeholder immediately
            const loadingCard = document.createElement('div');
            loadingCard.className = 'model-card';
            loadingCard.innerHTML = `
                <div class="card-header"><h3 class="model-name">${model.name}</h3></div>
                <div class="card-details">Loading details...</div>
            `;
            modelsGrid.appendChild(loadingCard);

            // Fetch the details asynchronously (Fan-Out)
            const details = await fetchModelDetails(model.id);

            // Once details are back, replace the loading card with the final card
            const finalCard = createModelCard(model, details);
            modelsGrid.replaceChild(finalCard, loadingCard);
        });

    } catch (error) {
        modelsGrid.innerHTML = '<div class="model-card placeholder" style="background-color: var(--danger-color); color: white;">Error loading models. Check API connection.</div>';
        console.error("Failed to load artifacts:", error);
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