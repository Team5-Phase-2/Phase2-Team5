const API_BASE_URL = "https://moy7eewxxe.execute-api.us-east-2.amazonaws.com/main";

const urlParams = new URLSearchParams(window.location.search);
const artifactId = urlParams.get("id");
const artifactType = urlParams.get("type"); // model, dataset, code

document.getElementById("artifactId").textContent = artifactId;

async function loadArtifact() {
    try {
        // --- Fetch metadata ---
        const meta = await fetch(`${API_BASE_URL}/artifacts/${artifactType}/${artifactId}`)
            .then(res => res.json());

        const artifactName = meta.metadata?.name || "Unknown Artifact";
        const downloadURL = meta.data?.download_url;
        const repoUrl = meta.data?.url;

        document.getElementById("artifactName").textContent = artifactName;

        // --- Only fetch ratings for MODELS ---
        if (artifactType === "model") {
            const rating = await fetch(`${API_BASE_URL}/artifact/${artifactType}/${artifactId}/rate`)
                .then(res => res.json());

            // Display main score
            document.getElementById("netScore").textContent = rating.net_score.toFixed(3);

            // Show subscores
            const subscoresBox = document.getElementById("subscores");
            subscoresBox.innerHTML = "";

            Object.entries(rating).forEach(([key, value]) => {
                const isNumber = typeof value === "number";
                const isNet = key === "net_score";
                const isLatency = key.endsWith("_latency");

                if (isNumber && !isNet && !isLatency) {
                    const row = document.createElement("p");
                    row.textContent = `${key}: ${value}`;
                    subscoresBox.appendChild(row);
                }
            });

        } else {
            // For datasets & code artifacts → ratings do not exist
            document.getElementById("netScore").textContent = "N/A";
            document.getElementById("subscores").innerHTML =
                `<p>No rating available for <strong>${artifactType}</strong> type.</p>`;
        }

        // --- Download button ---
        document.getElementById("downloadBtn").onclick = () => {
            window.location.href = downloadURL;
        };

        // --- README section ---
        await loadReadme(repoUrl);

    } catch (err) {
        console.error("Failed to load artifact:", err);
    }
}

async function loadReadme(repoUrl) {
    if (!repoUrl) {
        document.getElementById("readmeContent").textContent = "No README available.";
        return;
    }

    const readmeUrl = `${repoUrl}/raw/main/README.md`;

    try {
        const markdown = await fetch(readmeUrl).then(res => res.text());
        document.getElementById("readmeContent").textContent = markdown;
    } catch {
        document.getElementById("readmeContent").textContent = "No README available.";
    }
}

// --- Delete Artifact ---
document.getElementById("deleteBtn").onclick = async () => {
    if (!confirm("Are you ABSOLUTELY sure? This cannot be undone.")) return;

    const res = await fetch(`${API_BASE_URL}/artifacts/${artifactType}/${artifactId}`, {
        method: "DELETE"
    });

    if (res.status === 200) {
        alert("Artifact deleted permanently.");
        window.location.href = "/home.html";
    } else {
        alert("Delete failed.");
    }
};

loadArtifact();
