"""补植作业成活跟踪接口测试。"""

from datetime import date, timedelta


def replanting_payload(space_id, **overrides):
    payload = {
        "green_space_id": space_id,
        "plant_name": "红叶石楠",
        "plant_category": "shrub",
        "spec": "冠幅 60-80cm",
        "quantity": 100,
        "unit": "plant",
        "batch_no": "P20260701-01",
        "supplier": "萧山苗木合作社",
        "replant_date": (date.today() - timedelta(days=40)).isoformat(),
        "review_due_date": (date.today() + timedelta(days=20)).isoformat(),
        "operator": "王海涛",
    }
    payload.update(overrides)
    return payload


# ------------------------------------------------------------ 登记与编号
def test_create_replanting_generates_code_and_pending_status(api, make_space):
    space = make_space()
    data = api.data(
        api.post("/api/v1/replanting-records", replanting_payload(space.id)), 201
    )
    assert data["replanting_no"].startswith("RP-")
    assert data["review_status"] == "pending"
    assert data["review_status_label"] == "待复核"
    assert data["survival_rate"] is None
    assert data["survivor_quantity"] is None
    assert data["death_quantity"] is None
    assert data["low_survival"] is False
    assert data["plant_category_label"] == "灌木"
    assert data["unit_label"] == "株"


def test_overdue_status_when_review_due_passed(api, make_space):
    space = make_space()
    payload = replanting_payload(
        space.id,
        replant_date=(date.today() - timedelta(days=40)).isoformat(),
        review_due_date=(date.today() - timedelta(days=1)).isoformat(),
    )
    data = api.data(api.post("/api/v1/replanting-records", payload), 201)
    assert data["review_status"] == "overdue"
    assert data["review_status_label"] == "逾期未核"


def test_review_due_before_replant_date_is_rejected(api, make_space):
    space = make_space()
    payload = replanting_payload(
        space.id,
        replant_date="2026-03-10",
        review_due_date="2026-03-01",
    )
    response = api.post("/api/v1/replanting-records", payload)
    assert response.status_code == 422
    assert "review_due_date" in response.get_json()["data"]


def test_quantity_and_category_validated(api, make_space):
    space = make_space()
    response = api.post(
        "/api/v1/replanting-records",
        replanting_payload(space.id, quantity=0, plant_category="bonsai"),
    )
    assert response.status_code == 422
    details = response.get_json()["data"]
    assert "quantity" in details and "plant_category" in details


def test_record_must_belong_to_same_green_space(api, make_record, make_space):
    record = make_record()
    other = make_space(name="无关绿地")
    response = api.post(
        "/api/v1/replanting-records",
        replanting_payload(other.id, maintenance_record_id=record.id),
    )
    assert response.status_code == 422
    assert "不属于所选绿地" in response.get_json()["data"]["maintenance_record_id"]


def test_create_with_review_fields_marks_done(api, make_space):
    space = make_space()
    payload = replanting_payload(
        space.id,
        replant_date=(date.today() - timedelta(days=40)).isoformat(),
        review_due_date=(date.today() - timedelta(days=10)).isoformat(),
        reviewed_date=(date.today() - timedelta(days=8)).isoformat(),
        survivor_quantity=92,
        death_reason="drought",
    )
    data = api.data(api.post("/api/v1/replanting-records", payload), 201)
    assert data["review_status"] == "done"
    assert data["survival_rate"] == 92.0
    assert data["death_quantity"] == 8.0
    assert data["low_survival"] is False
    assert data["death_reason_label"] == "干旱缺水"


# ------------------------------------------------------------ 复核登记
def test_register_review_computes_rate_and_flag(api, make_replanting):
    record = make_replanting(quantity=100)
    data = api.data(api.patch(f"/api/v1/replanting-records/{record.id}/review", {
        "reviewed_date": date.today().isoformat(),
        "survivor_quantity": 80,
        "death_reason": "waterlogging",
        "death_remark": "连续降雨导致树穴积水。",
    }))
    assert data["review_status"] == "done"
    assert data["survival_rate"] == 80.0
    assert data["death_quantity"] == 20.0
    assert data["low_survival"] is True
    assert data["low_survival_threshold"] == 85.0
    assert data["death_reason_label"] == "积水烂根"


def test_review_requires_death_reason_when_dead_seedlings(api, make_replanting):
    record = make_replanting(quantity=100)
    response = api.patch(f"/api/v1/replanting-records/{record.id}/review", {
        "reviewed_date": date.today().isoformat(),
        "survivor_quantity": 90,
    })
    assert response.status_code == 422
    assert "death_reason" in response.get_json()["data"]


def test_full_survival_does_not_require_death_reason(api, make_replanting):
    record = make_replanting(quantity=50)
    data = api.data(api.patch(f"/api/v1/replanting-records/{record.id}/review", {
        "reviewed_date": date.today().isoformat(),
        "survivor_quantity": 50,
    }))
    assert data["survival_rate"] == 100.0
    assert data["death_quantity"] == 0.0
    assert data["death_reason"] is None


