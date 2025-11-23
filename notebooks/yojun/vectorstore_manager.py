import os
import re
from dotenv import load_dotenv
from openai import OpenAI
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

import pytesseract
from PIL import Image
import fitz  # PyMuPDF
from langchain_core.documents import Document

load_dotenv()
client = OpenAI()


def ocr_pdf(pdf_path):
    """텍스트가 없는 페이지를 OCR로 읽어서 Document 리스트 반환"""
    ocr_docs = []
    pdf = fitz.open(pdf_path)

    for page_idx in range(len(pdf)):
        page = pdf[page_idx]

        # 이미지 렌더링
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # OCR 텍스트 추출
        text = pytesseract.image_to_string(img, lang="kor+eng")

        ocr_docs.append(
            Document(
                page_content=text,
                metadata={"page": page_idx + 1}
            )
        )

    return ocr_docs


def translate_title_to_english(title: str) -> str:
    """한글 PDF 제목을 영어 폴더명으로 변환"""
    prompt = f"""
    Convert this Korean lecture PDF title into a natural English folder name.
    Conditions:
    - Use underscores instead of spaces
    - Remove special characters
    - Keep the meaning clear
    Title: {title}
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content.strip().lower()


def sanitize(name: str) -> str:
    """폴더명 안전하게 변환"""
    name = name.lower()
    name = re.sub(r"[^a-z0-9_-]+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_-")
    if len(name) < 3:
        name = "db_" + name
    return name


def save_month_folder_to_vectorstore(month_folder: str, db_root: str, month: str):
    """월별 폴더의 PDF를 하나씩 벡터스토어에 저장 (PDF별 개별 Chroma로 저장)"""

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    embedding = OpenAIEmbeddings(model="text-embedding-3-large")

    # lecture_08 같은 월별 폴더 생성
    month_path = os.path.join(db_root, f"lecture_{month}")
    os.makedirs(month_path, exist_ok=True)

    # PDF 하나씩 처리
    for filename in os.listdir(month_folder):
        if not filename.endswith(".pdf"):
            continue

        original_title = os.path.splitext(filename)[0]

        print(f"\n📘 제목 번역 중 → {original_title}")
        eng_title = translate_title_to_english(original_title)
        safe_name = sanitize(eng_title)
        print(f"➡ 영어 폴더명 생성: {safe_name}")

        pdf_path = os.path.join(month_folder, filename)

        # PyMuPDFLoader로 로딩 시도
        loader = PyMuPDFLoader(pdf_path)
        docs = loader.load()

        # 텍스트가 비어있으면 OCR fallback
        if len(docs) == 0 or all(len(d.page_content.strip()) == 0 for d in docs):
            print("⚠ PyMuPDFLoader 텍스트 없음 → OCR 실행")
            docs = ocr_pdf(pdf_path)

        total_pages = len(docs)

        # chunk 생성
        chunk_docs = []
        for doc_idx, doc in enumerate(docs):
            chunk_texts = splitter.split_text(doc.page_content)

            for chunk in chunk_texts:
                chunk_docs.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "month": month,
                            "filename": original_title,
                            "filename_eng": safe_name,
                            "page": doc_idx + 1,
                            "total_pages": total_pages
                        }
                    )
                )

        # PDF 이름으로 개별 저장 경로 생성
        store_path = os.path.join(month_path, safe_name)
        os.makedirs(store_path, exist_ok=True)

        # PDF별 독립 Chroma 저장
        Chroma.from_documents(
            documents=chunk_docs,
            embedding=embedding,
            persist_directory=store_path,
            collection_name=safe_name
        )

        print(f"✔ 저장 완료 → {store_path}")

    print("\n🎉 전체 벡터 저장 완료!")
