from io import BytesIO

def extract_resume_text(data, filename):
    filename = filename.lower()
    if filename.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    if filename.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
    if filename.endswith(".docx"):
        from docx import Document
        return "\n".join(paragraph.text for paragraph in Document(BytesIO(data)).paragraphs)
    raise ValueError("Supported CV formats are PDF, DOCX and TXT.")
