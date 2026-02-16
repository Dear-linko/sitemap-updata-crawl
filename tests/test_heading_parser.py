from monitor.heading_parser import extract_heading


def test_extract_h1_first() -> None:
    html = b"<html><body><h1>  Main   Title </h1><h2>Sub</h2></body></html>"
    heading, tag, reason = extract_heading(html)
    assert heading == "Main Title"
    assert tag == "h1"
    assert reason == "ok_h1"


def test_fallback_to_h2_when_h1_missing() -> None:
    html = b"<html><body><h2>Fallback Title</h2><h2>Other</h2></body></html>"
    heading, tag, reason = extract_heading(html)
    assert heading == "Fallback Title"
    assert tag == "h2"
    assert reason == "ok_h2"


def test_no_heading_found() -> None:
    html = b"<html><body><p>no heading</p></body></html>"
    heading, tag, reason = extract_heading(html)
    assert heading is None
    assert tag is None
    assert reason == "heading_not_found"


def test_skip_blank_h1_and_pick_next_h1() -> None:
    html = b"<html><body><h1>   </h1><h1>Good One</h1><h2>Sub</h2></body></html>"
    heading, tag, reason = extract_heading(html)
    assert heading == "Good One"
    assert tag == "h1"
    assert reason == "ok_h1"
