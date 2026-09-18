"""补植登记与成活复核接口。"""

from flask import Blueprint, request

from ..schemas import (
    replanting_filters,
    validate_replant_review,
    validate_replanting,
)
from ..services import ReplantingService
from ..utils.pagination import paginate, parse_page_args
from ..utils.requests import json_body
from ..utils.responses import created, ok

bp = Blueprint("replantings", __name__)


@bp.get("/replantings")
def list_replantings():
    filters = replanting_filters(request.args)
    page, page_size = parse_page_args()
    query = ReplantingService.list_replantings(filters, request.args)
    data = paginate(query, page, page_size)
    data["summary"] = ReplantingService.summary(filters)
    return ok(data)


@bp.get("/replantings/summary")
def replanting_summary():
    return ok(ReplantingService.summary(replanting_filters(request.args)))


@bp.post("/replantings")
def create_replanting():
    payload = validate_replanting(json_body())
    replanting = ReplantingService.create(payload)
    return created(replanting.to_dict(detail=True), message="补植记录登记成功")


@bp.get("/replantings/<int:replanting_id>")
def get_replanting(replanting_id):
    return ok(ReplantingService.detail(replanting_id))


@bp.put("/replantings/<int:replanting_id>")
def update_replanting(replanting_id):
    payload = validate_replanting(json_body())
    replanting = ReplantingService.update(replanting_id, payload)
    return ok(replanting.to_dict(detail=True), message="补植记录已更新")


@bp.patch("/replantings/<int:replanting_id>/review")
def register_review(replanting_id):
    payload = validate_replant_review(json_body())
    replanting = ReplantingService.register_review(replanting_id, payload)
    return ok(replanting.to_dict(detail=True), message="成活复核已登记")


@bp.delete("/replantings/<int:replanting_id>")
def delete_replanting(replanting_id):
    ReplantingService.delete(replanting_id)
    return ok(None, message="补植记录已删除")
