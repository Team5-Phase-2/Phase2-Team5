/**
 * app.js - Conceptual Logic for Fan-Out Data Loading
 */

const API_BASE_URL = 'https://moy7eewxxe.execute-api.us-east-2.amazonaws.com/main';

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
            
            headers: {
                'Content-Type': 'application/json', 
                // Include any required auth headers here if necessary
            },
            
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
            artifacts.forEach(async (model) => {
                // ... (Model card creation and detail fan-out logic from Step 3 goes here) ...
                // For demonstration:
                const card = document.createElement('div');
                card.className = 'model-card';
                card.innerHTML = `<h3>${model.name}</h3><p>ID: ${model.id}</p><p>Loading details...</p>`;
                modelsGrid.appendChild(card);
                
                // --- Start the Fan-Out calls ---
                const details = await fetchModelDetails(model.id);
                // Replace the loading card with the fully detailed card
                card.innerHTML = `<h3>${model.name}</h3><p>Rating: ${details.rating}</p>`;
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
