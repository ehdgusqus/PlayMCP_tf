FROM python:3.11-slim

WORKDIR /app

# 필요한 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY main.py .

# 환경 변수는 배포 플랫폼(Cloud Run, Railway 등)에서 설정하는 것을 권장.
# 실행 (FastMCP는 uvicorn 기반으로 실행됨)
CMD ["python", "main.py"]