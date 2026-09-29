#!/usr/bin/env bash
# Dừng thực thi ngay lập tức nếu có bất kỳ lệnh nào trả về mã lỗi
set -o errexit

echo "==> [1/4] Cài đặt dependencies..."
pip install -r requirements.txt

echo "==> [2/4] Thu gom static files..."
python manage.py collectstatic --no-input

echo "==> [3/4] Chạy Database Migrations..."
python manage.py migrate --no-input

echo "==> [4/4] Nạp dữ liệu mẫu ban đầu (Demo Seed Data)..."
python manage.py seed_real_data || true

echo "==> Quá trình Build hoàn tất thành công!"
