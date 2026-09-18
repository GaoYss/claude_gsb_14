"""补植登记与成活复核业务逻辑。"""

from sqlalchemy import case, func, or_

from ..constants import LOW_SURVIVAL_THRESHOLD
from ..errors import ValidationError
from ..extensions import db
from ..models import GreenSpace, MaintenanceRecord, Replanting
from ..utils.dates import today
from ..utils.numbers import to_float
from ..utils.sorting import parse_sort
from .base_service import BaseService
from .code_generator import daily_prefix


class ReplantingService(BaseService):
    """补植记录：登记苗木来源与规格，复核期后登记成活数量并核算成活率。"""

    model = Replanting
    label = "补植记录"
    code_field = "replant_no"
    code_width = 3

    SORTABLE = {
        "replant_date": Replanting.replant_date,
        "review_deadline": Replanting.review_deadline,
        "quantity": Replanting.quantity,
        "survival_rate": Replanting.survived_quantity,
        "created_at": Replanting.created_at,
    }

    @classmethod
    def code_prefix(cls):
        return daily_prefix("RP")

    # ------------------------------------------------------------ 校验与派生
    @classmethod
    def prepare_instance(cls, instance, payload):
        green_space_id = payload.get("green_space_id", instance.green_space_id)
        space = db.session.get(GreenSpace, green_space_id) if green_space_id else None
        if space is None:
            raise ValidationError("登记失败", details={"green_space_id": "所选绿地不存在"})

        record_id = payload.get("maintenance_record_id", instance.maintenance_record_id)
        if record_id:
            record = db.session.get(MaintenanceRecord, record_id)
            if record is None:
                raise ValidationError(
                    "登记失败", details={"maintenance_record_id": "关联的养护记录不存在"}
                )
            if record.green_space_id != space.id:
                raise ValidationError(
                    "登记失败",
                    details={"maintenance_record_id": "关联的养护记录不属于所选绿地"},
                )

        replant_date = payload.get("replant_date", instance.replant_date)
        if replant_date and space.established_date and replant_date < space.established_date:
            raise ValidationError(
                "登记失败",
                details={"replant_date": f"补植日期不能早于该绿地建成日期 {space.established_date}"},
            )

        review_deadline = payload.get("review_deadline", instance.review_deadline)
        if replant_date and review_deadline and review_deadline < replant_date:
            raise ValidationError(
                "登记失败", details={"review_deadline": "约定复核期不能早于补植日期"}
            )

        # 已复核的记录调整补植数量时，不能小于已登记的成活数量
        survived = instance.survived_quantity
        quantity = payload.get("quantity", instance.quantity)
        if survived is not None and quantity is not None and quantity < survived:
            raise ValidationError(
                "登记失败",
                details={"quantity": f"补植数量不能小于已登记的成活数量 {to_float(survived)}"},
            )

    # ------------------------------------------------------------ 成活复核
    @classmethod
    def register_review(cls, obj_id, payload):
        """登记（或重新登记）成活复核结果，死亡数量与成活率由后端统一计算。"""

        instance = cls.get(obj_id)
        survived = payload["survived_quantity"]
        if survived < 0 or survived > instance.quantity:
            raise ValidationError(
                "复核失败",
                details={"survived_quantity": f"成活数量需在 0 与补植数量 {to_float(instance.quantity)} 之间"},
            )

        reviewed_date = payload.get("reviewed_date") or today()
        if reviewed_date < instance.replant_date:
            raise ValidationError(
                "复核失败", details={"reviewed_date": "复核日期不能早于补植日期"}
            )

        # 有死亡植株时必须登记死亡原因，便于后续追溯供苗质量
        if survived < instance.quantity and not payload.get("death_cause"):
            raise ValidationError(
                "复核失败", details={"death_cause": "存在死亡植株时，请登记死亡原因"}
            )

        instance.survived_quantity = survived
        instance.reviewed_date = reviewed_date
        instance.death_cause = payload.get("death_cause")
        instance.death_detail = payload.get("death_detail")
        db.session.flush()
        db.session.commit()
        return instance

    # ------------------------------------------------------------ 查询
    @classmethod
    def _apply_filters(cls, query, filters):
        if filters.get("green_space_id"):
            query = query.filter(Replanting.green_space_id == filters["green_space_id"])
        if filters.get("maintenance_record_id"):
            query = query.filter(Replanting.maintenance_record_id == filters["maintenance_record_id"])
        if filters.get("plant_category"):
            query = query.filter(Replanting.plant_category == filters["plant_category"])
        if filters.get("source"):
            query = query.filter(Replanting.source == filters["source"])
        if filters.get("supplier"):
            query = query.filter(Replanting.supplier.like(f"%{filters['supplier']}%"))
        if filters.get("batch_no"):
            query = query.filter(Replanting.batch_no.like(f"%{filters['batch_no']}%"))
        if filters.get("date_from"):
            query = query.filter(Replanting.replant_date >= filters["date_from"])
        if filters.get("date_to"):
            query = query.filter(Replanting.replant_date <= filters["date_to"])

        status = filters.get("review_status")
        if status == "reviewed":
            query = query.filter(Replanting.survived_quantity.isnot(None))
        elif status == "pending":
            query = query.filter(
                Replanting.survived_quantity.is_(None),
                Replanting.review_deadline >= today(),
            )
        elif status == "overdue":
            query = query.filter(
                Replanting.survived_quantity.is_(None),
                Replanting.review_deadline < today(),
            )

        keyword = filters.get("keyword")
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    Replanting.replant_no.like(like),
                    Replanting.plant_name.like(like),
                    Replanting.spec.like(like),
                    Replanting.supplier.like(like),
                    Replanting.batch_no.like(like),
                    Replanting.operator.like(like),
                )
            )
        return query

    @classmethod
    def list_replantings(cls, filters, args):
        query = cls._apply_filters(db.session.query(Replanting), filters)
        return query.order_by(
            parse_sort(args, cls.SORTABLE, Replanting.replant_date.desc())
        )

    @classmethod
    def detail(cls, obj_id):
        return cls.get(obj_id).to_dict(detail=True)

    # ------------------------------------------------------------ 汇总
    @staticmethod
    def _rate(survived, quantity):
        if not quantity:
            return None
        return round(float(survived) / float(quantity) * 100, 1)

    @classmethod
    def _group_summary(cls, filters, group_column, group_label):
        """按指定维度（供苗单位 / 批次）汇总成活率，成活率只统计已复核记录。"""

        rows = (
            cls._apply_filters(
                db.session.query(
                    group_column,
                    func.count(Replanting.id),
                    func.coalesce(func.sum(Replanting.quantity), 0),
                    func.sum(
                        case(
                            (Replanting.survived_quantity.isnot(None), 1),
                            else_=0,
                        )
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    Replanting.survived_quantity.isnot(None),
                                    Replanting.quantity,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(func.sum(Replanting.survived_quantity), 0),
                ),
                filters,
            )
            .group_by(group_column)
            .all()
        )

        result = []
        for value, count, total_qty, reviewed_count, reviewed_qty, survived_qty in rows:
            rate = cls._rate(survived_qty, reviewed_qty)
            result.append({
                group_label: value,
                "count": count,
                "quantity": to_float(total_qty) or 0,
                "reviewed_count": reviewed_count or 0,
                "pending_count": (count or 0) - (reviewed_count or 0),
                "reviewed_quantity": to_float(reviewed_qty) or 0,
                "survived_quantity": to_float(survived_qty) or 0,
                "dead_quantity": to_float((reviewed_qty or 0) - (survived_qty or 0)) or 0,
                "survival_rate": rate,
                "low_survival": rate is not None and rate < LOW_SURVIVAL_THRESHOLD,
            })
        result.sort(key=lambda item: (item["survival_rate"] is None, item["survival_rate"] or 0))
        return result

    @classmethod
    def summary(cls, filters):
        """补植汇总：总体进度 + 按供苗单位与批次的成活率（偏低自动标记）。"""

        totals = cls._apply_filters(
            db.session.query(
                func.count(Replanting.id),
                func.coalesce(func.sum(Replanting.quantity), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (Replanting.survived_quantity.isnot(None), 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Replanting.survived_quantity.is_(None)
                                & (Replanting.review_deadline < today()),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Replanting.survived_quantity.isnot(None),
                                Replanting.quantity,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(func.sum(Replanting.survived_quantity), 0),
            ),
            filters,
        ).one()

        total_count, total_qty, reviewed_count, overdue_count, reviewed_qty, survived_qty = totals
        overall_rate = cls._rate(survived_qty, reviewed_qty)

        by_supplier = cls._group_summary(filters, Replanting.supplier, "supplier")
        by_batch = cls._group_summary(filters, Replanting.batch_no, "batch_no")

        return {
            "threshold": LOW_SURVIVAL_THRESHOLD,
            "total_count": total_count or 0,
            "total_quantity": to_float(total_qty) or 0,
            "reviewed_count": reviewed_count or 0,
            "pending_count": (total_count or 0) - (reviewed_count or 0),
            "overdue_count": overdue_count or 0,
            "reviewed_quantity": to_float(reviewed_qty) or 0,
            "survived_quantity": to_float(survived_qty) or 0,
            "dead_quantity": to_float((reviewed_qty or 0) - (survived_qty or 0)) or 0,
            "survival_rate": overall_rate,
            "low_survival": overall_rate is not None and overall_rate < LOW_SURVIVAL_THRESHOLD,
            "low_supplier_count": sum(1 for item in by_supplier if item["low_survival"]),
            "low_batch_count": sum(1 for item in by_batch if item["low_survival"]),
            "by_supplier": by_supplier,
            "by_batch": by_batch,
        }
