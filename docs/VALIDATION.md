# Kiểm thử

| Kiểm tra | Kết quả trên fixture |
| --- | --- |
| Python | 14 test hiện có chạy qua, gồm schema, dữ liệu sai và biên DST của weather/Silver. |
| PostgreSQL | Nạp tháng 01–03/2025 vào ba partitions. Mỗi tháng từ 1.203 dòng tạo 1.200 facts và 3 bản ghi Quarantine. Tổng phí tháng 01 là 34.601,04 USD và khớp cả ba marts. |
| Chạy lại | Đổi batch size rồi chạy lại tháng 01. Count và doanh thu giữ nguyên. Trip trùng nằm ở batch khác vẫn bị phát hiện. |
| Rollback | Mô phỏng lỗi sau COPY đầu tiên. Audit ghi `failed`, fact/marts trước đó vẫn đối soát đúng. |
| Toàn bộ dòng invalid | Quarantine lưu 1.203 bản ghi và trạng thái run là `failed`. Gold cũ vẫn đối soát đúng. |
| Backup và restore | Dump PostgreSQL, khôi phục vào DB mới và xác nhận tháng 01 vẫn đối soát. |
| dbt | 3 views và 7 data tests chạy thành công. |
| Airflow | DAG được parse thành công, ba task chạy qua với `dag.test()` và PostgreSQL warehouse. |
| Web | API đọc được counts, mart và dimension. Kiểm tra tương tác lọc, chart, drill-down, Quarantine và phân trang trên DOM với API/PostgreSQL đang chạy. Dashboard role không có quyền xóa fact. |

Môi trường kiểm thử chạy PostgreSQL cục bộ và fixture. Docker Desktop, tải nguồn thật qua Internet và giao diện Chromium trực quan cần xác nhận ở máy chạy demo.

## Lặp lại các bước chính

Chạy trong project fixture đã nạp tháng 01 từ [hướng dẫn demo](DEMO_VI.md).

```bash
docker compose run --rm runner python -m pytest -q
docker compose run --rm runner dbt build --project-dir dbt --profiles-dir dbt
docker compose run --rm -e DATA_DIR=/opt/project/data/demo runner python -m src.pipeline --month 2025-01 --skip-download
docker compose run --rm runner python -m src.verify --month 2025-01
```

Để demo rollback, chạy lệnh đầu dưới đây. Lệnh đó phải kết thúc với lỗi mô phỏng. Lệnh verify kế tiếp vẫn phải PASS.

```bash
docker compose run --rm -e DATA_DIR=/opt/project/data/demo runner python -m src.pipeline --month 2025-01 --skip-download --fail-after-batch
docker compose run --rm runner python -m src.verify --month 2025-01
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < docs/demo_checks.sql
```

Chạy benchmark trên dữ liệu thật để xem PostgreSQL thực thi hai truy vấn tương đương. Thời gian phụ thuộc dữ liệu, máy và trạng thái cache.

```bash
docker compose run --rm runner python -m scripts.benchmark --month 2025-01
```
