# Chạy và demo

## 1. Dữ liệu thật

Mở Docker Desktop. Trên MacBook 16 GB, có thể cấp khoảng 6–8 GB cho Docker nếu chạy đồng thời Airflow. Trước tiên chạy lệnh chuẩn bị và tháng đầu trong README, sau đó bổ sung hai tháng còn lại.

```bash
for month in 2025-02 2025-03; do
  docker compose run --rm runner python -m src.pipeline --month "$month" || break
  docker compose run --rm runner python -m src.verify --month "$month" || break
done
```

- `--skip-download` phát lại tháng đã có đủ Bronze. Dùng `--force` cho lần tải lại có chủ ý.
- Nếu tải lỗi, xem retry trong terminal, kiểm tra kết nối tới TLC CDN và Open-Meteo rồi chạy lại. Dùng fixture bên dưới để demo khi thiếu Internet.
- Dùng `docker compose ps -a` và `docker compose logs setup dashboard` để tìm lỗi khởi động. Nếu web chạy nhưng không thấy tháng mới, tải lại trang.

## 2. Fixture offline có đủ trường hợp để demo

Dùng Terminal riêng. Các biến export dưới đây giúp chạy song song với project thật. Docker cần tải dependencies ở lần build đầu.

```bash
export COMPOSE_PROJECT_NAME=nyc-taxi-fixture
export WEB_PORT=8502
docker compose up -d --build dashboard

docker compose run --rm -e DATA_DIR=/opt/project/data/demo runner python -m scripts.demo_seed --month 2025-01
docker compose run --rm -e DATA_DIR=/opt/project/data/demo runner python -m src.pipeline --month 2025-01 --skip-download
docker compose run --rm runner python -m src.verify --month 2025-01
```

