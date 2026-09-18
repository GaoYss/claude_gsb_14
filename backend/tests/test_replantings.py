"""补植登记与成活复核接口测试。"""

from datetime import timedelta

from app.utils.dates import today


def replanting_payload(space_id, **overrides):
    payload = {
        "green_space_id": space_id,
        "plant_name": "红叶石楠",
        "plant_category": "shrub",
        "spec": "冠幅 80-100cm",
        "quantity": 100,
        "unit": "plant",
        "source": "nursery",
        "supplier": "萧山苗木合作社",
        "batch_no": "XS-2026-03",
        "replant_date": (today() - timedelta(days=10)).isoformat(),
        "review_deadline": (today() + timedelta(days=20)).isoformat(),
        "operator": "王海涛",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------- 登记
def test_create_replanting_generates_no_and_is_pending(api, make_space):
    space = make_space()
    data = api.data(api.post("/api/v1/replantings", replanting_payload(space.id)), 201)
    assert data["replant_no"].startswith("RP-")
    assert data["supplier"] == "萧山苗木合作社"
    assert data["batch_no"] == "XS-2026-03"
    assert data["source_label"] == "苗圃采购"
    assert data["quantity"] == 100.0
    assert data["survived_quantity"] is None
    assert data["dead_quantity"] is None
    assert data["survival_rate"] is None
    assert data["review_status"] == "pending"
    assert data["low_survival"] is False


def test_required_fields_are_validated(api, make_space):
    space = make_space()
    response = api.post("/api/v1/replantings", {
        "green_space_id": space.id,
        "plant_name": "红叶石楠",
        "plant_category": "shrub",
        "quantity": 100,
        "replant_date": today().isoformat(),
    })
    assert response.status_code == 422
    details = response.get_json()["data"]
    assert {"source", "supplier", "batch_no", "review_deadline"} <= set(details)


def test_review_deadline_cannot_precede_replant_date(api, make_space):
    space = make_space()
    response = api.post("/api/v1/replantings", replanting_payload(
        space.id,
        replant_date="2026-05-01",
        review_deadline="2026-04-20",
    ))
    assert response.status_code == 422
    assert "约定复核期" in response.get_json()["data"]["review_deadline"]


def test_record_must_belong_to_same_green_space(api, make_record, make_space):
    record = make_record()
    other_space = make_space(name="无关绿地")
    response = api.post("/api/v1/replantings",
                        replanting_payload(other_space.id, maintenance_record_id=record.id))
    assert response.status_code == 422
    assert "不属于所选绿地" in response.get_json()["data"]["maintenance_record_id"]


# ---------------------------------------------------------------- 成活复核
def test_register_review_computes_rate_and_dead_quantity(api, make_replanting):
    replanting = make_replanting(quantity=50)
    data = api.data(api.patch(f"/api/v1/replantings/{replanting.id}/review", {
        "survived_quantity": 46,
        "death_cause": "drought",
        "death_detail": "连续高温，定根水未浇透",
    }))
    assert data["review_status"] == "reviewed"
    assert data["survived_quantity"] == 46.0
    assert data["dead_quantity"] == 4.0
    assert data["survival_rate"] == 92.0
    assert data["low_survival"] is False
    assert data["death_cause_label"] == "干旱缺水"
    assert data["reviewed_date"] == today().isoformat()


def test_low_survival_is_flagged_below_threshold(api, make_replanting):
    replanting = make_replanting(quantity=100)
    data = api.data(api.patch(f"/api/v1/replantings/{replanting.id}/review", {
        "survived_quantity": 80,
        "death_cause": "plant_quality",
    }))
    assert data["survival_rate"] == 80.0
    assert data["low_survival"] is True

    # 恰好等于阈值 85% 不标记
    other = make_replanting(batch_no="B-2")
    data = api.data(api.patch(f"/api/v1/replantings/{other.id}/review", {
        "survived_quantity": 85,
        "death_cause": "weather",
    }))
    assert data["survival_rate"] == 85.0
    assert data["low_survival"] is False


def test_survived_quantity_cannot_exceed_total(api, make_replanting):
    replanting = make_replanting(quantity=50)
    response = api.patch(f"/api/v1/replantings/{replanting.id}/review", {
        "survived_quantity": 51,
    })
    assert response.status_code == 422
    assert "成活数量" in response.get_json()["data"]["survived_quantity"]


def test_death_cause_required_when_some_died(api, make_replanting):
    replanting = make_replanting(quantity=20)
    response = api.patch(f"/api/v1/replantings/{replanting.id}/review", {
        "survived_quantity": 18,
    })
    assert response.status_code == 422
    assert "死亡原因" in response.get_json()["data"]["death_cause"]

    # 全部成活时不要求死亡原因
    data = api.data(api.patch(f"/api/v1/replantings/{replanting.id}/review", {
        "survived_quantity": 20,
    }))
    assert data["survival_rate"] == 100.0
    assert data["death_cause"] is None


def test_review_can_be_reregistered(api, make_replanting):
    replanting = make_replanting(quantity=10)
    api.data(api.patch(f"/api/v1/replantings/{replanting.id}/review", {
        "survived_quantity": 7,
        "death_cause": "disease",
    }))
    data = api.data(api.patch(f"/api/v1/replantings/{replanting.id}/review", {
        "survived_quantity": 9,
        "death_cause": "disease",
        "death_detail": "复检后两株恢复成活",
    }))
    assert data["survived_quantity"] == 9.0
    assert data["dead_quantity"] == 1.0
    assert data["survival_rate"] == 90.0


def test_review_date_cannot_precede_replant_date(api, make_replanting):
    replanting = make_replanting(replant_date=today() - timedelta(days=5))
    response = api.patch(f"/api/v1/replantings/{replanting.id}/review", {
        "survived_quantity": 100,
        "reviewed_date": (today() - timedelta(days=30)).isoformat(),
    })
    assert response.status_code == 422
    assert "复核日期" in response.get_json()["data"]["reviewed_date"]


def test_overdue_status_after_deadline(api, make_replanting):
    replanting = make_replanting(review_deadline=today() - timedelta(days=1))
    data = api.data(api.get(f"/api/v1/replantings/{replanting.id}"))
    assert data["review_status"] == "overdue"


def test_quantity_cannot_be_lower_than_survived_after_review(api, make_replanting):
    replanting = make_replanting(quantity=100)
    api.data(api.patch(f"/api/v1/replantings/{replanting.id}/review", {
        "survived_quantity": 90,
        "death_cause": "drought",
    }))
    response = api.put(f"/api/v1/replantings/{replanting.id}",
                       replanting_payload(replanting.green_space_id, quantity=80))
    assert response.status_code == 422
    assert "成活数量" in response.get_json()["data"]["quantity"]


# ---------------------------------------------------------------- 列表与筛选
def test_list_filters_by_review_status(api, make_replanting):
    reviewed = make_replanting(batch_no="B-1", review_deadline=today() + timedelta(days=10))
    api.data(api.patch(f"/api/v1/replantings/{reviewed.id}/review", {
        "survived_quantity": 95,
        "death_cause": "trampling",
    }))
    make_replanting(batch_no="B-2", review_deadline=today() + timedelta(days=10))
    make_replanting(batch_no="B-3", review_deadline=today() - timedelta(days=2))

    data = api.data(api.get("/api/v1/replantings", review_status="reviewed"))
    assert data["meta"]["total"] == 1
    assert data["items"][0]["batch_no"] == "B-1"

    data = api.data(api.get("/api/v1/replantings", review_status="pending"))
    assert data["meta"]["total"] == 1
    assert data["items"][0]["batch_no"] == "B-2"

    data = api.data(api.get("/api/v1/replantings", review_status="overdue"))
    assert data["meta"]["total"] == 1
    assert data["items"][0]["batch_no"] == "B-3"


def test_list_filters_by_supplier_and_batch(api, make_replanting):
    make_replanting(supplier="萧山苗木合作社", batch_no="XS-01")
    make_replanting(supplier="临安绿源苗圃", batch_no="LA-01")

    data = api.data(api.get("/api/v1/replantings", supplier="临安"))
    assert data["meta"]["total"] == 1
    assert data["items"][0]["supplier"] == "临安绿源苗圃"

    data = api.data(api.get("/api/v1/replantings", batch_no="XS"))
    assert data["meta"]["total"] == 1


# ---------------------------------------------------------------- 汇总
def test_summary_groups_by_supplier_and_batch_with_low_flag(api, make_replanting):
    # 供苗单位甲：成活率 90%（达标）
    good = make_replanting(supplier="甲苗圃", batch_no="J-1", quantity=100)
    api.data(api.patch(f"/api/v1/replantings/{good.id}/review", {
        "survived_quantity": 90,
        "death_cause": "weather",
    }))
    # 供苗单位乙：成活率 70%（偏低），且还有一批未复核
    bad_1 = make_replanting(supplier="乙苗圃", batch_no="Y-1", quantity=100)
    api.data(api.patch(f"/api/v1/replantings/{bad_1.id}/review", {
        "survived_quantity": 70,
        "death_cause": "plant_quality",
    }))
    make_replanting(supplier="乙苗圃", batch_no="Y-2", quantity=40,
                    review_deadline=today() + timedelta(days=9))

    data = api.data(api.get("/api/v1/replantings/summary"))
    assert data["threshold"] == 85
    assert data["total_count"] == 3
    assert data["total_quantity"] == 240.0
    assert data["reviewed_count"] == 2
    assert data["pending_count"] == 1
    assert data["survived_quantity"] == 160.0
    assert data["dead_quantity"] == 40.0
    assert data["survival_rate"] == 80.0
    assert data["low_survival"] is True
    assert data["low_supplier_count"] == 1
    assert data["low_batch_count"] == 1

    suppliers = {item["supplier"]: item for item in data["by_supplier"]}
    assert suppliers["甲苗圃"]["survival_rate"] == 90.0
    assert suppliers["甲苗圃"]["low_survival"] is False
    assert suppliers["乙苗圃"]["survival_rate"] == 70.0
    assert suppliers["乙苗圃"]["low_survival"] is True
    # 未复核的 40 株不计入成活率分母，但计入待复核条数
    assert suppliers["乙苗圃"]["pending_count"] == 1
    assert suppliers["乙苗圃"]["reviewed_quantity"] == 100.0

    batches = {item["batch_no"]: item for item in data["by_batch"]}
    assert batches["Y-1"]["low_survival"] is True
    assert batches["J-1"]["survival_rate"] == 90.0
    # 未复核批次成活率为空，不应被标记偏低
    assert batches["Y-2"]["survival_rate"] is None
    assert batches["Y-2"]["low_survival"] is False

    # 成活率最低的供苗单位排在最前
    assert data["by_supplier"][0]["supplier"] == "乙苗圃"


def test_summary_survival_rate_only_counts_reviewed(api, make_replanting):
    reviewed = make_replanting(batch_no="B-1", quantity=10)
    api.data(api.patch(f"/api/v1/replantings/{reviewed.id}/review", {
        "survived_quantity": 10,
    }))
    make_replanting(batch_no="B-2", quantity=90)

    data = api.data(api.get("/api/v1/replantings/summary"))
    # 分母只含已复核的 10 株，成活率 100% 而非 10%
    assert data["reviewed_quantity"] == 10.0
    assert data["survival_rate"] == 100.0
    assert data["low_survival"] is False


def test_summary_filters_follow_query(api, make_replanting):
    first = make_replanting(supplier="丙苗圃", batch_no="C-1", quantity=10)
    api.data(api.patch(f"/api/v1/replantings/{first.id}/review", {
        "survived_quantity": 5,
        "death_cause": "disease",
    }))
    make_replanting(supplier="丁苗圃", batch_no="D-1", quantity=10)

    data = api.data(api.get("/api/v1/replantings/summary", supplier="丙"))
    assert data["total_count"] == 1
    assert len(data["by_supplier"]) == 1
    assert data["by_supplier"][0]["supplier"] == "丙苗圃"
    assert data["by_supplier"][0]["survival_rate"] == 50.0


def test_delete_replanting(api, make_replanting):
    replanting = make_replanting()
    api.data(api.delete(f"/api/v1/replantings/{replanting.id}"))
    assert api.get(f"/api/v1/replantings/{replanting.id}").status_code == 404


def test_seed_data_keeps_replanting_consistency(api, seeded):
    data = api.data(api.get("/api/v1/replantings/summary"))
    assert data["total_count"] == seeded["replanting"]
    assert data["reviewed_count"] + data["pending_count"] == data["total_count"]
    # 演示数据中至少有一批成活率被标记为偏低
    assert any(item["low_survival"] for item in data["by_batch"])
