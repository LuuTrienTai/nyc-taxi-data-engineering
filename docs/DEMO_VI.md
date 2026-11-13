# Hướng dẫn chạy & demo

## 1. Chuẩn bị (Mac Apple Silicon / Windows Docker Desktop)

Giải nén vào thư mục mới, mở Terminal tại thư mục chứa `compose.yaml`. Không copy `.env`, venv hay dbt profile cũ. Bật Docker Desktop. Các lệnh dưới dùng bash/zsh; Windows dùng WSL hoặc Git Bash.

```bash
cp .env.example .env
docker compose build runner dashboard
docker compose up -d --wait postgres
docker compose run --rm runner python -m scripts.setup_services
```

`.env.example` chứa mật khẩu **local demo**, không dùng triển khai public. PostgreSQL host port 5433; các container dùng hostname postgres và port 5432.

## 2. Chạy dữ liệu thật

```bash
docker compose run --rm runner python -m src.pipeline --month 2025-01
docker compose run --rm runner python -m src.verify --month 2025-01
docker compose up -d dashboard metabase
```

Chờ pipeline kết thúc thành công. Mở http://localhost:8501, chọn tháng và Refresh. Có trip count, tổng phí, demand theo ngày, top zones, weather-demand. Lần đầu cần mạng tải Docker images, dependencies và dữ liệu. Sau khi Bronze đã có, chạy lại không cần tải nguồn:

```bash
docker compose run --rm runner python -m src.pipeline --month 2025-01 --skip-download
```

Mở rộng 3 tháng:

```bash
for month in 2025-02 2025-03; do
  docker compose run --rm runner python -m src.pipeline --month "$month"
  docker compose run --rm runner python -m src.verify --month "$month"
done
```

Nếu weather file cũ thiếu boundary hours, tải lại:

```bash
docker compose run --rm runner python -m src.ingestion.weather --month 2025-01 --force
```

## 3. Demo nhanh với dữ liệu giả lập, database riêng

Dừng project thật trước để tránh trùng port:

```bash
docker compose down
docker compose -p nyc-taxi-demo up -d --wait postgres
docker compose -p nyc-taxi-demo run --rm runner python -m scripts.setup_services
docker compose -p nyc-taxi-demo run --rm -e DATA_DIR=/opt/project/data/demo runner python -m scripts.demo_seed --month 2025-01
docker compose -p nyc-taxi-demo run --rm -e DATA_DIR=/opt/project/data/demo runner python -m src.pipeline --month 2025-01 --skip-download
docker compose -p nyc-taxi-demo run --rm runner python -m src.verify --month 2025-01
docker compose -p nyc-taxi-demo up -d dashboard
```

Kết quả mong đợi: **1.203 Bronze = 1.201 Gold + 2 rejected**. Đây là fixture synthetic, không trình bày như số liệu nghiên cứu NYC thật. Sau khi build images, demo fixture không cần gọi API nguồn.

Kiểm tra rerun + rollback tự động trên database demo:

```bash
docker compose -p nyc-taxi-demo run --rm -e DATA_DIR=/opt/project/data/demo runner python -m scripts.integration_check
```

Script chạy cùng tháng hai lần, đối chiếu counts/revenue, gây lỗi sau COPY, xác nhận Gold trước và sau lỗi không đổi.

## 4. Metabase

Mở http://localhost:3000, tạo tài khoản local lần đầu. Add database PostgreSQL:

| Trường | Giá trị |
|---|---|
| Display name | NYC Taxi Gold |
| Host | postgres |
| Port | 5432 |
| Database | nyc_taxi (hoặc POSTGRES_DB trong .env) |
| Username | metabase_reader |
| Password | METABASE_READER_PASSWORD trong .env |
| Schemas | gold |
| SSL | Tắt trong Docker local |

Dùng các SQL trong `docs/dashboard_queries.sql`, lưu từng Question và Add to Dashboard. Chọn line chart cho daily, bar chart cho zone, table cho weather. Dashboard tích hợp ở port 8501 đã sẵn sàng, không phụ thuộc thao tác cấu hình Metabase này.

## 5. Airflow (project dữ liệu thật)

Nếu đang dùng demo: `docker compose -p nyc-taxi-demo down`, rồi khởi động lại project thật. `setup_services` phải chạy trước để tạo airflow_meta.

```bash
docker compose up -d --wait postgres
docker compose run --rm runner python -m scripts.setup_services
docker compose -f compose.yaml -f compose.airflow.yaml --profile airflow build airflow-init
docker compose -f compose.yaml -f compose.airflow.yaml --profile airflow up -d airflow-webserver airflow-scheduler
```

