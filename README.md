# NYC Taxi — Bronze → transient Silver → Gold

Bản hoàn thiện từ starter, bỏ hoàn toàn staging và Silver persistence.

- Bronze: taxi Parquet, zone CSV, weather JSON/Parquet trên disk.
- Silver: DataFrame theo batch 50.000 dòng trong RAM; không ghi file/bảng trung gian.
- Gold: PostgreSQL `gold.dim_zone`, `gold.dim_weather_hour`, `gold.fact_trip`, ba bảng aggregate.
- Audit: trạng thái run, SHA-256 của nguồn taxi, số dòng và lý do loại theo source row. Đây là metadata vận hành, không phải Silver.
- Dashboard tích hợp: http://localhost:8501. Metabase: http://localhost:3000.
- Airflow tùy chọn: http://localhost:8080; chạy theo tháng truyền vào.

**Đọc [hướng dẫn demo tiếng Việt](docs/DEMO_VI.md) trước khi chạy.**
Thiết kế chi tiết: [ARCHITECTURE.md](docs/ARCHITECTURE.md).
Kiểm thử thực tế và giới hạn: [VALIDATION.md](docs/VALIDATION.md).

## Khởi động nhanh với dữ liệu thật

Cần Docker Desktop đang chạy, khoảng 6–8 GB RAM cấp cho Docker khi bật cả Airflow/Metabase. Chạy từ thư mục chứa compose.yaml:

```bash
cp .env.example .env
docker compose build runner dashboard
docker compose up -d --wait postgres
docker compose run --rm runner python -m scripts.setup_services
docker compose run --rm runner python -m src.pipeline --month 2025-01
docker compose run --rm runner python -m src.verify --month 2025-01
docker compose up -d dashboard metabase
```

Không cần cài Python/dbt trên Mac cho đường chạy chính. Cổng PostgreSQL host mặc định 5433 tránh xung đột 5432 của dự án cũ. Giữ nguyên port trong container là 5432.

## Kiểm thử

```bash
docker compose run --rm runner python -m unittest discover -s tests -v
```

Demo offline và integration test dùng project riêng `nyc-taxi-demo` theo DEMO_VI.md, không chạy fixture lên database dữ liệu thật.

## Thay đổi so với starter

Thay config/validate/load_staging/DAG/dbt đang chồng chéo bằng một luồng nhất quán. Giữ ingestion TLC/Open-Meteo và mở rộng ngày cuối weather để đủ giờ New York. Không giữ venv macOS, .git, secrets hoặc log cũ trong ZIP. Không tự xóa database/volume cũ. Compose project mới `nyc-taxi-gold` tách khỏi bản starter. dbt bây giờ là lớp view/test trên Gold, không tạo staging; aggregate chính được commit cùng fact để tránh dashboard đọc dữ liệu nửa cập nhật.
