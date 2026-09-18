"""补植登记与成活复核校验规则。"""

from ..constants import DEATH_CAUSE, MEASURE_UNIT, PLANT_CATEGORY, PLANT_SOURCE
from .common import PayloadValidator


def validate_replanting(payload):
    return (
        PayloadValidator(payload)
        .integer("green_space_id", "所属绿地", required=True, min_value=1)
        .integer("maintenance_record_id", "关联养护记录", min_value=1)
        .string("plant_name", "植株名称", required=True, max_length=96)
        .enum("plant_category", "植物类别", group=PLANT_CATEGORY, required=True)
        .string("spec", "规格", max_length=64)
        .number("quantity", "补植数量", required=True, min_value=0.01, max_value=999999)
        .enum("unit", "计量单位", group=MEASURE_UNIT, default="plant")
        .enum("source", "苗木来源", group=PLANT_SOURCE, required=True)
        .string("supplier", "供苗单位", required=True, max_length=96)
        .string("batch_no", "苗木批次", required=True, max_length=64)
        .date("replant_date", "补植日期", required=True)
        .date("review_deadline", "约定复核期", required=True)
        .string("operator", "登记人", max_length=64)
        .text("remark", "备注", max_length=2000)
        .done()
    )


def validate_replant_review(payload):
    return (
        PayloadValidator(payload)
        .number("survived_quantity", "成活数量", required=True, min_value=0, max_value=999999)
        .date("reviewed_date", "复核日期")
        .enum("death_cause", "死亡原因", group=DEATH_CAUSE)
        .text("death_detail", "死亡情况说明", max_length=2000)
        .done()
    )
