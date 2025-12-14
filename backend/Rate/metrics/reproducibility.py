"""backend.Rate.metrics.reproducibility

Metric to evaluate the reproducibility of example code in a model's README.

Uses generative AI to simulate execution of example code snippets from the
README, determining if they run successfully out-of-the-box or after fixes.
Returns a score of 1.0, 0.5, or 0.0 based on reproducibility.
"""


import time
import re
import json
from typing import Optional, Tuple
from .utils import query_genai, fetch_hf_readme_text

def reproducibility(model_url: str, code_url: str, dataset_url: str) -> Tuple[Optional[float], int]:
    """
    Evaluates the reproducibility of example code from a model's README.
    
    This function queries a generative AI to execute the example code from the README at the given model URL,
    simulating a standard environment with only explicitly imported libraries preinstalled. It returns a status code
    indicating whether the code works out of the box, after up to two fixes, or not at all, along with the latency
    of the evaluation in milliseconds.
    
    Parameters:
        model_url (str): The URL of the model or dataset whose README example code should be evaluated.
    
    Returns:
        Tuple[Optional[float], int]: A tuple containing the reproducibility score (1.0, 0.5, or 0.0) and the latency in milliseconds.
    """
    start_ns = time.time_ns()

    readme_content =  fetch_hf_readme_text(model_url).encode('utf-8')

    # query: str = f'Run example code from a readme you can get from the URL: {model_url}. Do not simulate errors that do not happen.' \
    # '1) Run the example code give in the readme and return a status code 1 if it works strait out of the box.' \
    # '2) If it doesn’t work see if you can fix it. After 2 attempts to fix it, if it works return a status code 0.5 otherwise return status code 0.' \
    # 'Respond with the formate: "Final Respose -- Status Code : <>"'

    # query: str = f'Please execute the example code from the README at {model_url} without simulating errors or assumptions. Assume all necessary prerequisites are met, and the code will be executed in a standard environment with no errors or exceptions.' \
    # 'Provide a status code of 1 if the code works straight out of the box, 0.5 if it works after 2 attempts to fix it, and 0 otherwise.' \
    # 'Respond with the formate: "Final Response -- Status Code : <>"'

    query: str = f"""
        [SYSTEM ROLE]
        You are an execution analyst responsible for evaluating whether example code from a 
        HuggingFace model README can run successfully in a clean environment. You must attempt to 
        execute the code exactly as written, without inventing missing steps or simulating 
        hypothetical errors. You may only use libraries explicitly imported in the code.

        [USER ROLE]
        The user provides the URL of a HuggingFace model and the README contents. Your job is to 
        evaluate the example code exactly as the user provides it.

        [INPUT]
        Model URL:
        {model_url}

        README CONTENTS:
        {readme_content.decode("utf-8")}

        [TASK]
        1. Locate the example code in the README.
        2. Attempt to execute the example code exactly as written.
        3. Environment constraints:
        - Assume a clean, standard Python environment.
        - No pip-installed libraries are available unless the code explicitly imports them.
        - You may only install or import libraries that the README example explicitly lists.

        4. If the README contains no example code or is empty:
        - Attempt to fetch the README directly from the provided model URL.

        5. List any assumptions you had to make to perform execution.

        [STATUS CODE RULES]
        Provide a status code based on execution viability:
        - 1     → The code runs successfully out of the box with no fixes.
        - 0.5   → The code runs after up to two minimal fixes.
        - 0     → The code does not run even after two fix attempts.

        [CONSTRAINTS]
        - Do not simulate imaginary errors.
        - Do not assume missing import statements.
        - Do not add steps unless strictly necessary for execution.
        - Do not modify the example code unless it is part of one of the two allowed fixes.
        - Do not include commentary unrelated to execution results.

        [OUTPUT FORMAT]
        Respond **only** in the following format:

        Final Response -- Status Code: <value>
        """

    resp: dict = query_genai(query)
    if resp == "Error":
        return 0.0, (time.time_ns() - start_ns) // 1_000_000
    # Load the JSON response
    response_json = json.loads(resp['body'])

    # Extract the content from the message
    content = response_json['choices'][0]['message']['content']

    score: float = extract_status_code(content)

    latency: int = (time.time_ns() - start_ns) // 1_000_000
    return score, latency

def extract_status_code(response: str) -> float:
    """
    Extract a numeric HTTP status code from a response string using a regex.
    Returns 0.0 if no status code is found.
    """
    pattern = r"Final Response -- Status Code : (\d+(?:\.\d+)?)"
    match = re.search(pattern, response)
    if match:
        return float(match.group(1))
    return 0.0
