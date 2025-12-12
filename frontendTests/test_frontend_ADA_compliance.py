import json
import pytest
from selenium import webdriver
from axe_selenium_python import Axe

@pytest.fixture
def driver():
    driver = webdriver.Chrome()
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