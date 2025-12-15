"""Frontend tests for the artifact page.
Tests artifact display, interaction, and UI functionality.
"""

import pytest
import time
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


TARGET_URL = "https://dkc81a64i5ewt.cloudfront.net/home.html"


def test_artifact_navigation_and_initial_load(driver):
    """
    Test 1: Navigate from Home to a specific Artifact page and check basic elements.
    We assume the first model-card on the home page is a 'model' type.
    """
    driver.get(TARGET_URL)
    wait = WebDriverWait(driver, 20)

    # 1. Locate the first model card's details button
    # Assuming 'btn-details' is the element that links to the artifact page.
    # Note: In a real test, you'd mock the API response here to control the link URL.
    details_btn = wait.until(
        EC.element_to_be_clickable((By.CLASS_NAME, "btn-details"))
    )
    
    # 2. Extract the href/link target (or use a known, mocked link)
    # Since we can't reliably get the ID from the card here, we'll hardcode navigation
    # to a specific URL that the JS expects for a 'model' type artifact.
    # Replace the ID/TYPE with known values your mock API will serve!

    MOCKED_MODEL_URL = f"https://dkc81a64i5ewt.cloudfront.net/artifact.html?id=3623129610&type=model"
    
    # Navigate directly to the mocked artifact URL
    driver.get(MOCKED_MODEL_URL)
    
    # 3. Wait for the core component to load (Artifact Name)
    artifact_name_header = wait.until(
        EC.visibility_of_element_located((By.ID, "artifactName"))
    )

    # 4. Assert: Check the artifact ID displayed in the header
    artifact_id_span = driver.find_element(By.ID, "artifactId")
    assert "3623129610" in artifact_id_span.text, "Artifact ID was not displayed correctly."
    
    # 5. Assert: Check the download button is present
    download_btn = driver.find_element(By.ID, "downloadBtn")
    assert download_btn.is_displayed(), "Download button is missing."

    delete_btn = driver.find_element(By.ID, "deleteBtn")
    assert delete_btn.is_displayed(), "Delete button is missing."
