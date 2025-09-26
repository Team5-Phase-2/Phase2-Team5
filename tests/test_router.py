from src.url.router import UrlRouter, ModelItem

def route_list(urls):
    return list(UrlRouter().route(urls))

def test_grouping_basic():
    urls = [
        "https://huggingface.co/datasets/foo/bar",
        "https://github.com/acme/repo",
        "https://huggingface.co/google/gemma-3-270m",
    ]
    items = route_list(urls)
    assert len(items) == 1
    it = items[0]
    assert it.model_url.endswith("google/gemma-3-270m")
    assert "datasets/foo/bar" in it.datasets[0]
    assert "github.com/acme/repo" in it.code[0]

def test_skips_unknown():
    urls = [
        "https://example.com/whatever",
        "https://huggingface.co/google/gemma-3-270m",
    ]
    items = route_list(urls)
    assert len(items) == 1
    assert items[0].datasets == []
    assert items[0].code == []

def test_multiple_models_split_groups():
    urls = [
        "https://huggingface.co/datasets/d1/a",
        "https://huggingface.co/google/modelA",
        "https://huggingface.co/datasets/d2/b",
        "https://github.com/foo/bar",
        "https://huggingface.co/openai/modelB",
    ]
    items = route_list(urls)
    assert len(items) == 2
    assert "google/modelA" in items[0].model_url
    assert items[0].datasets == ["https://huggingface.co/datasets/d1/a"]
    assert "openai/modelB" in items[1].model_url
    assert items[1].datasets == ["https://huggingface.co/datasets/d2/b"]
    assert items[1].code == ["https://github.com/foo/bar"]

def test_empty_and_spaces():
    items = route_list(["", "   ", "\n"])
    assert items == []

def test_no_dangling_collections():
    urls = [
        "https://huggingface.co/datasets/d1/a",
        "https://huggingface.co/google/modelA",
        "https://huggingface.co/openai/modelB",
    ]
    items = route_list(urls)
    assert len(items) == 2
    assert items[0].datasets == ["https://huggingface.co/datasets/d1/a"]
    assert items[1].datasets == []  # cleared after first model

def test_modelitem_dataclass():
    mi = ModelItem("m", ["d"], ["c"])
    assert mi.model_url == "m"
    assert mi.datasets == ["d"]
    assert mi.code == ["c"]
