import io

import pypdf

from web_search_mcp.extractors import (
    chunk_relevant_text,
    clean_extract_markdown,
    extract_pdf,
)


def test_clean_extract_markdown():
    html = "<h1>Title</h1><p>Some paragraph text with <strong>bold</strong>.</p>"
    md = clean_extract_markdown(html)
    assert "# Title" in md or "Title" in md
    assert "bold" in md


def test_extract_pdf():
    # Create simple in-memory PDF
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    text = extract_pdf(pdf_bytes)
    assert isinstance(text, str)


def test_chunk_relevant_text():
    text = (
        "Python 3.12 is released with speed improvements.\n\n"
        "Go 1.26 is released with new garbage collector.\n\n"
        "Rust 1.85 has new compiler features."
    )
    chunked = chunk_relevant_text(text, query="Go release", max_chars=100)
    assert "Go 1.26" in chunked


def test_extract_contacts_and_socials():
    from web_search_mcp.extractors import extract_contacts_and_socials

    html = """
    <html>
      <body>
        <a href="https://wa.me/905551234567">WhatsApp Support</a>
        <a href="mailto:contact@example.com">Email Us</a>
        <a href="tel:+905559876543">Call Us</a>
      </body>
    </html>
    """
    contacts = extract_contacts_and_socials(html)
    assert "+905551234567" in contacts["whatsapp"]
    assert "contact@example.com" in contacts["email"]
    assert "+905559876543" in contacts["phone"]
