"""补植登记与成活复核模型。"""

from ..constants import (
    DEATH_CAUSE,
    LOW_SURVIVAL_THRESHOLD,
    MEASURE_UNIT,
    PLANT_CATEGORY,
    PLANT_SOURCE,
)
from ..extensions import db
from ..utils.dates import format_date, format_datetime, today
from ..utils.numbers import to_float
from .mixins import TimestampMixin, quantity_column


class Replanting(TimestampMixin, db.Model):
    """补植记录：登记苗木来源、数量与规格，约定复核期后登记成活情况。"""

    __tablename__ = "replanting"

    id = db.Column(db.Integer, primary_key=True)
    replant_no = db.Column(db.String(32), nullable=False, unique=True, index=True)
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
    source = db.Column(db.String(32), nullable=False, index=True)
    supplier = db.Column(db.String(96), nullable=False, index=True)
    batch_no = db.Column(db.String(64), nullable=False, index=True)
    replant_date = db.Column(db.Date, nullable=False, index=True)
    review_deadline = db.Column(db.Date, nullable=False, index=True)
    reviewed_date = db.Column(db.Date, index=True)
    survived_quantity = db.Column(quantity_column())
    death_cause = db.Column(db.String(32), index=True)
    death_detail = db.Column(db.Text)
    operator = db.Column(db.String(64))
    remark = db.Column(db.Text)

    green_space = db.relationship("GreenSpace", back_populates="replantings", lazy="joined")
    record = db.relationship("MaintenanceRecord", back_populates="replantings")

    # ------------------------------------------------------------ 派生属性
    @property
    def dead_quantity(self):
        """死亡数量 = 补植数量 - 成活数量，未复核时为空。"""

        if self.survived_quantity is None:
            return None
        return self.quantity - self.survived_quantity

    @property
    def survival_rate(self):
        """成活率（百分比，保留 1 位小数），未复核时为空。"""

        if self.survived_quantity is None or not self.quantity:
            return None
        return round(float(self.survived_quantity) / float(self.quantity) * 100, 1)

    @property
    def review_status(self):
        """复核状态：已复核 / 已逾期（超过约定复核期未登记）/ 待复核。"""

        if self.survived_quantity is not None:
            return "reviewed"
        if self.review_deadline and today() > self.review_deadline:
            return "overdue"
        return "pending"

    @property
    def low_survival(self):
        """成活率低于阈值（且已复核）时标记。"""

        rate = self.survival_rate
        return rate is not None and rate < LOW_SURVIVAL_THRESHOLD

    def to_dict(self, detail=False):
        data = {
            "id": self.id,
            "replant_no": self.replant_no,
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
            "source": self.source,
            "source_label": PLANT_SOURCE.label(self.source),
            "supplier": self.supplier,
            "batch_no": self.batch_no,
            "replant_date": format_date(self.replant_date),
            "review_deadline": format_date(self.review_deadline),
            "reviewed_date": format_date(self.reviewed_date),
            "survived_quantity": to_float(self.survived_quantity),
            "dead_quantity": to_float(self.dead_quantity),
            "survival_rate": self.survival_rate,
            "review_status": self.review_status,
            "low_survival": self.low_survival,
            "death_cause": self.death_cause,
            "death_cause_label": DEATH_CAUSE.label(self.death_cause) if self.death_cause else None,
            "operator": self.operator,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }
        if detail:
            data["death_detail"] = self.death_detail
            data["remark"] = self.remark
        return data