Mở http://localhost:8080; tài khoản `.env`: admin / airflow_demo_2026 theo mặc định. Đợi init migrate xong, bật DAG `nyc_taxi_monthly_pipeline`, chọn Trigger DAG với month `2025-01`.

Ba task: `ingest_bronze` → `silver_in_memory_to_gold` → `verify_gold`. Silver và load phải cùng task vì Silver không persist. Xem Graph và Logs. DAG manual là chủ ý cho tháng TLC đã công bố; có retries, không tự đoán tháng mới có dữ liệu.

## 6. Flow thuyết trình 10–15 phút

| Thời gian | Thao tác | Điều cần nói / bằng chứng |
|---|---|---|
| 1 phút | Giới thiệu kiến trúc | Chỉ lưu Bronze và Gold; Silver trong RAM |
| 2 phút | Mở `data/bronze` và `silver.py` | Dữ liệu gốc + validation theo batch, không Silver files |
| 2 phút | Trigger DAG hoặc CLI pipeline | Ba task end-to-end; audit success |
| 2 phút | Mở dashboard 8501 | Demand/revenue/zone/weather, month filter |
| 2 phút | Rerun cùng tháng | Không tăng số dòng; nguồn được thay thế atomic |
| 2 phút | Demo integration_check trên fixture | Lỗi giữa COPY → rollback, Gold giữ nguyên |
| 2 phút | SQL kiểm tra + test report | Count reconciliation, reasons, schema không staging |

Không nên chờ download cả tháng trong buổi demo: tải trước, trình diễn rerun với Bronze cache. Chạy unit test:

```bash
docker compose run --rm runner python -m unittest discover -s tests -v
```

Mở psql để chạy queries trong `docs/demo_checks.sql`:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Nếu demo project riêng, thêm `-p nyc-taxi-demo` vào mọi lệnh compose.

## 7. dbt tùy chọn

Pipeline chính đã xây marts atomic; dbt dùng để tạo view trình bày và kiểm tra SQL. Không tạo staging, không đọc Silver file.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r dbt/requirements.txt
set -a
source .env
set +a
dbt build --project-dir dbt --profiles-dir dbt
```

## 8. Benchmark / backup / restore

```bash
docker compose run --rm runner python -m scripts.benchmark
mkdir -p backups
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/nyc_taxi.dump
```

Restore vào DB **mới**, không đè database đang demo:

```bash
docker compose exec postgres sh -c 'createdb -U "$POSTGRES_USER" taxi_restore_check'
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d taxi_restore_check --no-owner' < backups/nyc_taxi.dump
docker compose run --rm -e POSTGRES_DB=taxi_restore_check runner python -m src.verify --month 2025-01
```

Benchmark in execution time/buffers thật; không khẳng định tốc độ cải thiện trước khi đo. DB restore đã tồn tại thì dùng một tên mới.

## 9. Dừng sau demo

Nếu không bật Airflow:

```bash
docker compose down
```

Nếu đã bật Airflow:

```bash
docker compose -f compose.yaml -f compose.airflow.yaml --profile airflow down
```

Fixture demo: `docker compose -p nyc-taxi-demo down`.
Không thêm `-v` nếu muốn giữ dữ liệu. Bronze vẫn ở thư mục data, Gold ở named volume. Khi chạy lại chỉ cần up postgres/dashboard; không phải tải lại.

## 10. Lỗi thường gặp

- Port 5433/3000/8501/8080 bận: dừng project đang dùng port; hoặc đổi host port Compose. Không đổi port nội bộ postgres 5432.
- Docker daemon unavailable: bật Docker Desktop và chờ Ready.
- Dashboard 503: pipeline chưa chạy, setup_services chưa tạo reader, hoặc mật khẩu .env không khớp volume đã tạo.
- Đổi POSTGRES_PASSWORD sau lần init: volume giữ mật khẩu cũ. Dùng mật khẩu ban đầu hoặc ALTER ROLE có chủ đích; không xóa volume để thử.
- Airflow restart/error: xem `docker compose -f compose.yaml -f compose.airflow.yaml --profile airflow logs --tail=100 airflow-init airflow-scheduler`.
- Thiếu tài nguyên: chỉ bật postgres + dashboard, tắt Metabase/Airflow khi không cần.
- Volume cũ có staging: dự án mới có tên riêng; không nối vào DB starter cũ. Không tự DROP schema vì có thể chứa dữ liệu cần giữ.
