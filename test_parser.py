from bfi_odyssey_monitor import parse_items_from_html, total_pages_from_html, page_url_template

# Real BFI markup: two sold-out rows + one constructed AVAILABLE row + pagination
html = '''
<div class="results">
<div class="odd result-box-item"><div class="item-description result-box-item-details">
<div class="item-name"><a href="x" class="more-info">The Odyssey</a></div>
<div class="item-start-date"><span class="start-date-label">-</span><span class="start-date">Sunday 19 July 2026 20:20</span></div>
<div class="item-venue">BFI IMAX</div></div>
<div class="item-link result-box-item-details last-column soldout"><span class="unavailable-message">Sold out!</span></div></div>

<div class="even result-box-item"><div class="item-description result-box-item-details">
<div class="item-name"><a href="x" class="more-info">The Odyssey</a></div>
<div class="item-start-date"><span class="start-date-label">-</span><span class="start-date">Monday 20 July 2026 08:30</span></div>
<div class="item-venue">BFI IMAX</div></div>
<div class="item-link result-box-item-details last-column soldout"><span class="unavailable-message">Sold out!</span></div></div>

<div class="odd result-box-item"><div class="item-description result-box-item-details">
<div class="item-name"><a href="x" class="more-info">The Odyssey</a></div>
<div class="item-start-date"><span class="start-date-label">-</span><span class="start-date">Saturday 15 August 2026 19:00</span></div>
<div class="item-venue">BFI IMAX</div></div>
<div class="item-link result-box-item-details last-column"><a href="book" class="button">Book</a></div></div>

<div class="pagination">
<a href="/imax/Online/default.asp?sToken=ABC&BOset::WScontent::SearchResultsInfo::current_page=2&doWork::WScontent::getPage=1">2</a>
<a href="/imax/Online/default.asp?sToken=ABC&BOset::WScontent::SearchResultsInfo::current_page=32">32</a>
</div></div>
'''

items = parse_items_from_html(html)
print("Parsed items:")
for i in items: print(" ", i)
assert len(items) == 3, items
assert items[0]["status"] == "Sold out"
assert items[2]["status"] == "Available", "available row not detected!"
print("total_pages:", total_pages_from_html(html))
assert total_pages_from_html(html) == 32

build = page_url_template(html, "https://whatson.bfi.org.uk/imax/Online/default.asp")
print("page 7 URL:", build(7))
assert "current_page=7" in build(7)
print("\nALL PARSER TESTS PASSED")
