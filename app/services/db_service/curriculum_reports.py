from datetime import datetime
from typing import Dict, Any, Mapping, Union

from pydantic import BaseModel
from app.core.mongodb import get_mongo_db
from app.core.mongodb import CurriculumReport

from pymongo.database import Database

mongo_db: Database = get_mongo_db()
report_col = mongo_db["curriculum_reports"]

def fetch_curriculum_report(
    camp_id: int,
    week_index: int,
) -> CurriculumReport | None:
    """
    MongoDB에서 기존 커리큘럼 리포트를 조회한다.
    없으면 None 반환.
    """
    report = report_col.find_one(
            {"camp_id": camp_id, "week_index": week_index}
        )
    return report

def upsert_curriculum_report(
    camp_id: int,
    week_index: int,
    report_data: Union["CurriculumReport", Mapping[str, Any]],
) -> None:
    """
    MongoDB에 커리큘럼 리포트를 upsert 한다.
    - camp_id + week_index 기준으로 upsert
    - report_data는 Pydantic 모델 또는 dict 모두 허용
    """

    now = datetime.utcnow()

    # 1) top-level: 모델이면 먼저 한 번 풀어줌
    if isinstance(report_data, BaseModel):
        doc: Any = report_data.model_dump()
    else:
        doc = dict(report_data)

    def convert(obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            return obj.model_dump()

        if isinstance(obj, Mapping):
            return {k: convert(v) for k, v in obj.items()}

        if isinstance(obj, (list, tuple, set)):
            return [convert(v) for v in obj]

        return obj

    # 3) nested 까지 전부 Mongo 호환 타입으로 변환
    doc = convert(doc)

    # 4) camp_id / week_index 강제 세팅
    doc["camp_id"] = camp_id
    doc["week_index"] = week_index

    # 5) upsert
    report_col.update_one(
        {"camp_id": camp_id, "week_index": week_index},
        {
            "$set": doc,
        },
        upsert=True,
    )