# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Dung
- **Student ID**: [Your ID Here]
- **Date**: 2026-06-01
- **Team**: Team A2 — Minh, Đạt, Duy, Dũng

---

## I. Technical Contribution (15 Points)

### Overview
Tôi tham gia nhiều phần trong dự án: **UI/UX**, **web demo phần so sánh**, **đồng bộ branch và đẩy code lên main**, **xử lý xung đột merge**, và **soạn thảo báo cáo cá nhân**. Dựa trên lịch sử commit, tôi đã thực hiện các thay đổi dưới tác giả `QuocdungNe`, bao gồm cập nhật giao diện `web/styles.css`, đồng bộ nội dung `web/index.html`, giải quyết push protection rồi đẩy thành công lên `main`.

### Modules implemented / led

| Area | Files | What I did |
|:---|:---|:---|
| **Web UI** | `web/styles.css`, `web/index.html`, `web/app.js` | Cải thiện giao diện, làm mới theme, tối ưu trải nghiệm responsive, hiển thị rõ ràng các panel so sánh. |
| **Git integration / push** | repository | Quản lý branch, merge xung đột, đồng bộ với remote, xử lý push protection do secret trong `.env`, và đảm bảo các thay đổi được đẩy lên `main`. |
| **Demo layout** | `web/index.html` | Đảm bảo cấu trúc hiển thị 4 chế độ: Baseline, Tool-aware, Agent v1, Agent v2, đồng bộ với web demo. |
| **Documentation / report** | `report/individual_reports/REPORT_Dung.md` | Viết báo cáo cá nhân theo mẫu `REPORT_Minh.md`, tổng hợp commit và lịch sử đẩy code. |
| **Review & validation** | repository | Kiểm tra file, xác minh nội dung CSS/HTML và đảm bảo giao diện không gây lỗi UI trước khi commit. |

### Code Highlights
- **Giao diện UI/UX**: điều chỉnh màu sắc, bo góc, phân cấp typograpy, và tương phản giữa các vùng chứa dữ liệu để nội dung dễ đọc hơn.
- **Responsive**: layout lưới chuyển từ 4 cột xuống 2 cột hoặc 1 cột trên mobile.
- **CTA rõ ràng**: nút `Run comparison` được làm nổi bật bằng gradient và shadow.
- **Báo cáo Git**: sử dụng git log để xác định các commit liên quan và tổng hợp thành nội dung báo cáo.

### Documentation
- Trong bản demo, mỗi chế độ được thiết kế để so sánh trực quan giữa chatbot không công cụ và agent ReAct.
- Giao diện UI hỗ trợ việc đánh giá nhanh: trạng thái simulate/live, tham số query, trace logic, và cảnh báo thất bại.

---

## II. Debugging Case Study (10 Points)

### Problem Description
Trong quá trình push và merge, tôi gặp lỗi `GH013: Repository rule violations` do GitHub phát hiện secret GCP API Key trong file `.env`.

### Log Source
- Git output: `remote: error: GH013: Repository rule violations found for refs/heads/main.`
- Vị trí secret: `.env:5`.

### Diagnosis
Lỗi không phải do code logic của demo, mà do **quy tắc bảo mật GitHub**. File `.env` chứa giá trị `GEMINI_API_KEY` thực tế và bị secret scanning phát hiện.

### Solution
1. Thay giá trị thật bằng placeholder: `GEMINI_API_KEY=your_gemini_api_key_here`.
2. Commit lại thay đổi và cố gắng push lại.
3. Kiểm tra remote và pull trước khi push, vì branch local chưa đồng bộ với remote.

Kết quả: đã push thành công lên `main` sau khi sửa secret và đồng bộ với remote.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning
`Thought` block là một thành phần quan trọng để Agent đưa ra suy luận có cấu trúc. Đối với các truy vấn cần nhiều bước hoặc xác thực dữ liệu catalog, agent ReAct giúp giảm hallucination bằng cách thêm `Observation` thực tế sau mỗi hành động.

### 2. Reliability
- **Agent tốt hơn** khi câu hỏi yêu cầu tìm kiếm hoặc kiểm tra tồn kho, vì nó dựa vào công cụ để lấy dữ liệu.
- **Chatbot có thể tốt hơn** với câu hỏi đơn giản, chung chung, vì agent dễ bị overhead và gọi tool thừa.
- **Tool-aware chatbot** là dễ gây nhầm lẫn nhất vì nó chỉ giả lập `Observation` trong prompt mà không thực sự thực thi.

### 3. Observation
Feedback từ môi trường (`Observation`) giúp agent sửa đường đi theo thực tế thay vì dựa trên suy đoán. Khi tool trả về `No matching products found`, agent có thể mở rộng tìm kiếm hoặc thử hành động khác.

---

## IV. Future Improvements (5 Points)

- **Scalability**: chuyển `web/app.js` và backend sang kiến trúc API rõ ràng hơn, dùng cache và async khi gọi các công cụ.
- **Safety**: tách rõ `prompt` và `tool execution`; giới hạn các hành động hợp lệ trong Agent v2 để tránh hallucinated tool.
- **Performance**: lưu trữ kết quả tìm kiếm tạm thời, dùng SQLite index tốt hơn cho truy vấn sản phẩm.
- **Operations**: thêm file `.env.example` rõ ràng để tránh commit nhầm API key và bảo vệ secret tốt hơn.

---


