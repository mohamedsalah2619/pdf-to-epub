#!/usr/bin/env python3
"""
PDF to EPUB Web App - Streamlit
"""

import io
import re
import tempfile
from pathlib import Path

import streamlit as st
import pdfplumber
from pypdf import PdfReader
from ebooklib import epub


# ==================== Page Config ====================
st.set_page_config(
    page_title="PDF → EPUB Converter",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==================== Custom CSS ====================
st.markdown("""
<style>
    .stApp {
        max-width: 800px;
        margin: 0 auto;
    }
    .main-title {
        text-align: center;
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.3rem;
        color: #1f2937;
    }
    .subtitle {
        text-align: center;
        color: #6b7280;
        margin-bottom: 2rem;
        font-size: 1.05rem;
    }
    .stDownloadButton > button {
        width: 100%;
        background-color: #10b981 !important;
        color: white !important;
        font-weight: 600;
        border-radius: 8px;
        padding: 0.6rem 1rem;
    }
    .success-box {
        background-color: #ecfdf5;
        border: 1px solid #10b981;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# ==================== Helper Functions ====================
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [line.strip() for line in text.splitlines()]
    return '\n'.join(lines).strip()


def extract_text_from_pdf(pdf_file, progress_bar=None) -> list[str]:
    """Extract text page by page."""
    pages_text = []
    
    # Save uploaded file to temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_file.getvalue())
        tmp_path = tmp.name

    try:
        with pdfplumber.open(tmp_path) as pdf:
            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages_text.append(clean_text(text))
                if progress_bar:
                    progress_bar.progress((i + 1) / total, text=f"استخراج الصفحة {i+1} من {total}")
    except Exception:
        # Fallback to pypdf
        reader = PdfReader(tmp_path)
        total = len(reader.pages)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages_text.append(clean_text(text))
            if progress_bar:
                progress_bar.progress((i + 1) / total, text=f"استخراج الصفحة {i+1} من {total}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return pages_text


def create_epub_bytes(
    pages_text: list[str],
    title: str = "Converted Book",
    author: str = "Unknown",
    language: str = "ar",
    pages_per_chapter: int = 8,
) -> bytes:
    """Create EPUB and return as bytes."""
    book = epub.EpubBook()

    book.set_identifier(f"pdf2epub-{abs(hash(title)) % 10**10}")
    book.set_title(title)
    book.set_language(language)
    book.add_author(author)

    # CSS
    style = """
    @namespace epub "http://www.idpf.org/2007/ops";
    body {
        font-family: "Amiri", "Scheherazade New", "Noto Naskh Arabic", "Georgia", serif;
        line-height: 1.75;
        margin: 1.2em;
        direction: rtl;
        text-align: right;
    }
    h1 {
        text-align: center;
        margin: 1.8em 0 1em 0;
        font-size: 1.5em;
    }
    p {
        margin: 0.7em 0;
        text-indent: 1.3em;
    }
    """
    nav_css = epub.EpubItem(
        uid="style_nav",
        file_name="style/nav.css",
        media_type="text/css",
        content=style
    )
    book.add_item(nav_css)

    chapters = []
    spine = ["nav"]
    toc = []
    total_pages = len(pages_text)
    chapter_num = 1

    for start in range(0, total_pages, pages_per_chapter):
        end = min(start + pages_per_chapter, total_pages)
        chapter_pages = pages_text[start:end]

        content_parts = [f"<h1>الفصل {chapter_num}</h1>"]
        for page_text in chapter_pages:
            if page_text.strip():
                paragraphs = page_text.split("\n\n")
                for para in paragraphs:
                    para = para.strip().replace("\n", " ")
                    if para:
                        # Escape basic HTML
                        para = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        content_parts.append(f"<p>{para}</p>")

        chapter_content = "\n".join(content_parts)
        if len(chapter_content) < 60:
            continue

        c = epub.EpubHtml(
            title=f"الفصل {chapter_num}",
            file_name=f"chap_{chapter_num:03d}.xhtml",
            lang=language,
        )
        c.content = f"""<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" 
      xml:lang="{language}" lang="{language}" dir="rtl">
<head>
    <title>الفصل {chapter_num}</title>
    <link rel="stylesheet" type="text/css" href="style/nav.css"/>
</head>
<body>
{chapter_content}
</body>
</html>"""
        c.add_item(nav_css)
        book.add_item(c)
        chapters.append(c)
        spine.append(c)
        toc.append(c)
        chapter_num += 1

    if not chapters:
        raise ValueError("لم يتم العثور على نص كافٍ في الملف. تأكد أن الـ PDF يحتوي على نص قابل للاختيار (مش صور فقط).")

    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    # Write to memory
    buffer = io.BytesIO()
    epub.write_epub(buffer, book)
    buffer.seek(0)
    return buffer.getvalue()


# ==================== UI ====================
st.markdown('<div class="main-title">📚 محول PDF إلى EPUB</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">ارفع ملف PDF واحصل على كتاب إلكتروني جاهز للقراءة</div>', unsafe_allow_html=True)

# Upload
uploaded_file = st.file_uploader(
    "اختر ملف PDF",
    type=["pdf"],
    help="يفضل أن يكون الـ PDF فيه نص قابل للاختيار (مش سكاند)"
)

# Settings
with st.expander("⚙️ إعدادات متقدمة", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("عنوان الكتاب", value="")
        author = st.text_input("اسم المؤلف", value="Unknown")
    with col2:
        language = st.selectbox("اللغة", options=["ar", "en"], index=0, 
                                format_func=lambda x: "العربية" if x == "ar" else "English")
        pages_per_chapter = st.slider("عدد الصفحات لكل فصل", min_value=3, max_value=20, value=8)

# Convert button
if uploaded_file is not None:
    if not title:
        title = Path(uploaded_file.name).stem

    st.write(f"**الملف:** `{uploaded_file.name}` ({uploaded_file.size / 1024:.1f} KB)")

    if st.button("🔄 تحويل إلى EPUB", type="primary", use_container_width=True):
        try:
            progress = st.progress(0, text="جاري بدء التحويل...")
            
            # Extract
            pages = extract_text_from_pdf(uploaded_file, progress_bar=progress)
            
            progress.progress(0.85, text="جاري إنشاء ملف EPUB...")
            
            # Create EPUB
            epub_bytes = create_epub_bytes(
                pages_text=pages,
                title=title,
                author=author,
                language=language,
                pages_per_chapter=pages_per_chapter,
            )
            
            progress.progress(1.0, text="تم بنجاح!")
            
            st.markdown(f"""
            <div class="success-box">
                <h3 style="margin:0; color:#065f46;">✅ تم التحويل بنجاح!</h3>
                <p style="margin:0.5rem 0 0 0; color:#047857;">
                    عدد الصفحات: {len(pages)} &nbsp;|&nbsp; حجم الملف: {len(epub_bytes)/1024:.1f} KB
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Download
            output_name = Path(uploaded_file.name).stem + ".epub"
            st.download_button(
                label="⬇️ تحميل ملف EPUB",
                data=epub_bytes,
                file_name=output_name,
                mime="application/epub+zip",
                use_container_width=True
            )
            
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"حدث خطأ أثناء التحويل: {str(e)}")

else:
    st.info("👆 ارفع ملف PDF للبدء")

# Footer
st.markdown("---")
st.caption("يعمل بشكل ممتاز مع ملفات PDF اللي فيها نص. ملفات السكاند (صور فقط) تحتاج OCR وغير مدعومة حالياً.")