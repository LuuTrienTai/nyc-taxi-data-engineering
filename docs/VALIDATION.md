# Báo cáo kiểm thử — 2026-11-13

## Đã thực thi thành công

| Kiểm tra | Kết quả |
|---|---|
| Python unit tests | 13/13 PASS |
| Silver rules | Timestamp, lệch tháng, distance, infinity, zone, optional NULL |
| Identity | Giữ hai source rows có cùng thuộc tính |
| Timezone | Spring nonexistent hour bị loại; fall overlap được flag |
| Weather coverage | January 744 local hours; March 743; November 720 unique local hours, overlap observations=2 |
| Zone lookup | Bảo toàn tên `NA` và service zone `N/A`, không đọc nhầm thành NULL |
| PostgreSQL 16.2 standalone | Schema, PK/FK, 1201 facts, SQL của cả ba marts PASS |
| Đối chiếu fixture | 1203 Bronze = 1201 valid + 2 rejected; revenue = 19216 USD |
| SQL transaction | DELETE trong transaction rồi ROLLBACK giữ 1201 facts |
| dbt parse | PASS với core 1.11.17 / postgres adapter 1.9.0 |
| Python compile / YAML / JS syntax | PASS |

Unit tests chạy với pandas 2.2.3, pyarrow 19.0.1, psycopg 3.2.6, Python 3.12. Runtime Docker mục tiêu Python 3.11.

## Chưa thể xác nhận trong môi trường này

- Không có Docker daemon; không chạy container stack, Metabase hoặc Airflow UI.
- Môi trường không cho tạo socket; PostgreSQL chạy được **standalone backend**, không mở server. Vì vậy chưa chạy end-to-end qua psycopg/COPY, advisory lock/concurrent readers, hay HTTP dashboard.
- Test rollback đã thực thi là SQL transaction trên PostgreSQL thật; script `integration_check.py` cho đường Python/COPY được cung cấp để chạy trên máy có Docker, chưa được tính là PASS ở đây.
- Chưa tải và xử lý full một tháng TLC/Open-Meteo; chưa benchmark hiệu năng dữ liệu thật.
- Backup/restore và quyền read-only có script/hướng dẫn, cần chạy xác nhận trên stack Docker.
- Dashboard đã kiểm tra cú pháp JavaScript, chưa render screenshot hay test trình duyệt.

Không coi bảng trên là chứng nhận production hoặc khẳng định mọi service đã chạy thành công.

## Chạy lại

```bash
python -m unittest discover -s tests -v
```

Kiểm tra SQL standalone (tùy chọn cho Linux, không cần cho Docker demo):

```bash
pip install pgserver==0.1.4
python -m scripts.sql_standalone_check
```

Script tạo fixture và database tạm, chạy đúng các câu SQL aggregate lấy từ pipeline, rồi kiểm tra count/revenue và rollback. Không mô phỏng kết nối psycopg.

Bước chấp nhận trước buổi demo: chạy `scripts.integration_check` trên project demo, chạy một tháng dữ liệu thật với `src.verify`, mở dashboard, trigger DAG rồi xem ba task xanh. Xem đầy đủ lệnh trong DEMO_VI.md.

## Giới hạn vận hành

Thiết kế dành cho demo môn học trên máy local. Audit run có thể còn `running` nếu process bị kill cưỡng bức; đối chiếu Airflow logs để xác định run bị gián đoạn. Không chạy `--force` đồng thời với pipeline khác trên cùng Bronze. Nguồn Bronze là cache cập nhật có chủ đích, chưa có lịch sử nhiều phiên bản object store. Mật khẩu mặc định chỉ dùng local, Metabase H2 chỉ phục vụ demo. Không có SLA dữ liệu/thời gian xử lý được đo trên máy người dùng.
