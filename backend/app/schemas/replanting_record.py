"""补植作业记录校验规则。"""

from ..constants import (
    MEASURE_UNIT,
    PLANT_CATEGORY,
    REPLANTING_DEATH_REASON,
)
from .common import PayloadValidator


def validate_replanting(payload):
    """补植登记 / 编辑：苗木来源、数量、规格与约定复核期。

    复核字段（成活数量、死亡原因、复核日期）也允许出现在全量编辑中，
    字段间联动规则由 service 层统一校验。
    """

    return (
        PayloadValidator(payload)
        .integer("green_space_id", "所属绿地", required=True, min_value=1)
        .integer("maintenance_record_id", "关联养护记录", min_value=1)
        .string("plant_name", "苗木名称", required=True, max_length=96)
        .enum("plant_category", "植物类别", group=PLANT_CATEGORY, required=True)
        .string("spec", "规格", max_length=64)
        .number("quantity", "补植数量", required=True, min_value=0.01, max_value=999999)
        .enum("unit", "计量单位", group=MEASURE_UNIT, default="plant")
        .string("batch_no", "供苗批次", max_length=64)
        .string("supplier", "供苗单位", max_length=96)
        .date("replant_date", "补植日期", required=True)
        .date("review_due_date", "约定复核日期")
        .date("reviewed_date", "复核日期")
        .number("survivor_quantity", "成活数量", min_value=0, max_value=999999)
        .enum("death_reason", "主要死亡原因", group=REPLANTING_DEATH_REASON)
        .text("death_remark", "死亡情况说明", max_length=2000)
        .string("operator", "登记人", max_length=64)
        .text("remark", "备注", max_length=2000)
        .done()
    )


def validate_replanting_review(payload):
    """复核登记：只接收复核日期、成活数量与死亡原因。"""

    return (
        PayloadValidator(payload)
        .date("reviewed_date", "复核日期", required=True)
        .number("survivor_quantity", "成活数量", required=True, min_value=0, max_value=999999)
        .enum("death_reason", "主要死亡原因", group=REPLANTING_DEATH_REASON)
        .text("death_remark", "死亡情况说明", max_length=2000)
        .done()
    )
