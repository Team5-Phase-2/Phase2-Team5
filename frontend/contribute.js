/**
 * contribute.js - Handles the submission logic for new artifacts.
 */

// Use the same API base URL
const API_BASE_URL = 'https://moy7eewxxe.execute-api.us-east-2.amazonaws.com/main';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('artifactForm');
    // Removed nameInput
    const typeSelect = document.getElementById('artifactType');
    const urlInput = document.getElementById('artifactUrl');
    // Removed descriptionInput
    const submitButton = document.getElementById('submitButton');
    const messageContainer = document.getElementById('messageContainer');

    function showMessage(text, isError = false) {
        messageContainer.textContent = text;
        messageContainer.className = isError 
            ? 'message-container error' 
            : 'message-container success';
    }
    
    // Simple Exponential Backoff Retry mechanism
    async function fetchWithRetry(url, options, maxRetries = 3) {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const response = await fetch(url, options);
            
            // If response is NOT ok, we need to read the body for logging, 
            // but we must clone the response first if we want the outer function 
            // to also read it (though in successful cases, we avoid reading here).
            
            if (response.ok) {
                return response;
            }
            
            // Check for HTTP errors defined in the spec that are NOT retriable
            if (response.status === 400 || response.status === 403 || response.status === 409 || response.status === 424) {
                // Read the body for error message but CLONE first if necessary 
                // to prevent double reading, although in this context, 
                // throwing an error stops execution anyway.
                // Let's stick to reading the text to extract the error body cleanly:
                const errorBody = await response.text(); 
                throw new Error(`API Error (${response.status}): ${errorBody || response.statusText}`);
            }
            
            // For other errors (like server 5xx or timeouts), we retry
            throw new Error(`HTTP Error: ${response.status} ${response.statusText}`);
            
        } catch (error) {
            if (attempt === maxRetries - 1) {
                throw error; // Re-throw if last attempt failed
            }
            const delay = Math.pow(2, attempt) * 1000;
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // 1. Prepare data
        const artifactType = typeSelect.value;
        const ArtifactUrl = urlInput.value.trim()

        // 2. Lock UI during submission
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        messageContainer.className = 'message-container hidden'; // Clear previous messages

        try {
            // 3. Construct the API call payload and endpoint
            const url = `${API_BASE_URL}/artifact/${artifactType}`;
            
            const requestBody = {
                url: ArtifactUrl
            };

            const options = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                // The body is an array containing the single new artifact object
                body: JSON.stringify(requestBody) 
            };
            
            // 4. Execute API call with retry mechanism
            const response = await fetchWithRetry(url, options);
            
            // Assuming the backend returns the successfully created artifact object

            if (response.status === 201) {
                const result = await response.json(); 
                const artifactName = result.metadata?.name || nameInput.value.trim();
                const artifactId = result.metadata?.id || 'N/A';
                showMessage(`Artifact "${artifactName}" registered successfully! ID: ${artifactId}`, false);
            } else {
                // Handle unexpected successful statuses that don't match 201/202
                throw new Error(`Unexpected successful response status: ${response.status}`);
            }

        } catch (error) {
            // 6. Error
            console.error('Artifact submission failed:', error);
            showMessage(`Submission Failed: ${error.message}. Please try again.`, true);
        } finally {
            // 7. Unlock UI
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fas fa-upload"></i> Submit Artifact';
        }
    });
});