import httpx

from monitor.fetcher import SitemapFetcher


def test_fetch_head_failure_fallback_get_works() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            raise httpx.ConnectTimeout("timeout")
        return httpx.Response(200, headers={"ETag": "v1"}, content=b"<xml>ok</xml>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetcher = SitemapFetcher(timeout_sec=2, user_agent="test-agent", client=client)

    head = fetcher.fetch_head("https://example.com/sitemap.xml")
    assert head.error is not None

    content = fetcher.fetch_content_hash("https://example.com/sitemap.xml")
    assert content.error is None
    assert content.content_hash is not None
    assert content.etag == "v1"

    fetcher.close()


def test_fetch_page_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html><h1>Hello</h1></html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetcher = SitemapFetcher(timeout_sec=2, user_agent="test-agent", client=client)

    page = fetcher.fetch_page("https://example.com/new-page")
    assert page.error is None
    assert page.http_status == 200
    assert page.content_bytes is not None

    fetcher.close()


def test_fetch_page_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"busy")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetcher = SitemapFetcher(timeout_sec=2, user_agent="test-agent", client=client)

    page = fetcher.fetch_page("https://example.com/new-page")
    assert page.error == "GET failed: 503"
    assert page.http_status == 503

    fetcher.close()


def test_fetch_page_client_error_is_not_treated_as_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, content=b"<html>challenge</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetcher = SitemapFetcher(timeout_sec=2, user_agent="test-agent", client=client)

    page = fetcher.fetch_page("https://example.com/new-page")
    assert page.error == "GET failed: 403"
    assert page.http_status == 403
    assert page.content_bytes is None

    fetcher.close()
