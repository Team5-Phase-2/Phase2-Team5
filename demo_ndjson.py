from src.url.router import ModelItem
from src.url.ndjson_writer import NdjsonWriter
import sys

# make a fake ModelItem (normally comes from the router)
item = ModelItem(
    model_url="https://huggingface.co/google/gemma-3-270m",
    datasets=["https://huggingface.co/datasets/xlangai/AgentNet"],
    code=["https://github.com/SkyworkAI/Matrix-Game"]
)

writer = NdjsonWriter(out=sys.stdout)
writer.write(item)
