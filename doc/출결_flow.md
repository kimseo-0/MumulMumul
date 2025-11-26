```
flowchart LR
    A[입력: class_id, date_range] --> B[AttendanceCalculator\n출결 계산]
    A --> C[MeetingActivityCalculator\n회의 활동 계산]
    A --> D[ChatbotActivityCalculator\n챗봇 질문 계산]

    B --> E[AIReportGenerator\n(LLM)]
    C --> E
    D --> E

    E --> F[최종 출결 리포트 payload]
```