from pathlib import Path


FRONTEND = Path(__file__).parents[1] / "static" / "index.html"


def test_frontend_exposes_api_documentation():
    html = FRONTEND.read_text()

    assert 'href="/docs"' in html
    assert 'rel="service-desc"' in html
    assert 'href="/openapi.json"' in html
