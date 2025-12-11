from app.services.learning_quiz.llm import generate_quiz

def test_make_quiz(question, grade):
    
    # STEP 4 테스트용 context (나중에는 vectorstore에서 가져옴)
    dummy_context = """
    Pandas에서 DataFrame을 합치는 방법은 merge(), concat(), join()이 있다.
    merge()는 SQL JOIN처럼 동작하며 공통 column을 기준으로 결합한다.
    concat()은 DataFrame을 행 또는 열 기준으로 합칠 수 있다.
    """

    question = "판다스에서 데이터프레임을 어떻게 합치는지 알려줘"
    grade = "초급"

    result = generate_quiz(dummy_context, question, grade)
    
    for q in result.quiz:
        print(q.id, q.type, q.question, q.answer)

    return result  


