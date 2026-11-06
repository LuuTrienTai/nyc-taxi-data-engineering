# Chốt Week 2 cho nhóm NYC Taxi

Chạy từ thư mục repo trên Mac/Linux. Ví dụ dùng một tháng `2025-01`. Nếu nhóm đã chốt tháng khác, đổi biến `MONTH` và dùng đúng tháng đó ở Airflow và SQL.

## 0. Lấy code và chuẩn bị môi trường

Nếu dùng Git và đang ở đúng bản code của ZIP gốc, tạo nhánh từ code đã merge và áp dụng patch đi kèm từ thư mục repo. Thay đường dẫn ví dụ bằng đường dẫn thực đến file patch.

```bash
git switch -c fix/week2-integration
git apply --check /path/to/week2.patch
git apply /path/to/week2.patch
git status --short
```

Thư mục `nyc_taxi_starter/` trong ZIP là bản chạy độc lập. Nếu mở riêng thư mục đó, bắt đầu ngay từ bước cài môi trường bên dưới.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-m2.txt -r requirements-m3.txt -r requirements-m3-week2.txt

test -f .env || cp .env.example .env
test -f dbt/profiles.yml || cp dbt/profiles.yml.example dbt/profiles.yml
```

Sửa `.env`. Giữ thông tin Postgres đang dùng nếu volume đã tồn tại. Thêm các biến Airflow từ `.env.example` nếu dùng `.env` cũ. Thay placeholder bằng giá trị local. Dùng mật khẩu Postgres chỉ gồm ký tự chữ và số cho cấu hình Airflow trong repo. Đặt `AIRFLOW_UID` thành giá trị của `id -u` để container có quyền ghi vào repo được mount. Có thể tạo chuỗi ngẫu nhiên cho `AIRFLOW_SECRET_KEY` bằng `python -c 'import secrets; print(secrets.token_hex(32))'`.

```bash
set -a
source .env
set +a
export POSTGRES_HOST=127.0.0.1
export MONTH=2025-01
```

## 1. M1 mở PostgreSQL và Metabase

```bash
docker compose config --quiet
docker compose up -d --wait postgres metabase
for sql in docker/postgres/init/*.sql; do
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$sql"
done
python scripts/m1_smoke_test.py
```

Hai file SQL có thể áp dụng lại cho volume có cấu trúc từ ZIP gốc. Bước này tạo staging, warehouse, marts và audit nếu còn thiếu, đồng thời bổ sung cột ghi mã Airflow run. Metabase mở tại http://localhost:3000 theo port mặc định.

## 2. M2 tải và kiểm tra dữ liệu

```bash
python -m src.ingestion.taxi --month "$MONTH"
python -m src.ingestion.weather --month "$MONTH"
python -m src.processing.validate --month "$MONTH"
python -m src.processing.verify_m2 --month "$MONTH"
```

Giữ log tổng số dòng taxi ở Bronze, Silver và Quarantine. Kiểm tra `Bronze = Silver + Quarantine` và Silver có dữ liệu. Các dòng lỗi có `quarantine_reason`. Khóa chuyến dựa trên tên file và vị trí vật lý của dòng. Các chuyến có thông tin giống nhau vẫn được giữ thành các dòng nguồn riêng. Việc chạy lại cùng file dùng lại khóa và thay dữ liệu tháng ở staging.

## 3. M3 nạp staging và dựng warehouse bằng dbt

```bash
python -m src.warehouse.load_staging --month "$MONTH"
dbt debug --project-dir dbt --profiles-dir dbt
dbt parse --project-dir dbt --profiles-dir dbt
dbt build --project-dir dbt --profiles-dir dbt
```

Đối chiếu số dòng taxi mà loader in ra với Silver của M2. `dbt debug` xác nhận kết nối. `dbt parse` kiểm tra các tham chiếu model. `dbt build` chạy SQL và các test. Xem [giải thích M3](M3_WEEK2.md) để đọc kết quả.

## 4. M4 xem staging và đối soát Gold

```bash
python -m src.processing.eda --month "$MONTH"
python -m src.processing.validate_marts --month "$MONTH"
```

Lưu kết quả cuối `staging = fact = Gold` có số chuyến và doanh thu. Script kiểm từng nhóm giờ, ngày, pickup zone. Doanh thu ở đây là tổng `total_amount` của các chuyến qua validation, theo định nghĩa của nhóm. Có thể dán truy vấn trong `dashboard_queries.sql` vào Metabase. Từ Metabase container, kết nối PostgreSQL qua host `postgres`, port `5432` và thông tin DB trong `.env`.

## 5. M1 trigger Airflow hai lần

```bash
docker compose -f compose.yaml -f compose.airflow.yaml --profile airflow config --quiet
docker compose -f compose.yaml -f compose.airflow.yaml --profile airflow up -d --build airflow-webserver airflow-scheduler
docker compose -f compose.yaml -f compose.airflow.yaml --profile airflow exec airflow-scheduler airflow dags list-import-errors
```

Mở http://localhost:8080, đăng nhập, bật DAG `nyc_taxi_monthly_pipeline` rồi Trigger với tháng `2025-01`. Chờ 6 task xanh. Mở log `verify_output` và giữ số chuyến/doanh thu. Trigger lại đúng tháng khi lần trước đã xong, so hai kết quả và kiểm tra audit.

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT data_period, status, rows_loaded, finished_at FROM audit.pipeline_runs ORDER BY finished_at DESC LIMIT 5"
```

Nếu DAG xanh nhưng audit chưa xuất hiện, xem log scheduler. Callback ghi audit có thể chạy sau khi Airflow cập nhật trạng thái trên UI.

## Bằng chứng để chốt

| Member | Bằng chứng |
|---|---|
| M1 | Smoke test pass, DAG import thành công và hai lần chạy cùng tháng đều xanh với KPI giống nhau |
| M2 | Log tải 3 nguồn, kiểm tra schema và tổng Bronze/Silver/Quarantine |
| M3 | Log loader trùng số dòng Silver, `dbt build` pass, fact có dữ liệu đúng tháng |
| M4 | Log EDA và đối soát từng nhóm ngày/giờ/zone, có số chuyến và doanh thu |

Phạm vi Week 2 là một tháng dữ liệu thật chạy được và đối soát được. Lịch tự động và dashboard hoàn chỉnh thuộc Week 3. Giờ phân tích demand theo giờ địa phương New York, còn thời tiết được ghép theo giờ UTC. Chuyến thiếu bản ghi khớp vẫn ở fact, với cột enrichment NULL. Dữ liệu thời tiết hiện tải theo tháng UTC, nên một số chuyến cuối tháng theo giờ New York có thể thiếu weather khi mới nạp riêng một tháng.
