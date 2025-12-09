import pytest
from selenium import webdriver
# Import desired browser options if needed, e.g., ChromeOptions

# Define the list of browsers you want to test
@pytest.fixture(scope="function", params=["chrome", "edge"])
def driver(request):
    browser_name = request.param
    
    if browser_name == "chrome":
        # Setup for Chrome Driver
        # Consider adding options/service here
        driver = webdriver.Chrome()
    elif browser_name == "edge":
        # Setup for Edge Driver
        # Consider adding options/service here
        driver = webdriver.Edge()
    else:
        raise ValueError(f"Unsupported browser: {browser_name}")

    driver.maximize_window()
    
    # This yields the driver to the test function
    yield driver
    
    # Teardown: runs after the test finishes
    driver.quit()