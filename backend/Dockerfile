FROM python:3.10-slim

WORKDIR /app

# Cài đặt các gói phụ thuộc cần thiết
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cổng mà API sẽ lắng nghe
EXPOSE 8000

# Tạo thư mục lưu biểu đồ
RUN mkdir -p /app/visualizations

# Lệnh để chạy ứng dụng khi container được khởi động
# Cài đặt thư viện khi khởi động và chạy ứng dụng
CMD bash -c "pip install --no-cache-dir -r requirements.txt && uvicorn api:app --host 0.0.0.0 --port 8000 --reload"
