import os
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv

# .env 파일 로드 (OpenAI API Key를 환경 변수에서 사용하기 위함)
load_dotenv()

def create_and_save_vectorstore(file_path: str, db_path: str, collection_name: str = "Lecture"):
    """
    PDF 파일을 로드하고, 텍스트를 청크로 분할한 후, 
    OpenAI 임베딩을 사용하여 Chroma VectorStore에 저장하는 함수입니다.

    Args:
        file_path (str): 로드할 PDF 파일의 전체 경로.
        db_path (str): 벡터 저장소(Chroma)를 저장할 디렉토리 경로.
        collection_name (str): 벡터 저장소 내에서 데이터를 저장할 컬렉션 이름 (기본값: "Lecture").

    Returns:
        Chroma: 생성 및 저장된 Chroma VectorStore 객체.
    """
    
    # 1. 파일 존재 여부 확인
    if not os.path.exists(file_path):
        print(f"오류: 파일을 찾을 수 없습니다. 경로: {file_path}")
        return None
        
    print(f"=== 1. 문서 로드 중: {file_path} ===")
    try:
        # 2. 문서 로드 (PyMuPDFLoader 사용)
        loader = PyMuPDFLoader(file_path)
        docs = loader.load()
    except Exception as e:
        print(f"오류: 문서 로드 중 예외 발생: {e}")
        return None

    if not docs:
        print("오류: 로드된 문서 내용이 없습니다.")
        return None

    print(f"총 {len(docs)} 페이지 로드 완료.")

    # 3. 텍스트 스플리터(청킹) 설정
    print("=== 2. 텍스트 청크 분할 중 ===")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,     # 한 조각(chunk)의 최대 문자 수
        chunk_overlap=100,   # 조각 간에 겹치는 문자 수
        separators=["\n\n", "\n", " ", ""]  # 텍스트 분할 우선순위
    )

    # 문서(docs)를 여러 개의 chunk로 분리
    chunks = splitter.split_documents(docs)
    print(f"총 {len(chunks)} 개의 청크(조각)로 분할 완료.")

    # 4. 임베딩 모델 및 벡터 저장소 설정
    print("=== 3. 임베딩 생성 및 VectorStore 저장 중 ===")
    # text-embedding-3-small 모델 사용
    embedding = OpenAIEmbeddings(model="text-embedding-3-small") 

    # 5. Chroma VectorStore 생성 및 지정된 경로에 저장
    try:
        # from_documents를 사용하여 청크를 벡터화하고 db_path에 저장
        vectorstore = Chroma.from_documents(
            documents=chunks,                  # 분할된 문서 조각 리스트
            embedding=embedding,               # 사용할 임베딩 모델
            persist_directory=db_path,         # 벡터 데이터를 저장할 폴더 경로
            collection_name=collection_name    # 데이터 컬렉션 이름 지정
        )
        print(f"성공: 벡터 저장소 저장 완료! 경로: {db_path}, 컬렉션: {collection_name}")
        return vectorstore
        
    except Exception as e:
        print(f"오류: Chroma VectorStore 저장 중 예외 발생: {e}")
        return None



# --- 함수 사용 예시 ---
if __name__ == '__main__':
    # 실제 파일 경로와 저장소 경로로 변경해야 합니다.
    # __file__ 변수가 Jupyter 환경에서는 정의되지 않으므로, 절대 경로를 사용하거나 
    # 현재 디렉토리를 기준으로 경로를 조정해야 합니다.
    
    # 예시 경로 설정 (사용자의 코드에 있던 경로를 참고하여 가정)
    example_file_path = "C:\\POTENUP\\MumulMumul\\storage\\lectures\\01 파이썬 기초 문법 I (변수, 자료형).pdf"
    example_db_path = "C:\\POTENUP\\MumulMumul\\storage\\vectorstore"
    example_collection_name = "Python_Lecture"
    
    # 윈도우 환경에서는 raw string 또는 슬래시(/)를 사용하는 것이 경로 오류를 줄이는 데 도움이 됩니다.
    # 예: r"C:\POTENUP\..." 또는 "C:/POTENUP/..."
    # 여기서는 예시 코드를 위해 주석 처리하고 사용자에게 경로 수정을 안내합니다.
    
    # 테스트를 위해 임시로 존재하지 않는 경로를 사용하겠습니다. 실제 사용 시에는 경로를 바꿔주세요.
    
    # 실제 사용 예시:
    # my_file_path = "path/to/your/document.pdf" 
    # my_db_path = "./my_chroma_db"
    
    # vector_db = create_and_save_vectorstore(
    #     file_path=my_file_path, 
    #     db_path=my_db_path, 
    #     collection_name="My_Documents"
    # )
    
    # if vector_db:
    #     print("\n검색기(Retriever) 테스트:")
    #     retriever = vector_db.as_retriever(search_kwargs={"k": 2})
    #     query = "파이썬 변수 생성 규칙이 뭐야?"
    #     results = retriever.invoke(query)
    #     print(f"검색어: {query}")
    #     for i, doc in enumerate(results):
    #         print(f"--- [검색 결과 {i+1}] ---")
    #         print(doc.page_content[:200] + "...")