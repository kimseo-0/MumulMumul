import os
import re
from dotenv import load_dotenv
from openai import OpenAI

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

import pytesseract
from PIL import Image
import fitz  # PyMuPDF

load_dotenv()
client = OpenAI()


# ---------------- OCR 품질 체크 ----------------
def is_text_meaningful(text: str, min_length=20, min_alpha_ratio=0.4) -> bool:
    text = text.strip()
    if len(text) < min_length:
        return False

    valid = sum(c.isalnum() for c in text)
    total = sum(1 for c in text if not c.isspace())

    if total == 0:
        return False

    return valid / total >= min_alpha_ratio


# ---------------- OCR ----------------
def ocr_pdf(pdf_path):
    ocr_docs = []
    pdf = fitz.open(pdf_path)
    config = "--oem 3 --psm 3"

    for idx, page in enumerate(pdf):
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang="kor+eng", config=config)

        ocr_docs.append(
            Document(page_content=text, metadata={"page": idx + 1})
        )

    return ocr_docs


# ---------------- 제목 영어 변환 ----------------
def translate_title_to_english(title: str):
    prompt = f"""
    Convert this Korean lecture PDF title into a clean English name.
    Use underscores. Remove special characters.
    Title: {title}
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return resp.choices[0].message.content.strip().lower()


# ---------------- 파일명 정리 ----------------
def sanitize(name: str):
    name = re.sub(r"[^a-z0-9_-]+", "_", name.lower())
    name = re.sub(r"_+", "_", name)
    return name.strip("_-")


def chunck_pdf(month_folder):
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)

    all_chunks = []
    for filename in os.listdir(month_folder):
        if not filename.endswith(".pdf"):
            continue

        print(f"\n📘 처리 중 → {filename}")

        original_title = os.path.splitext(filename)[0]
        eng_title = sanitize(translate_title_to_english(original_title))

        pdf_path = os.path.join(month_folder, filename)

        # 1) PyMuPDFLoader로 로딩
        docs = PyMuPDFLoader(pdf_path).load()

        # 2) 텍스트 없으면 OCR
        if len(docs) == 0 or all(not is_text_meaningful(d.page_content) for d in docs):
            print("⚠ 텍스트 없음 → OCR 실행")
            docs = ocr_pdf(pdf_path)

        total_pages = len(docs)

        # 3) 청크 생성 후 전체 리스트에 저장
        for idx, doc in enumerate(docs):

            if not is_text_meaningful(doc.page_content):
                continue

            chunk_texts = splitter.split_text(doc.page_content)

            for chunk in chunk_texts:
                if not is_text_meaningful(chunk):
                    continue
                
                all_chunks.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "filename": original_title,
                            "filename_eng": eng_title,
                            "page": idx + 1,
                            "total_pages": total_pages,
                        }
                    )
                )

        print(f"   ✔ 청크 누적 개수: {len(all_chunks)}")

    return all_chunks


# -----------------------------------------------------
#         ★★★ 월별 PDF → 1개의 Chroma DB 통합 저장 ★★★
# -----------------------------------------------------
def save_month_folder_to_vectorstore(folder: str, db_root: str, month: str):
    embedding = OpenAIEmbeddings(model="text-embedding-3-large")

    # 저장 경로 = curriculum_07
    store_path = os.path.join(db_root, f"curriculum_{month}")
    os.makedirs(store_path, exist_ok=True)

    # 전체 월 데이터를 모을 리스트
    all_chunks = []
    for folderName in os.listdir(folder):
        full_path = os.path.join(folder, folderName)

        # 폴더인지 확인
        if os.path.isdir(full_path):
            print(f"{folderName} 폴더 벡터스토어 저장 시작")
            chunck = chunck_pdf(full_path)
            all_chunks.extend(chunck)

    # ---------------------------
    # 4) Chroma 1개로 통합 저장
    # ---------------------------

    print(f"\n✨ 최종 청크 {len(all_chunks)}개 통합 저장 중…")

    Chroma.from_documents(
        documents=all_chunks,
        embedding=embedding,
        persist_directory=store_path,
        collection_name=f"curriculum_{month}"
    )

    print(f"✔ 통합 DB 생성 완료 → {store_path}")
    print("\n🎉 모든 벡터 저장 완료!")
