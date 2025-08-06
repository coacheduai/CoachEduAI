# CoachEduAI - Educational AI Platform

CoachEduAI là một nền tảng giáo dục AI tích hợp với các tính năng chatbot, cuộc thi, bài tập và xếp hạng thời gian thực.

## 🚀 Cách khởi động server

### Phương pháp 1: Sử dụng script tự động (Khuyến nghị)

#### Windows:
```bash
# Chạy file batch
start_server.bat
```

#### Linux/Mac:
```bash
# Cấp quyền thực thi
chmod +x run_server.py

# Chạy script
python run_server.py
```

### Phương pháp 2: Cài đặt thủ công

1. **Cài đặt Python 3.11+**
   ```bash
   # Kiểm tra phiên bản Python
   python --version
   ```

2. **Tạo môi trường ảo (khuyến nghị)**
   ```bash
   python -m venv python
   
   # Windows
   python\Scripts\activate
   
   # Linux/Mac
   source python/bin/activate
   ```

3. **Cài đặt dependencies**
   ```bash
   # Sử dụng pip
   pip install -r requirements.txt
   
   # Hoặc sử dụng poetry
   poetry install
   ```

4. **Khởi động server**
   ```bash
   python main.py
   ```

## 🌐 Truy cập ứng dụng

Sau khi khởi động thành công, mở trình duyệt và truy cập:
- **Local**: http://localhost:5000
- **Network**: http://[your-ip]:5000

## ⚙️ Cấu hình

### Biến môi trường

Bạn có thể tùy chỉnh cấu hình server bằng các biến môi trường:

```bash
# Port server (mặc định: 5000)
export PORT=8080

# Host (mặc định: 0.0.0.0)
export HOST=127.0.0.1

# Debug mode (mặc định: False)
export DEBUG=True
```

### Windows (PowerShell):
```powershell
$env:PORT = "8080"
$env:HOST = "127.0.0.1"
$env:DEBUG = "True"
python main.py
```

## 📁 Cấu trúc dự án

```
AI/
├── main.py              # File chính của ứng dụng
├── run_server.py        # Script khởi động server
├── requirements.txt     # Dependencies
├── pyproject.toml       # Cấu hình Poetry
├── .replit             # Cấu hình Replit
├── start_server.bat    # Script Windows
├── coachedual.db       # Database SQLite
├── static/             # CSS, JS, images
├── templates/          # HTML templates
└── python/             # Virtual environment
```

## 🔧 Tính năng chính

- ✅ **Đăng ký/Đăng nhập** với xác thực
- ✅ **Chatbot AI** với lịch sử chat
- ✅ **Cuộc thi** - tạo và tham gia
- ✅ **Bài tập** - tạo và giải bài tập
- ✅ **Nhóm học tập** - tạo và quản lý nhóm
- ✅ **Xếp hạng thời gian thực** với SocketIO
- ✅ **Hồ sơ người dùng** với avatar
- ✅ **Tìm kiếm** cuộc thi, bài tập, nhóm
- ✅ **Thông báo** và cập nhật real-time

## 🛠️ Troubleshooting

### Lỗi thường gặp:

1. **Port đã được sử dụng**
   ```bash
   # Thay đổi port
   export PORT=8080
   python main.py
   ```

2. **Thiếu dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Lỗi database**
   ```bash
   # Xóa file database cũ
   rm coachedual.db
   # Khởi động lại server
   python main.py
   ```

4. **Lỗi SocketIO**
   - Server sẽ tự động fallback về Flask thường
   - Kiểm tra console để xem thông báo lỗi

### Logs và Debug:

- Server sẽ hiển thị thông tin chi tiết khi khởi động
- Debug mode sẽ hiển thị lỗi chi tiết
- Kiểm tra console để xem logs

## 📞 Hỗ trợ

Nếu gặp vấn đề, hãy:
1. Kiểm tra logs trong console
2. Đảm bảo Python 3.11+ đã được cài đặt
3. Cài đặt lại dependencies: `pip install -r requirements.txt`
4. Xóa và tạo lại database nếu cần

## 🔄 Cập nhật

Để cập nhật server:
```bash
git pull
pip install -r requirements.txt
python main.py
``` 