from src.url.router import UrlRouter

def test_router_groups_before_model():
    urls = [
        "https://huggingface.co/datasets/u/ds1",
        "https://github.com/o/r1",
        "https://huggingface.co/google/gemma-3-270m",
    ]
    items = list(UrlRouter().route(urls))
    assert len(items) == 1
    m = items[0]
    assert m.datasets and m.code