def test_review_rejects_survivor_over_quantity_and_future_date(api, make_replanting):
    record = make_replanting(quantity=100)
    response = api.patch(f"/api/v1/replanting-records/{record.id}/review", {
        "reviewed_date": (date.today() + timedelta(days=1)).isoformat(),
        "survivor_quantity": 120,
    })
    assert response.status_code == 422
    details = response.get_json()["data"]
    assert "survivor_quantity" in details
    assert "reviewed_date" in details


def test_review_fields_must_come_together(api, make_space):
    space = make_space()
    payload = replanting_payload(
        space.id, survivor_quantity=90
    )  # 只填成活数量、不填复核日期
    response = api.post("/api/v1/replanting-records", payload)
    assert response.status_code == 422
    assert "reviewed_date" in response.get_json()["data"]


def test_review_not_found(api):
    assert api.patch("/api/v1/replanting-records/9999/review", {
        "reviewed_date": date.today().isoformat(),
        "survivor_quantity": 1,
    }).status_code == 404


# ------------------------------------------------------------ 更新与删除
def test_update_replanting(api, make_replanting):
    record = make_replanting()
    data = api.data(api.put(f"/api/v1/replanting-records/{record.id}", {
        "green_space_id": record.green_space_id,
        "plant_name": "金森女贞",
        "plant_category": "shrub",
        "quantity": 120,
        "unit": "plant",
        "supplier": "临安绿源苗圃",
        "replant_date": record.replant_date.isoformat(),
        "review_due_date": (date.today() + timedelta(days=15)).isoformat(),
    }))
    assert data["plant_name"] == "金森女贞"
    assert data["quantity"] == 120.0
    assert data["supplier"] == "临安绿源苗圃"
    assert data["review_status"] == "pending"


def test_delete_replanting(api, make_replanting):
    record = make_replanting()
    api.delete(f"/api/v1/replanting-records/{record.id}")
    assert api.get(f"/api/v1/replanting-records/{record.id}").status_code == 404


def test_deleting_maintenance_record_keeps_replanting(api, make_record, make_replanting):
    record = make_record()
    replanting = make_replanting(record=record)
    api.data(api.delete(f"/api/v1/maintenance-records/{record.id}"))
    data = api.data(api.get(f"/api/v1/replanting-records/{replanting.id}"))
    assert data["maintenance_record_id"] is None
    assert data["record"] is None


# ------------------------------------------------------------ 查询筛选
def test_list_filters_by_review_status(api, make_space, make_replanting):
    space = make_space()
    future = make_replanting(
        space=space,
        replant_date=date.today() - timedelta(days=10),
        review_due_date=date.today() + timedelta(days=20),
    )
    overdue = make_replanting(
        space=space,
        replant_date=date.today() - timedelta(days=40),
        review_due_date=date.today() - timedelta(days=10),
    )
    done = make_replanting(
        space=space,
        replant_date=date.today() - timedelta(days=40),
        review_due_date=date.today() - timedelta(days=10),
    )
    api.data(api.patch(f"/api/v1/replanting-records/{done.id}/review", {
        "reviewed_date": date.today().isoformat(),
        "survivor_quantity": 100,
    }))

    pending = api.data(api.get("/api/v1/replanting-records", review_status="pending"))
    assert pending["meta"]["total"] == 1
    assert pending["items"][0]["id"] == future.id

    overdue_rows = api.data(api.get("/api/v1/replanting-records", review_status="overdue"))
    assert overdue_rows["meta"]["total"] == 1
    assert overdue_rows["items"][0]["id"] == overdue.id

    done_rows = api.data(api.get("/api/v1/replanting-records", review_status="done"))
    assert done_rows["meta"]["total"] == 1
    assert done_rows["items"][0]["id"] == done.id


def test_list_filters_low_survival_and_supplier(api, make_replanting):
    low = make_replanting(supplier="余杭花卉基地", batch_no="B1", quantity=100)
    make_replanting(supplier="萧山苗木合作社", batch_no="B2", quantity=100)
    api.data(api.patch(f"/api/v1/replanting-records/{low.id}/review", {
        "reviewed_date": date.today().isoformat(),
        "survivor_quantity": 70,
        "death_reason": "poor_seedling",
    }))

    rows = api.data(api.get("/api/v1/replanting-records", low_survival="true"))
    assert rows["meta"]["total"] == 1
    assert rows["items"][0]["id"] == low.id

    by_supplier = api.data(api.get("/api/v1/replanting-records", supplier="余杭花卉基地"))
    assert by_supplier["meta"]["total"] == 1


