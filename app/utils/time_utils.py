# isoformat 을 datetime 객체로 변환
from datetime import datetime
def parse_iso8601_to_datetime(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str)

# import datetime 객체를 isoformat 문자열로 변환
def datetime_to_isoformat(dt: datetime) -> str:
    return dt.isoformat()

# import datetime 객체를 특정 포맷의 문자열로 변환(2025년 12월 31일 오후 11:59분 59초)
def datetime_to_custom_str(dt: datetime) -> str:
    return dt.strftime("%Y년 %m월 %d일 %p %I:%M")

def datetime_to_iso_milliseconds(dt: datetime) -> str:
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")