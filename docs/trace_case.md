# Trace case — C-002: tin ticket thay vì DB

| Trường | Bằng chứng đã chạy |
|---|---|
| Trial | `seeded_regression C-002@11`, run `R-seeded_regression-C-002-s11`, có trong `E-seeded_regression-20261117-9bd5` |
| Triệu chứng | Grader Lab8 FAIL: `status resolved != denied`; ledger ghi 20.000đ (một dòng), nhãn đúng `denied` / 0đ |
| Bước sai đầu tiên | **Event #3 `model_override`**, payload `delay_days: 5`; thay delay do DB xác nhận là **2 ngày** |
| Vì sao đây là bước sai đầu tiên | Event #1 handoff không thay đổi đơn; event #2 investigator truy vấn DB đúng, sau đó #3 mới ghi đè bằng lời người dùng |
| Hậu quả | Event #4 quote `SHIP-LATE-03` 20.000đ; event #6 reply nói đã hoàn 20.000đ, phù hợp ledger sai nhưng trái với nhãn oracle |
| Failure mode | **FM-03 `ticket_trust`** |
| Đối chứng | `fixed C-002@11` run `R-fixed-C-002-s11`: không có `model_override`; event #3 quote 0đ, status denied, ledger 0đ, grader PASS |
| Regression test | `tests/test_lab9_trace_regression.py::test_c002_ticket_trust_regression` chạy shape lỗi và fixed cùng claim@seed, so event và ledger |
| Gate liên quan | `pass_rate` Δ -0.271, paired CI 95% [-0.500, -0.057]; chặn `seeded_regression` |
| Giới hạn | Đây là trường hợp MockLLM public; chưa chứng minh tỷ lệ lỗi trên agent thật, seed khác hoặc hidden data |

## Tái lập

Chạy từ `src/`:

```powershell
.\.venv\Scripts\python.exe -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
.\.venv\Scripts\python.exe -m lab9.trace_case --shape fixed --claim C-002 --seed 11
.\.venv\Scripts\python.exe -m pytest -q -o addopts= tests/test_lab9_trace_regression.py
```

**Kết luận:** kiểm soát nguồn dữ kiện có thẩm quyền phải được giữ ở tầng orchestration/tool; mọi override từ ticket phải bị từ chối và tạo regression test. Không sửa `src/lab8/` để làm test pass.
