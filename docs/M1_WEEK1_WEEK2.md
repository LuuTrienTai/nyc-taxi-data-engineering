# M1 infrastructure và orchestration

Xem [checklist Week 2](WEEK2_CHECKPOINT.md) để cấu hình `.env`, khởi động PostgreSQL/Metabase, áp dụng SQL cho volume cũ và khởi động Airflow.

- Scheduler đọc DAG từ `/opt/project/airflow/dags`. Container dùng `postgres:5432` để kết nối PostgreSQL. Script chạy trên host dùng `127.0.0.1` và port đã publish.
- DAG nhận tham số `month` theo `YYYY-MM`. Hai task ingest có thể chạy song song. Sau đó chạy validation và kiểm tra Silver, load staging, dbt build, đối soát Gold.
- DAG chạy thủ công trong Week 2, giới hạn một run đang hoạt động. Mỗi task có một lần retry.
- Callback ghi trạng thái cuối và mã run vào `audit.pipeline_runs`. Số dòng taxi ghi cho run thành công lấy từ `audit.monthly_loads`.
- Khi chạy lại cùng tháng, giữ nguyên file Bronze để kiểm tra idempotency. So log `verify_output` của hai run.
