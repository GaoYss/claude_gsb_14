"""补植作业成活跟踪接口。"""

from flask import Blueprint, request

from ..schemas import (
    replanting_filters,
    validate_replanting,
    validate_replanting_review,
)
from ..services import ReplantingService
from ..utils.pagination import paginate, parse_page_args
from ..utils.requests import json_body
from ..utils.responses import created, ok

bp = Blueprint("replanting_records", __name__)


@bp.get("/replanting-records")
def list_records():
    filters = replanting_filters(request.args)
    page, page_size = parse_page_args()
    query = ReplantingService.list_records(filters, request.args)
    data = paginate(query, page, page_size)
    data["summary"] = ReplantingService.summary(filters)
    return ok(data)


@bp.get("/replanting-records/summary")
def record_summary():
    return ok(ReplantingService.summary(replanting_filters(request.args)))


@bp.post("/replanting-records")
def create_record():
    payload = validate_replanting(json_body())
    record = ReplantingService.create(payload)
    return created(record.to_dict(detail=True), message="补植作业登记成功")


@bp.get("/replanting-records/<int:record_id>")
def get_record(record_id):
    return ok(ReplantingService.detail(record_id))


@bp.put("/replanting-records/<int:record_id>")
def update_record(record_id):
    payload = validate_replanting(json_body())
    record = ReplantingService.update(record_id, payload)
    return ok(record.to_dict(detail=True), message="补植作业记录已更新")


@bp.patch("/replanting-records/<int:record_id>/review")
def register_review(record_id):
    """约定复核期后登记成活数量与死亡原因。"""

    payload = validate_replanting_review(json_body())
    record = ReplantingService.register_review(record_id, payload)
    return ok(record.to_dict(detail=True), message="成活复核已登记")


@bp.delete("/replanting-records/<int:record_id>")
def delete_record(record_id):
    ReplantingService.delete(record_id)
    return ok(None, message="补植作业记录已删除")
