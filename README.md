# SecureModelHub

SecureModelHub is an open registry for machine learning models, developed in association with ACME Co. It ingests models primarily from Hugging Face, analyzes them for security and trustworthiness using automated metrics, stores approved artifacts in Amazon S3, and redistributes them through a controlled API. The system emphasizes model security, code quality, and safe distribution of ML models, source code, and datasets.

## Architecture Overview

SecureModelHub uses a serverless architecture built on AWS Lambda, with the following components and data flow:

- **Frontend**: A static web UI deployed via AWS CloudFront with Web Application Firewall (WAF) for security. Provides user interaction for browsing and accessing the registry.
- **API Gateway**: Routes requests to Lambda functions for artifact management.
- **Lambda Functions**: Handle core operations such as model ingestion, rating, storage, and retrieval. Key functions include:
  - `Rate`: Computes trustworthiness metrics (e.g., license compliance, code quality, bus factor).
  - `Upload`: Stores approved artifacts in S3.
  - `Artifacts`: Lists available artifacts.
  - `Get_Rate`: Retrieves ratings for specific models.
  - Health checks and utility functions (e.g., regex validation).
- **S3 Storage**: Central repository for model artifacts and metadata.
- **External Integrations**: Fetches model data from Hugging Face API for analysis.

Data flow: User submits model URL → Rate Lambda analyzes → If approved, Upload Lambda stores in S3 → Artifacts Lambda lists for redistribution.

```
[User] → CloudFront (UI) → API Gateway → Lambda (Rate/Upload/etc.) → S3
                                            ↓
                                    Hugging Face API (for analysis)
```

## Key Features

- **Automated Model Rating**: Evaluates models on metrics like license permissiveness, code quality, dataset availability, performance claims, size, bus factor, reviewedness, and reproducibility.
- **Secure Storage and Distribution**: Stores artifacts in S3 with controlled access; no authentication required for public use.
- **Hugging Face Integration**: Primarily supports models from Hugging Face, with API-based metadata fetching.
- **Serverless Scalability**: AWS Lambda handles variable loads without infrastructure management.
- **Health Monitoring**: Includes health-check endpoints for service availability.
- **Regex Safety Validation**: Prevents potentially unsafe regex patterns in model metadata.

## Security Model and Trust Assumptions

- **No Authentication**: The registry is open; anyone on the internet can access the site and services without credentials.
- **Trust Assumptions**: Relies on automated metrics for trustworthiness; assumes Hugging Face as a trusted source. No manual review or user verification.
- **Security Measures**: CloudFront WAF provides basic protection; Lambda functions operate with minimal permissions. Sensitive data (e.g., API keys) should be managed via environment variables.
- **Limitations**: Public access means no access control; potential for abuse or untrusted submissions.

## Supported Model Sources

- Primarily Hugging Face (models and datasets).
- Supports model URLs from Hugging Face for ingestion and rating.

## Installation / Deployment

### Local Development

1. Clone the repository.
2. Install Python 3.14 and dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run tests:
   ```
   pytest
   ```

### AWS Deployment

- Deploy Lambda functions via CD.
- Configure S3 bucket for artifact storage.
- Deploy frontend to CloudFront with WAF enabled.
- CI/CD: Automated via GitHub Actions (see `.github/workflows/` for AWS Lambda deployment, S3 uploads, and testing).

## Configuration

- **Environment Variables**:
  - `REGISTRY_BUCKET`: S3 bucket name for storing artifacts and metadata.
  - `GITHUB_TOKEN`: (Optional) For GitHub API access in metrics like reviewedness.
- **IAM Permissions**: Lambda functions require S3 read/write access and API Gateway invocation.
- **Assumptions**: AWS account with Lambda, S3, CloudFront, and API Gateway enabled.

## API or Invocation Examples

SecureModelHub exposes RESTful endpoints via API Gateway (base URL: `https://dkc81a64i5ewt.cloudfront.net`). No authentication is required; the `X-Authorization` header is not enforced. Below are the implemented endpoints, matched to backend sub-directories:

### /health (Health/)
- **GET**: Heartbeat check
  - Description: Lightweight liveness probe. Returns HTTP 200 when the registry API is reachable.
  - Response: 200 - Service reachable.

### /reset (Reset/)
- **DELETE**: Reset the registry
  - Description: Reset the registry to a system default state.
  - Response: 200 - Registry is reset.

### /artifacts (Artifacts/)
- **POST**: Get the artifacts from the registry
  - Description: Get any artifacts fitting the query. Provide an array with artifact queries.
  - Body: JSON array of artifact queries (e.g., `[{"name": "*"}]`)
  - Parameters: `offset` (query, optional) for pagination.
  - Response: 200 - List of artifacts; 400 - Invalid query; 413 - Too many results.

### /artifact/{artifact_type} (Register_Artifact_Setup/, Rate/, Upload/)
- **POST**: Register a new artifact
  - Description: Register a new artifact by providing a downloadable source URL.
  - Path: `artifact_type` (model, dataset, code)
  - Body: `{"url": "https://huggingface.co/model/id", "name": "ModelName"}`
  - Response: 201 - Created; 202 - Accepted; 400 - Invalid data; 409 - Exists; 424 - Disqualified rating.

### /artifact/{artifact_type}/{id} (Get_Artifact_Id/, Delete/)
- **GET**: Interact with the artifact
  - Description: Return this artifact.
  - Path: `artifact_type`, `id`
  - Response: 200 - Artifact data; 400 - Invalid; 404 - Not found.
- **DELETE**: Delete this artifact
  - Description: Delete the artifact by ID.
  - Response: 200 - Deleted; 400 - Invalid; 404 - Not found.

### /artifact/model/{id}/rate (Get_Rate/)
- **GET**: Get ratings for this model artifact
  - Description: Retrieve computed trustworthiness metrics.
  - Path: `id`
  - Response: 200 - JSON with metrics; 400 - Invalid; 404 - Not found; 500 - Rating error.

### /artifact/{artifact_type}/{id}/cost (Get_Cost/)
- **GET**: Get the cost of an artifact
  - Description: Return the total cost (size in MB).
  - Path: `artifact_type`, `id`
  - Query: `dependency` (boolean, default false)
  - Response: 200 - Cost data; 400 - Invalid; 404 - Not found; 500 - Error.

### /artifact/byRegEx (Regex/)
- **POST**: Get any artifacts fitting the regular expression
  - Description: Search for artifacts using regex over names and READMEs.
  - Body: `{"regex": "pattern"}`
  - Response: 200 - List of artifacts; 400 - Invalid; 404 - None found.

### /tracks (Track/)
- **GET**: Get the list of tracks a student has planned to implement
  - Description: Return the list of tracks.
  - Response: 200 - List; 500 - Error.

Invoke Lambda functions directly or via API Gateway events.

## Limitations and Non-Goals

- No user authentication or access control.
- Metrics are heuristic-based; not a substitute for expert review.
- Frontend is static; no dynamic features like user accounts.

## Future Work

- Enhance metrics with additional security checks (implied by extensibility in `metrics/`).
- Add support for more model sources.
- Implement caching or database integration for performance.
