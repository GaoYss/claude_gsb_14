"""补植作业成活跟踪业务逻辑。"""

from sqlalchemy import and_, case, func, or_

from ..constants import LOW_SURVIVAL_THRESHOLD
from ..errors import ValidationError
from ..extensions import db
from ..models import GreenSpace, MaintenanceRecord, ReplantingRecord
from ..utils.dates import today
from ..utils.numbers import to_float
from ..utils.sorting import parse_sort
from .base_service import BaseService
from .code_generator import daily_prefix


class ReplantingService(BaseService):
    """补植作业：登记苗木来源与约定复核期，复核后核算成活率并汇总预警。"""

    model = ReplantingRecord
    label = "补植作业记录"
    code_field = "replanting_no"
    code_width = 3

    SORTABLE = {
        "replant_date": ReplantingRecord.replant_date,
        "review_due_date": ReplantingRecord.review_due_date,
        "reviewed_date": ReplantingRecord.reviewed_date,
        "quantity": ReplantingRecord.quantity,
        "created_at": ReplantingRecord.created_at,
    }

    @classmethod
    def code_prefix(cls):
        return daily_prefix("RP")

    # ------------------------------------------------------------ 状态表达式
    @staticmethod
    def reviewed_condition():
        """已复核：复核日期与成活数量均已登记。"""

        return and_(
            ReplantingRecord.reviewed_date.is_not(None),
            ReplantingRecord.survivor_quantity.is_not(None),
        )

    @classmethod
    def overdue_condition(cls):
        """逾期未核：尚未复核且约定复核日期已过。"""

        return and_(
            or_(
                ReplantingRecord.reviewed_date.is_(None),
                ReplantingRecord.survivor_quantity.is_(None),
            ),
            ReplantingRecord.review_due_date.is_not(None),
            ReplantingRecord.review_due_date < today(),
        )

    @classmethod
    def pending_condition(cls):
        """待复核：尚未复核，且未到约定复核日期（含未约定复核日期）。"""

        return and_(
            or_(
                ReplantingRecord.reviewed_date.is_(None),
                ReplantingRecord.survivor_quantity.is_(None),
            ),
            or_(
                ReplantingRecord.review_due_date.is_(None),
                ReplantingRecord.review_due_date >= today(),
            ),
        )

    @staticmethod
    def low_survival_condition():
        """已复核且成活率低于阈值：成活数 × 100 < 阈值 × 补植数。"""

        return and_(
            ReplantingRecord.reviewed_date.is_not(None),
            ReplantingRecord.survivor_quantity.is_not(None),
            ReplantingRecord.survivor_quantity * 100 < LOW_SURVIVAL_THRESHOLD * ReplantingRecord.quantity,
        )

    # ------------------------------------------------------------ 校验
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

        review_due = payload.get("review_due_date", instance.review_due_date)
        if review_due and replant_date and review_due < replant_date:
            raise ValidationError(
                "登记失败", details={"review_due_date": "约定复核日期不能早于补植日期"}
            )

        cls._validate_review_fields(instance, payload, replant_date=replant_date)

    @classmethod
    def _validate_review_fields(cls, instance, payload, *, replant_date=None):
        """复核字段联动：成活数量与复核日期必须同时存在，且不越界。"""

        errors = {}
        quantity = payload.get("quantity", instance.quantity)
        survivor = payload.get("survivor_quantity", instance.survivor_quantity)
        reviewed_date = payload.get("reviewed_date", instance.reviewed_date)
        replant_date = replant_date or instance.replant_date
        death_reason = payload.get("death_reason", instance.death_reason)

        if (survivor is not None) != (reviewed_date is not None):
            if survivor is None:
                errors["survivor_quantity"] = "已登记复核日期时必须填写成活数量"
            if reviewed_date is None:
                errors["reviewed_date"] = "登记成活数量时必须填写复核日期"

        if survivor is not None and reviewed_date is not None:
            if quantity is not None and survivor > quantity:
                errors["survivor_quantity"] = "成活数量不能大于补植数量"
            if replant_date and reviewed_date < replant_date:
                errors["reviewed_date"] = "复核日期不能早于补植日期"
            if reviewed_date > today():
                errors["reviewed_date"] = "复核日期不能晚于今天"
            if quantity is not None and survivor < quantity and not death_reason:
                errors["death_reason"] = "存在死亡苗木，请登记主要死亡原因"

        if errors:
            raise ValidationError("复核信息未通过校验", details=errors)

        # 全部成活时无需保留死亡原因；返回是否需要归一化
        return survivor is not None and quantity is not None and survivor >= quantity

    # ------------------------------------------------------------ 写入
    @classmethod
    def apply_derived(cls, instance):
        if instance.survivor_quantity is not None and instance.quantity is not None \
                and instance.survivor_quantity >= instance.quantity:
            instance.death_reason = None
            instance.death_remark = None

    @classmethod
    def register_review(cls, obj_id, payload):
        """约定复核期后登记成活数量与死亡原因。"""

        instance = cls.get(obj_id)
        merged = {
            "quantity": instance.quantity,
            "replant_date": instance.replant_date,
            **payload,
        }
        all_survived = cls._validate_review_fields(instance, merged)
        instance.reviewed_date = payload["reviewed_date"]
        instance.survivor_quantity = payload["survivor_quantity"]
        instance.death_reason = payload.get("death_reason")
        instance.death_remark = payload.get("death_remark")
        if all_survived:
            instance.death_reason = None
            instance.death_remark = None
        db.session.flush()
        db.session.commit()
        return instance

    # ------------------------------------------------------------ 查询
    @classmethod
    def _apply_filters(cls, query, filters):
        if filters.get("green_space_id"):
            query = query.filter(ReplantingRecord.green_space_id == filters["green_space_id"])
        if filters.get("maintenance_record_id"):
            query = query.filter(
                ReplantingRecord.maintenance_record_id == filters["maintenance_record_id"]
            )
        if filters.get("plant_category"):
            query = query.filter(ReplantingRecord.plant_category == filters["plant_category"])
        if filters.get("supplier"):
            query = query.filter(ReplantingRecord.supplier == filters["supplier"])
        if filters.get("batch_no"):
            query = query.filter(ReplantingRecord.batch_no == filters["batch_no"])
        if filters.get("date_from"):
            query = query.filter(ReplantingRecord.replant_date >= filters["date_from"])
        if filters.get("date_to"):
            query = query.filter(ReplantingRecord.replant_date <= filters["date_to"])

        status = filters.get("review_status")
        if status == "done":
            query = query.filter(cls.reviewed_condition())
        elif status == "overdue":
            query = query.filter(cls.overdue_condition())
        elif status == "pending":
            query = query.filter(cls.pending_condition())
        if filters.get("low_survival"):
            query = query.filter(cls.low_survival_condition())

        keyword = filters.get("keyword")
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    ReplantingRecord.replanting_no.like(like),
                    ReplantingRecord.plant_name.like(like),
                    ReplantingRecord.spec.like(like),
                    ReplantingRecord.supplier.like(like),
                    ReplantingRecord.batch_no.like(like),
                    ReplantingRecord.operator.like(like),
                )
            )
        return query

    @classmethod
    def list_records(cls, filters, args):
        query = cls._apply_filters(db.session.query(ReplantingRecord), filters)
        return query.order_by(
            parse_sort(args, cls.SORTABLE, ReplantingRecord.replant_date.desc())
        )

    @classmethod
    def detail(cls, obj_id):
        return cls.get(obj_id).to_dict(detail=True)

    # ------------------------------------------------------------ 汇总
    @classmethod
    def _aggregate_metrics(cls, extra_select, group_columns=None, filters=None):
        """按给定列分组（extra_select 中可含聚合列），返回复核与成活聚合。"""

        group_columns = group_columns or extra_select
        reviewed = cls.reviewed_condition()
        low = cls.low_survival_condition()
        query = cls._apply_filters(db.session.query(ReplantingRecord), filters or {})
        rows = (
            query.with_entities(
                *extra_select,
                func.count(ReplantingRecord.id),
                func.coalesce(func.sum(ReplantingRecord.quantity), 0),
                func.coalesce(func.sum(case((reviewed, 1), else_=0)), 0),
                func.coalesce(
                    func.sum(case((reviewed, ReplantingRecord.quantity), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(case((reviewed, ReplantingRecord.survivor_quantity), else_=0)), 0
                ),
                func.coalesce(func.sum(case((low, 1), else_=0)), 0),
            )
            .group_by(*group_columns)
            .all()
        )
        return rows

    @staticmethod
    def _metrics_row(count, quantity, reviewed_count, reviewed_quantity, survivor_quantity,
                     low_count):
        rate = (
            round(float(survivor_quantity) / float(reviewed_quantity) * 100, 1)
            if reviewed_quantity else None
        )
        return {
            "count": count or 0,
            "quantity": to_float(quantity) or 0,
            "reviewed_count": reviewed_count or 0,
            "reviewed_quantity": to_float(reviewed_quantity) or 0,
            "survivor_quantity": to_float(survivor_quantity) or 0,
            "death_quantity": to_float(reviewed_quantity - survivor_quantity) or 0,
            "survival_rate": rate,
            "low_survival": rate is not None and rate < LOW_SURVIVAL_THRESHOLD,
            "low_count": low_count or 0,
        }

    @classmethod
    def totals(cls, filters):
        """当前筛选条件下的复核与成活总量（不含供苗单位/批次分组）。"""

        filtered = cls._apply_filters(db.session.query(ReplantingRecord), filters)

        reviewed = cls.reviewed_condition()
        overdue = cls.overdue_condition()
        low = cls.low_survival_condition()
        totals = filtered.with_entities(
            func.count(ReplantingRecord.id),
            func.coalesce(func.sum(ReplantingRecord.quantity), 0),
            func.coalesce(func.sum(case((reviewed, 1), else_=0)), 0),
            func.coalesce(
                func.sum(case((reviewed, ReplantingRecord.quantity), else_=0)), 0
            ),
            func.coalesce(
                func.sum(case((reviewed, ReplantingRecord.survivor_quantity), else_=0)), 0
            ),
            func.coalesce(func.sum(case((overdue, 1), else_=0)), 0),
            func.coalesce(func.sum(case((low, 1), else_=0)), 0),
        ).one()

        (total_count, total_quantity, reviewed_count, reviewed_quantity,
         survivor_quantity, overdue_count, low_count) = totals
        pending_count = (total_count or 0) - (reviewed_count or 0) - (overdue_count or 0)
        return {
            "total_count": total_count or 0,
            "total_quantity": to_float(total_quantity) or 0,
            "reviewed_count": reviewed_count or 0,
            "pending_count": max(pending_count, 0),
            "overdue_count": overdue_count or 0,
            "reviewed_quantity": to_float(reviewed_quantity) or 0,
            "survivor_quantity": to_float(survivor_quantity) or 0,
            "death_quantity": to_float(reviewed_quantity - survivor_quantity) or 0,
            "survival_rate": (
                round(float(survivor_quantity) / float(reviewed_quantity) * 100, 1)
                if reviewed_quantity else None
            ),
            "low_survival_threshold": LOW_SURVIVAL_THRESHOLD,
            "low_survival_count": low_count or 0,
        }

    @classmethod
    def summary(cls, filters):
        """按供苗单位与供苗批次汇总成活率，偏低时打标记。"""

        result = cls.totals(filters)

        by_supplier = []
        for row in cls._aggregate_metrics(
            [func.coalesce(ReplantingRecord.supplier, "")], filters=filters
        ):
            supplier = row[0]
            metrics = cls._metrics_row(*row[1:])
            metrics.update({
                "supplier": supplier or None,
                "label": supplier or "未登记供苗单位",
            })
            by_supplier.append(metrics)
        by_supplier.sort(key=lambda item: item["quantity"], reverse=True)

        by_batch = []
        batch_group = func.coalesce(ReplantingRecord.batch_no, "")
        for row in cls._aggregate_metrics(
            [batch_group, func.max(func.coalesce(ReplantingRecord.supplier, ""))],
            [batch_group],
            filters=filters,
        ):
            batch_no, supplier = row[0], row[1]
            metrics = cls._metrics_row(*row[2:])
            metrics.update({
                "batch_no": batch_no or None,
                "label": batch_no or "未分批",
                "supplier": supplier or None,
            })
            by_batch.append(metrics)
        by_batch.sort(key=lambda item: (item["supplier"] or "", item["batch_no"] or ""))

        result["by_supplier"] = by_supplier
        result["by_batch"] = by_batch
        return result

    # ------------------------------------------------------------ 提醒
    @classmethod
    def due_for_review(cls, within_days=7, limit=10):
        """已到（或超过）约定复核日期且尚未复核的补植作业，供看板提醒。"""

        from datetime import timedelta

        deadline = today() + timedelta(days=max(within_days, 0))
        records = (
            db.session.query(ReplantingRecord)
            .filter(
                or_(
                    ReplantingRecord.reviewed_date.is_(None),
                    ReplantingRecord.survivor_quantity.is_(None),
                ),
                ReplantingRecord.review_due_date.is_not(None),
                ReplantingRecord.review_due_date <= deadline,
            )
            .order_by(ReplantingRecord.review_due_date.asc())
            .limit(limit)
            .all()
        )
        return records
