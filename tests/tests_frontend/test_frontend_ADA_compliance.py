"""Frontend accessibility (ADA) compliance tests.
Tests UI components for accessibility standards using Axe Selenium.
"""

import json
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from axe_selenium_python import Axe

@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    yield driver
    driver.quit()

def test_accessibility_homepage(driver):
    driver.get("http://dkc81a64i5ewt.cloudfront.net/home.html")

    axe = Axe(driver)
    axe.inject()

    results = axe.run()

    # Save results to file for debugging

    violations = results["violations"]

    # Print violations nicely if present
    if violations:
        print("\nAccessibility Violations Found:")
        for v in violations:
            print(f"\nViolation: {v['id']} - {v['description']}")
            for node in v["nodes"]:
                print(f"  HTML: {node['html']}")
                print(f"  Target: {node['target']}")

    # Fail the test if any violations were found
    assert len(violations) == 0, f"A11y violations detected: {len(violations)}"


def test_accessibility_contribute(driver):
    driver.get("http://dkc81a64i5ewt.cloudfront.net/contribute.html")

    axe = Axe(driver)
    axe.inject()

    results = axe.run()

    # Save results to file for debugging

    violations = results["violations"]

    # Print violations nicely if present
    if violations:
        print("\nAccessibility Violations Found:")
        for v in violations:
            print(f"\nViolation: {v['id']} - {v['description']}")
            for node in v["nodes"]:
                print(f"  HTML: {node['html']}")
                print(f"  Target: {node['target']}")

    # Fail the test if any violations were found
    assert len(violations) == 0, f"A11y violations detected: {len(violations)}"


def test_accessibility_artifacts(driver):
    driver.get("http://dkc81a64i5ewt.cloudfront.net/artifact.html")

    axe = Axe(driver)
    axe.inject()

    results = axe.run()

    # Save results to file for debugging

    violations = results["violations"]

    # Print violations nicely if present
    if violations:
        print("\nAccessibility Violations Found:")
        for v in violations:
            print(f"\nViolation: {v['id']} - {v['description']}")
            for node in v["nodes"]:
                print(f"  HTML: {node['html']}")
                print(f"  Target: {node['target']}")

    # Fail the test if any violations were found
    assert len(violations) == 0, f"A11y violations detected: {len(violations)}"


def test_accessibility_docs(driver):
    driver.get("http://dkc81a64i5ewt.cloudfront.net/docs.html")

    axe = Axe(driver)
    axe.inject()

    results = axe.run()

    # Save results to file for debugging

    violations = results["violations"]

    # Print violations nicely if present
    if violations:
        print("\nAccessibility Violations Found:")
        for v in violations:
            print(f"\nViolation: {v['id']} - {v['description']}")
            for node in v["nodes"]:
                print(f"  HTML: {node['html']}")
                print(f"  Target: {node['target']}")

    # Fail the test if any violations were found
    assert len(violations) == 0, f"A11y violations detected: {len(violations)}"