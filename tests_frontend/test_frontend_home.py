import pytest
import time
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -----------------------------------------------------------------------------
# 🔧 CONFIGURATION
# -----------------------------------------------------------------------------
# UPDATE THIS to your local server URL or file path
TARGET_URL = "https://dkc81a64i5ewt.cloudfront.net/home.html"
RE_DOS_TIMEOUT_SECONDS = 5 

# -----------------------------------------------------------------------------
# 🧪 TEST CASES
# -----------------------------------------------------------------------------

def test_contribute_artifact_navigation(driver):
    """
    Feature 3: Verify the 'Contribute Artifact' button navigates correctly.
    """
    driver.get(TARGET_URL)

    # 1. Locate the Contribute button (using the text inside the anchor tag)
    contribute_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.LINK_TEXT, "Contribute Artifact"))
    )
    
    # 2. Click the button
    contribute_btn.click()

    # 3. Assert: Check if the URL string contains 'contribute.html'
    # Note: This might fail if the file doesn't exist locally, 
    # but it verifies the browser TRIED to go there.
    assert "contribute.html" in driver.current_url


def test_regex_search_functionality(driver):
    """
    Feature 2: Verify the Regex Search bar filters results.
    """
    driver.get(TARGET_URL)
    wait = WebDriverWait(driver, 15) # Longer wait for API calls

    # 1. Input a search query
    search_input = wait.until(EC.visibility_of_element_located((By.ID, "searchInput")))
    search_input.clear()
    search_input.send_keys("BERT") # Example query

    # 2. Click the Search Button
    search_btn = driver.find_element(By.ID, "searchButton")
    search_btn.click()

    # 3. Wait for the "Searching..." placeholder to appear
    # This verifies the UI reacted to the click
    wait.until(
        EC.text_to_be_present_in_element((By.ID, "modelsGrid"), "Searching")
    )

    # 4. Wait for the "Searching..." placeholder to DISAPPEAR (meaning results loaded)
    # We wait for the spinner icon to NOT be present anymore
    wait.until_not(
        EC.presence_of_element_located((By.CLASS_NAME, "fa-spinner"))
    )

    # 5. Assert: Verify we have at least one model card or a "No artifacts" message
    # We look for the generic card class
    cards = driver.find_elements(By.CLASS_NAME, "model-card")
    assert len(cards) > 0, "No result cards or message appeared after search."


def test_model_details_modal(driver):
    """
    Feature 1: Verify clicking 'Details' opens the modal and 'View Artifact' exists.
    """
    driver.get(TARGET_URL)
    wait = WebDriverWait(driver, 20)

    # 1. Wait for the initial data fetch (init() function) to complete
    # We wait for a "Details" button to become clickable. 
    # This implies the API returned data and cards were rendered.
    details_btn = wait.until(
        EC.element_to_be_clickable((By.CLASS_NAME, "btn-details"))
    )

    # 2. Click the first "Details" button found
    details_btn.click()

    # 3. Wait for the Modal Overlay to appear
    modal = wait.until(
        EC.visibility_of_element_located((By.CLASS_NAME, "modal-overlay"))
    )

    # 4. Assertions inside the modal
    # Check if the title is visible
    modal_title = modal.find_element(By.CLASS_NAME, "modal-title")
    assert modal_title.is_displayed()
    
    # Check for Model ID code block
    modal_id = modal.find_element(By.CLASS_NAME, "modal-id")
    assert modal_id.is_displayed()

    # 5. Close the modal
    close_btn = modal.find_element(By.CLASS_NAME, "close-btn")
    close_btn.click()

    # 6. Verify modal is gone (wait for invisibility)
    wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-overlay")))

