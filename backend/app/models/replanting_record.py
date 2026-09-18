"""补植作业成活跟踪模型。"""

from ..constants import (
    LOW_SURVIVAL_THRESHOLD,
    MEASURE_UNIT,
    PLANT_CATEGORY,
    REPLANTING_DEATH_REASON,
    REPLANTING_REVIEW_STATUS,
)
from ..extensions import db
from ..utils.dates import format_date, format_datetime, today
from ..utils.numbers import to_float
from .mixins import TimestampMixin, quantity_column


class ReplantingRecord(TimestampMixin, db.Model):
    """补植作业记录：登记苗木来源、数量与规格，复核期后跟踪成活情况。"""

    __tablename__ = "replanting_record"

    id = db.Column(db.Integer, primary_key=True)
    replanting_no = db.Column(db.String(32), nullable=False, unique=True, index=True)
    green_space_id = db.Column(
        db.Integer, db.ForeignKey("green_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    maintenance_record_id = db.Column(
        db.Integer,
        db.ForeignKey("maintenance_record.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    plant_name = db.Column(db.String(96), nullable=False, index=True)
    plant_category = db.Column(db.String(32), nullable=False, index=True)
    spec = db.Column(db.String(64))
    quantity = db.Column(quantity_column(), nullable=False, default=0)
    unit = db.Column(db.String(16), nullable=False, default="plant")
    batch_no = db.Column(db.String(64), index=True)
    supplier = db.Column(db.String(96), index=True)
    replant_date = db.Column(db.Date, nullable=False, index=True)
    review_due_date = db.Column(db.Date)
    # 复核期后回填
    reviewed_date = db.Column(db.Date)
    survivor_quantity = db.Column(quantity_column())
    death_reason = db.Column(db.String(32))
    death_remark = db.Column(db.Text)
    operator = db.Column(db.String(64))
    remark = db.Column(db.Text)

    green_space = db.relationship("GreenSpace", back_populates="replantings", lazy="joined")
    record = db.relationship("MaintenanceRecord", back_populates="replantings")

    # ------------------------------------------------------------ 派生状态
    @property
    def is_reviewed(self):
        return self.reviewed_date is not None and self.survivor_quantity is not None

    @property
    def death_quantity(self):
        """死亡数量 = 补植数量 − 成活数量。"""

        if not self.is_reviewed:
            return None
        return round(float(self.quantity or 0) - float(self.survivor_quantity or 0), 2)

    @property
    def survival_rate(self):
        """成活率（%），保留 1 位小数；未复核时为空。"""

        if not self.is_reviewed or not self.quantity:
            return None
        return round(float(self.survivor_quantity or 0) / float(self.quantity) * 100, 1)

    @property
    def is_low_survival(self):
        """成活率低于阈值时标记，供汇总与列表预警。"""

        rate = self.survival_rate
        return rate is not None and rate < LOW_SURVIVAL_THRESHOLD

    @property
    def review_status(self):
        """待复核 / 逾期未核 / 已复核。"""

        if self.is_reviewed:
            return "done"
        if self.review_due_date and self.review_due_date < today():
            return "overdue"
        return "pending"

    def to_dict(self, detail=False):
        data = {
            "id": self.id,
            "replanting_no": self.replanting_no,
            "green_space_id": self.green_space_id,
            "green_space": self.green_space.to_brief() if self.green_space else None,
            "maintenance_record_id": self.maintenance_record_id,
            "record": (
                {
                    "id": self.record.id,
                    "record_no": self.record.record_no,
                    "record_date": format_date(self.record.record_date),
                }
                if self.record
                else None
            ),
            "plant_name": self.plant_name,
            "plant_category": self.plant_category,
            "plant_category_label": PLANT_CATEGORY.label(self.plant_category),
            "spec": self.spec,
            "quantity": to_float(self.quantity),
            "unit": self.unit,
            "unit_label": MEASURE_UNIT.label(self.unit),
            "batch_no": self.batch_no,
            "supplier": self.supplier,
            "replant_date": format_date(self.replant_date),
            "review_due_date": format_date(self.review_due_date),
            "reviewed_date": format_date(self.reviewed_date),
            "survivor_quantity": to_float(self.survivor_quantity),
            "death_quantity": to_float(self.death_quantity),
            "death_reason": self.death_reason,
            "death_reason_label": (
                REPLANTING_DEATH_REASON.label(self.death_reason) if self.death_reason else None
            ),
            "survival_rate": self.survival_rate,
            "review_status": self.review_status,
            "review_status_label": REPLANTING_REVIEW_STATUS.label(self.review_status),
            "low_survival": self.is_low_survival,
            "low_survival_threshold": LOW_SURVIVAL_THRESHOLD,
            "operator": self.operator,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }
        if detail:
            data["death_remark"] = self.death_remark
            data["remark"] = self.remark
        return data
