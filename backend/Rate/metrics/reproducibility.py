
import time
import re
import json
from typing import Optional, Tuple

from .utils import query_genai

def reproducibility(model_url: str) -> Tuple[Optional[float], int]:
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

  # query: str = f'Run example code from a readme you can get from the URL: {model_url}. Do not simulate errors that do not happen.' \
  # '1) Run the example code give in the readme and return a status code 1 if it works strait out of the box.' \
  # '2) If it doesn’t work see if you can fix it. After 2 attempts to fix it, if it works return a status code 0.5 otherwise return status code 0.' \
  # 'Respond with the formate: "Final Respose -- Status Code : <>"'

  # query: str = f'Please execute the example code from the README at {model_url} without simulating errors or assumptions. Assume all necessary prerequisites are met, and the code will be executed in a standard environment with no errors or exceptions.' \
  # 'Provide a status code of 1 if the code works straight out of the box, 0.5 if it works after 2 attempts to fix it, and 0 otherwise.' \
  # 'Respond with the formate: "Final Response -- Status Code : <>"'

  query: str = f'Please execute the example code from the README at {model_url} without simulating errors or assumptions.' \
  'Executed in a standard environment with no pip libraries already installed. Only preinstall libraries that come from explicite imports.' \
  'List any assumptions made.' \
  'Provide a status code of 1 if the code works straight out of the box, 0.5 if it works after 2 attempts to fix it, and 0 otherwise.' \
  'Respond with the formate: "Final Response -- Status Code : <>"'

  resp: dict = query_genai(query)
  # if resp == "Error":
  #   return 0.0, (time.time_ns() - start_ns) // 1_000_000
  # Load the JSON response
  response_json = json.loads(resp['body'])

  # Extract the content from the message
  content = response_json['choices'][0]['message']['content']
  # print(content)

  # print(resp)
  score: float = extract_status_code(content)

  latency: int = (time.time_ns() - start_ns) // 1_000_000
  return score, latency

def extract_status_code(response: str) -> float:
    pattern = r"Final Response -- Status Code : (\d+(?:\.\d+)?)"
    match = re.search(pattern, response)
    if match:
        return float(match.group(1))
    else:
        return 0.0


if __name__ == "__main__":
  urls = {
    "https://huggingface.co/google-bert/bert-base-uncased",
    "https://huggingface.co/datasets/bookcorpus/bookcorpus",
    "https://github.com/google-research/bert",
    "https://huggingface.co/parvk11/audience_classifier_model",
    "https://huggingface.co/distilbert-base-uncased-distilled-squad",
    "https://huggingface.co/caidas/swin2SR-lightweight-x2-64",
    "https://huggingface.co/vikhyatk/moondream2",
    "https://huggingface.co/microsoft/git-base",
    "https://huggingface.co/WinKawaks/vit-tiny-patch16-224",
    "https://huggingface.co/patrickjohncyh/fashion-clip",

    "https://huggingface.co/lerobot/diffusion_pusht",
    "https://huggingface.co/parthvpatil18/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab",
    "https://huggingface.co/microsoft/resnet-50",
    "https://huggingface.co/crangana/trained-gender",
    "https://huggingface.co/onnx-community/trained-gender-ONNX",
    "https://huggingface.co/datasets/rajpurkar/squad",
    "https://www.kaggle.com/datasets/hliang001/flickr2k",
    "https://github.com/zalandoresearch/fashion-mnist",
  }

  for url in urls:
    score, latency = reproducibility(url)
    print(score, latency)