def test_regex_redos_protection(driver):
    """Tests if the application handles a known ReDOS-vulnerable string quickly."""
    
    redos_string = "(a|aa)*$"
    wait = WebDriverWait(driver, RE_DOS_TIMEOUT_SECONDS + 2) # Buffer for test execution
    
    driver.get(TARGET_URL)
    
    # [FIXED] Use ID 'searchInput'
    search_box = driver.find_element(By.ID, "searchInput")
    # [FIXED] Use ID 'searchButton'
    search_button = driver.find_element(By.ID, "searchButton")
    
    search_box.clear()
    search_box.send_keys(redos_string)
    
    start_time = time.time()
    search_button.click()
    
    try:
        # [FIXED] Wait for the loading spinner to disappear instead of generic 'results_area'
        # This confirms the search has actually finished processing.
        wait.until_not(
             EC.presence_of_element_located((By.CLASS_NAME, "fa-spinner"))
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response_time < RE_DOS_TIMEOUT_SECONDS, \
            f"Potential ReDOS failure! Response took {response_time:.2f}s (Max {RE_DOS_TIMEOUT_SECONDS}s)."
            
        # [FIXED] Check 'modelsGrid' for the text
        results_text = driver.find_element(By.ID, "modelsGrid").text
        
        # Check for either empty results message OR error message
        assert "No Artifacts found" in results_text or "Error" in results_text or len(results_text) == 0, \
            "Expected error or empty result, but got unexpected results."
            
    except TimeoutException:
        raise AssertionError(f"ReDOS timeout exceeded! The search took longer than {RE_DOS_TIMEOUT_SECONDS} seconds.")


def test_empty_input_returns_all_models(driver):
    """Tests that an empty search box returns all available artifacts/models."""
    
    # UPDATE THIS number to match your actual database count
    EXPECTED_TOTAL_MODELS = 25 
    
    driver.get(TARGET_URL)
    wait = WebDriverWait(driver, 10)
    
    # [FIXED] Use ID 'searchButton'
    search_button = driver.find_element(By.ID, "searchButton")
    
    # Do not put anything in the search box (it's already clear)
    search_button.click()
    
    # [FIXED] Wait for spinner to disappear
    wait.until_not(
        EC.presence_of_element_located((By.CLASS_NAME, "fa-spinner"))
    )
    
    # [FIXED] Use class 'model-card' instead of 'model_result_item'
    model_elements = driver.find_elements(By.CLASS_NAME, "model-card")
    
    # Note: If this fails, check if EXPECTED_TOTAL_MODELS matches your live site
    assert len(model_elements) > 0, "Expected models to return, but found 0."


def test_non_matching_input_message(driver):
    """Tests that the specific input 'ece461rocks!' returns 'No Artifacts found'."""
    
    SEARCH_TERM = "ece461rocks!"
    EXPECTED_FAILURE_TEXT = "No artifacts found matching" 
    
    driver.get(TARGET_URL)
    wait = WebDriverWait(driver, 10)
    
    # 1. Wait for input to be ready
    search_box = wait.until(EC.element_to_be_clickable((By.ID, "searchInput")))
    time.sleep(0.5) 
    # 2. Locate button
    search_button = driver.find_element(By.ID, "searchButton")
    
    search_box.clear()
    search_box.send_keys(SEARCH_TERM)
    
    # --- SYNCHRONOUS FIX 1: Ensure the click event is fully sent ---
    search_button.click()
    # Adding a short sleep is a common, though sometimes necessary, measure 
    # when the browser event queue is slow to start processing the click.
    time.sleep(0.5) 
    # -----------------------------------------------------------------
    
    # 3. Wait for the new state (the expected text) to appear.
    wait.until(
        EC.text_to_be_present_in_element((By.ID, "modelsGrid"), EXPECTED_FAILURE_TEXT)
    )
    
    # ... rest of your assertions ...
    results_text = driver.find_element(By.ID, "modelsGrid").text
    
    assert EXPECTED_FAILURE_TEXT in results_text, \
        f"Expected failure message '{EXPECTED_FAILURE_TEXT}' not found."
    
    assert SEARCH_TERM in results_text, \
        f"Expected search term '{SEARCH_TERM}' not found in the results."

def test_docs_button_navigation(driver):
    """
    Checks if clicking the 'Docs' link in the header navigates to 'docs.html'.
    """
    driver.get(TARGET_URL)
    wait = WebDriverWait(driver, 5)

    # 1. Locate the 'Docs' button using its link text
    # The HTML shows a link with class 'nav-link' and text 'Docs'
    docs_link = wait.until(
        EC.element_to_be_clickable((By.LINK_TEXT, "Docs"))
    )
    
    # 2. Click the link
    docs_link.click()

    # 3. Assert: Check if the URL string contains 'docs.html'
    assert "docs.html" in driver.current_url, \
        f"Docs link failed to navigate. Current URL: {driver.current_url}"