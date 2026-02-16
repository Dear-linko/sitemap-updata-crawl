import gzip

from monitor.sitemap_parser import extract_sitemap_urls


def test_extract_urls_from_xml() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
  <url><loc>https://example.com/a</loc></url>
  <url><loc>https://example.com/b</loc></url>
</urlset>
"""
    urls = extract_sitemap_urls(xml, "https://example.com/sitemap.xml")
    assert urls == ["https://example.com/a", "https://example.com/b"]


def test_extract_urls_from_gzip_xml() -> None:
    xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/c</loc></url>
</urlset>"""
    gz = gzip.compress(xml)
    urls = extract_sitemap_urls(gz, "https://example.com/sitemap.xml.gz")
    assert urls == ["https://example.com/c"]


def test_extract_urls_from_txt() -> None:
    txt = b"https://example.com/a\nhttps://example.com/b\n"
    urls = extract_sitemap_urls(txt, "https://example.com/sitemap.txt")
    assert urls == ["https://example.com/a", "https://example.com/b"]
