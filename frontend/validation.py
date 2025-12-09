from selenium import webdriver
from axe_selenium_python import Axe

driver = webdriver.Chrome()
driver.get("http://127.0.0.1:3000/home.html")

axe = Axe(driver)
axe.inject()

results = axe.run()

# Save results
axe.write_results(results, "axe-results.json")

# Fail test if violations exist
violations = results["violations"]
for v in violations:
    print("\nViolation:", v["id"], "-", v["description"])
    for node in v["nodes"]:
        print("  HTML:", node["html"])
        print("  Target:", node["target"])