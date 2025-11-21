# interactive_chatbot.py
"""
직접 질문을 입력해서 테스트하기
"""
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv

load_dotenv()

def ask(q: str, db_path: str) -> str:
    vs = Chroma(
        persist_directory=db_path, 
        embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"), 
        collection_name="control_statement"
    )
    llm = ChatOpenAI(model="gpt-4o-mini")
    is_learning = "YES" in llm.invoke(f"학습질문이면YES 아니면NO: {q}").content
    
    if is_learning:
        docs = vs.similarity_search(q, k=3)
        context = "\n".join([d.page_content for d in docs])
        return llm.invoke(f"자료:\n{context}\n\n질문: {q}\n\n답변하세요.").content
    else:
        return llm.invoke(f"{q}\n간단답변+학습질문유도").content


# ===== 대화형 테스트 =====
if __name__ == "__main__":
    DB_PATH = "C:/POTENUP/MumulMumul/storage/vectorstore"
    
    print("="*60)
    print("🤖 머물머울 학습 도우미 (대화형 모드)")
    print("="*60)
    print("💡 종료하려면 'quit' 또는 'exit' 입력")
    print("="*60)
    
    while True:
        # 사용자 입력 받기
        question = input("\n💬 질문을 입력하세요: ").strip()
        
        # 종료 명령어 체크
        if question.lower() in ['quit', 'exit', '종료', 'q']:
            print("\n👋 챗봇을 종료합니다. 좋은 하루 되세요!")
            break
        
        # 빈 입력 무시
        if not question:
            print("❌ 질문을 입력해주세요!")
            continue
        
        # 답변 생성
        print("\n⏳ 답변 생성 중...")
        try:
            answer = ask(question, DB_PATH)
            print(f"\n🤖 답변:\n{answer}")
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
        
        print("\n" + "-"*60)