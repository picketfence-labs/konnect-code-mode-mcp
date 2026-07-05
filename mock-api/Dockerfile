# 世界主要都市の月平均気温モック API（FastAPI）
# ローカル/Minikube で「大量レコードを返す上流 API」として使う。
FROM python:3.12-slim

WORKDIR /app

# 依存だけ先にコピーしてレイヤキャッシュを効かせる
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体とデータ（cities.json / temperatures.json）
COPY server.py generate_data.py ./
COPY data/ ./data/

EXPOSE 8000

# 0.0.0.0 で待受（クラスタ内 Service から到達可能に）
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