# ------------------------------------------------------------ 汇总
def test_summary_groups_by_supplier_and_batch_with_low_flag(api, make_space, make_replanting):
    space = make_space()
    b1 = make_replanting(space=space, supplier="S1", batch_no="B1", quantity=100)
    b2 = make_replanting(space=space, supplier="S1", batch_no="B2", quantity=50)
    make_replanting(space=space, supplier="S2", batch_no="B3", quantity=200,
                    replant_date=date.today() - timedelta(days=5),
                    review_due_date=date.today() + timedelta(days=25))

    api.data(api.patch(f"/api/v1/replanting-records/{b1.id}/review", {
        "reviewed_date": date.today().isoformat(),
        "survivor_quantity": 70,
        "death_reason": "disease",
    }))
    api.data(api.patch(f"/api/v1/replanting-records/{b2.id}/review", {
        "reviewed_date": date.today().isoformat(),
        "survivor_quantity": 50,
    }))

    data = api.data(api.get("/api/v1/replanting-records/summary"))
    assert data["total_count"] == 3
    assert data["reviewed_count"] == 2
    assert data["pending_count"] == 1
    assert data["reviewed_quantity"] == 150.0
    assert data["survivor_quantity"] == 120.0
    assert data["death_quantity"] == 30.0
    assert data["survival_rate"] == 80.0
    assert data["low_survival_count"] == 1

    suppliers = {item["supplier"]: item for item in data["by_supplier"]}
    assert suppliers["S1"]["survival_rate"] == 80.0
    assert suppliers["S1"]["low_survival"] is True
    assert suppliers["S1"]["low_count"] == 1
    assert suppliers["S2"]["survival_rate"] is None
    assert suppliers["S2"]["low_survival"] is False

    batches = {item["batch_no"]: item for item in data["by_batch"]}
    assert batches["B1"]["survival_rate"] == 70.0
    assert batches["B1"]["low_survival"] is True
    assert batches["B1"]["supplier"] == "S1"
    assert batches["B2"]["survival_rate"] == 100.0
    assert batches["B3"]["reviewed_count"] == 0


def test_summary_respects_filters(api, make_replanting):
    make_replanting(supplier="甲苗圃", quantity=100)
    make_replanting(supplier="乙苗圃", quantity=100)
    data = api.data(api.get("/api/v1/replanting-records/summary", supplier="甲苗圃"))
    assert data["total_count"] == 1
    assert {item["supplier"] for item in data["by_supplier"]} == {"甲苗圃"}


def test_summary_handles_empty_dataset(api):
    data = api.data(api.get("/api/v1/replanting-records/summary"))
    assert data["total_count"] == 0
    assert data["survival_rate"] is None
    assert data["by_supplier"] == []
    assert data["by_batch"] == []


# ------------------------------------------------------------ 看板与字典
def test_dashboard_review_reminder_lists_overdue(api, make_replanting):
    overdue = make_replanting(
        replant_date=date.today() - timedelta(days=40),
        review_due_date=date.today() - timedelta(days=2),
    )
    make_replanting(
        replant_date=date.today() - timedelta(days=5),
        review_due_date=date.today() + timedelta(days=25),
    )
    data = api.data(api.get("/api/v1/statistics/dashboard"))
    ids = [item["id"] for item in data["replanting_reviews"]]
    assert overdue.id in ids

    reminders = api.data(api.get("/api/v1/statistics/reminders"))
    assert "replanting_reviews" in reminders


def test_meta_enums_include_replanting_groups(api):
    data = api.data(api.get("/api/v1/meta/enums"))
    groups = data["enums"]
    assert "replanting_death_reason" in groups
    assert "replanting_review_status" in groups
    death_values = {item["value"] for item in groups["replanting_death_reason"]}
    assert {"drought", "disease", "poor_seedling"} <= death_values


# ------------------------------------------------------------ 绿地级联
def test_green_space_delete_protection_counts_replanting(api, make_replanting):
    record = make_replanting()
    space_id = record.green_space_id
    response = api.delete(f"/api/v1/green-spaces/{space_id}")
    assert response.status_code == 409
    assert response.get_json()["data"]["replanting_record"] == 1

    api.data(api.delete(f"/api/v1/green-spaces/{space_id}", force="true"))
    assert api.get(f"/api/v1/replanting-records/{record.id}").status_code == 404


def test_green_space_profile_aggregates_replanting(api, make_space, make_replanting):
    space = make_space()
    record = make_replanting(space=space, quantity=100, supplier="S1", batch_no="B1")
    api.data(api.patch(f"/api/v1/replanting-records/{record.id}/review", {
        "reviewed_date": date.today().isoformat(),
        "survivor_quantity": 90,
        "death_reason": "trample",
    }))
    profile = api.data(api.get(f"/api/v1/green-spaces/{space.id}/profile"))
    stats = profile["statistics"]
    assert stats["replanting_count"] == 1
    assert stats["replanting_quantity"] == 100.0
    assert stats["replanting_reviewed_count"] == 1
    assert stats["replanting_survival_rate"] == 90.0
    assert profile["recent_replantings"][0]["replanting_no"] == record.replanting_no


# ------------------------------------------------------------ 演示数据
def test_seeded_data_flags_low_survival_supplier(api, seeded):
    data = api.data(api.get("/api/v1/replanting-records/summary"))
    assert data["total_count"] == seeded["replanting_record"]
    assert data["reviewed_count"] >= 1
    assert data["low_survival_count"] >= 1
    flagged = {item["supplier"] for item in data["by_supplier"] if item["low_survival"]}
    assert "余杭花卉基地" in flagged

    overdue_or_pending = data["pending_count"] + data["overdue_count"]
    assert overdue_or_pending >= 1