Mở [dashboard demo](http://localhost:8502). Kỳ vọng **1.203 Bronze → 1.200 Gold + 3 Quarantine**. Ba lý do là trùng trip ID, khoảng cách âm và location ID lạ. Để demo đổi tháng, chạy lại hai lệnh seed và pipeline cho tháng khác. Cơ sở dữ liệu đã có run thật thành công sẽ từ chối nạp fixture và ngược lại.

## 3. Airflow

Chạy từ Terminal của project mong muốn. Với fixture, seed Bronze trước và đặt `export AIRFLOW_DATA_DIR=/opt/project/data/demo AIRFLOW_PORT=8081` trong Terminal riêng chứa các biến ở mục 2.

```bash
docker compose -f compose.yaml -f compose.airflow.yaml --profile airflow up -d --build
```

Mở [Airflow thật](http://localhost:8080) hoặc [Airflow fixture](http://localhost:8081), đăng nhập theo `.env`. Trong DAG **nyc_taxi_monthly_pipeline**, dùng **Trigger DAG** và nhập month **2025-01**. Đối với fixture hoặc một lần replay, bật **replay_bronze**. Với Airflow thật, unpause DAG để scheduler chạy theo lịch.

| Task | Show gì |
| --- | --- |
| `ingest_bronze` | Task log tải hoặc dùng cache của ba nguồn. Nếu replay, task dùng Bronze sẵn có. |
| `silver_transform_and_load_gold` | Log có `run_id`, số dòng Bronze, Gold và Quarantine. Silver và COPY chạy chung task, theo batch RAM. |
| `verify_gold` | Count và doanh thu được đối soát với tất cả marts. Task fail nếu dữ liệu không khớp. |

Lịch thật mặc định là ngày 15 mỗi tháng lúc 06:00 New York. `TAXI_MONTH_LAG=3` chọn tháng trước mốc chạy ba tháng để có dư thời gian công bố dữ liệu. Đây là giả định vận hành có thể chỉnh. Dùng trigger tháng cụ thể nếu cần bù tháng hoặc nguồn chưa công bố. Fixture dùng trigger tay. Đặt mật khẩu `AIRFLOW_DB_PASSWORD` bằng ký tự an toàn cho URL như chữ, số hoặc dấu gạch dưới vì Compose đưa giá trị vào chuỗi kết nối.

## 4. Flow trình bày

1. **Pipeline explorer → Bronze.** Chọn tháng và run, mở tên file, số dòng, checksum và một mẫu raw.
2. **Silver.** Mở cùng source row trước và sau xử lý. Chỉ ra `trip_id`, `duration_minutes`, zone pickup/drop-off, calendar date và thời tiết khớp giờ.
3. **Quarantine.** Lọc `duplicate_trip_id` để chỉ ra vì sao loại chuyến trùng. Mở lại `unknown_zone` hoặc `invalid_trip_distance` để show dữ liệu lỗi.
4. **Gold → Gold warehouse.** Đọc phép đối soát số dòng. Mở `fact_trip`, đổi sang `dim_date` rồi `dim_weather`, cuối cùng mở ba marts. Hai role pickup và drop-off dùng chung `dim_zone`.
5. **Analytics.** Chọn Pickup hoặc Drop-off, lọc borough/zone và khoảng ngày. Chuyển Trips sang Revenue rồi chọn Day, Hour of day hoặc Weekday vs weekend. Xem bảng Trips/hour theo dải nhiệt độ và mưa, đổi filter thời tiết, kiểm tra KPI thời lượng và chạy Calculate trong **Fare by trip distance**.
6. **dbt.** Chạy `dbt build` như README. Có thể chạy lệnh benchmark trong VALIDATION để xem khác biệt giữa quét fact và đọc mart.

## 5. Dùng Bronze từ bản cũ

Bản mới tạo Compose project riêng. Dừng container cũ nếu chúng giữ cổng 8501 hoặc 8080, hoặc đổi các cổng web trong `.env`. PostgreSQL không bind cổng lên máy host. Schema fact đã đổi khóa và cách phân vùng. Để giữ kết quả nhất quán, tạo Gold bản mới bằng cách phát lại file nguồn từ Bronze cũ.

Nếu thư mục cũ có `data/bronze`, thay đường dẫn dưới đây bằng đường dẫn thực rồi chạy từ thư mục dự án mới sau khi đã khởi động dashboard.

```bash
tar -C /duong-dan/project-cu/data -cf - bronze |
  docker compose run --rm -T runner tar --no-same-owner --no-same-permissions -C /opt/project/data -xf -
docker compose run --rm runner python -m src.pipeline --month 2025-01 --skip-download
docker compose run --rm runner python -m src.verify --month 2025-01
```

## 6. Backup và khôi phục

Dump dưới đây sao lưu warehouse, audit và quarantine của DB đang chạy. Sao lưu Bronze riêng nếu cần replay hoặc đối chiếu các raw file. Thư mục `backups` chứa dữ liệu thật nên giữ cục bộ.

```bash
mkdir -p backups
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > backups/nyc_taxi.dump
docker compose run --rm -T runner tar -C /opt/project/data -cf - bronze > backups/bronze.tar
```

Khôi phục thử vào database mới `nyc_taxi_recovery` trên cùng PostgreSQL. Lệnh verify dùng tạm DB vừa khôi phục. Để phục vụ DB này, đặt `POSTGRES_DB=nyc_taxi_recovery` trong `.env`, chạy lại `docker compose up -d --build dashboard` để setup cấp quyền cho dashboard.

```bash
docker compose exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" nyc_taxi_recovery'
docker compose exec -T postgres sh -c 'pg_restore --exit-on-error --no-owner --no-acl -U "$POSTGRES_USER" -d nyc_taxi_recovery' < backups/nyc_taxi.dump
docker compose run --rm -e POSTGRES_DB=nyc_taxi_recovery runner python -m src.verify --month 2025-01
```

## 7. Dừng demo

```bash
# Khi chạy dashboard / CLI
docker compose down

# Khi đã bật Airflow
docker compose -f compose.yaml -f compose.airflow.yaml --profile airflow down
```

Chạy lệnh dừng trong đúng Terminal của project thật hoặc fixture. Cả hai lệnh giữ volumes dữ liệu.

## Cập nhật từ gói trước

Giữ nguyên PostgreSQL volume. Sau khi giải nén bản mới vào thư mục project, build lại dashboard rồi chạy lại pipeline cho từng tháng đang dùng. Lệnh nạp tạo cột thời lượng mới trong mart và tính lại dữ liệu tháng.

```bash
docker compose up -d --build dashboard
docker compose run --rm runner python -m src.pipeline --month 2025-01 --skip-download
docker compose run --rm runner python -m src.verify --month 2025-01
```

Lặp lại hai lệnh cuối với các tháng còn lại. Tải lại dashboard bằng Cmd + Shift + R.
