# RSS Watcher

리눅스 커널과 안드로이드 커널/보안 업데이트를 수집하는 소형 셀프호스팅 감시 서비스입니다.

## 현재 범위

현재 이 저장소에는 다음을 포함한 실행 가능한 MVP 골격이 들어 있습니다.

- FastAPI app
- APScheduler-based polling jobs
- source configuration loader
- SQLAlchemy models for collected items and poll runs
- scoring service for security candidates
- SMTP mailer interface
- example source configuration for kernel and Android sources

## 프로젝트 구조

```text
rss/
  app/
    api/
    collectors/
    core/
    db/
    mail/
    models/
    services/
  config/
  docs/
  tests/
```

## 로컬 실행

```bash
py -3.10 -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

앱은 기본적으로 SQLite로 시작하며, `config/sources.yaml` 파일이 있으면 그 파일을 읽고, 없으면 `config/sources.example.yaml`을 사용합니다.

Windows에서는 공식 CPython 3.10~3.13 또는 Docker 사용을 권장합니다. 현재 이 워크스페이스의 MSYS2 Python 3.14 환경은 일부 의존성 wheel이 없어 설치가 바로 되지 않을 수 있습니다.

## 주요 엔드포인트

- `GET /healthz`
- `GET /sources`
- `POST /poll/{source_id}`
- `GET /poll-runs/recent`
- `GET /items/recent`
- `GET /raw-events/recent`

## 권장 구현 순서

1. 첫 번째 실제 수집기인 `kernel_org_releases`를 구현합니다.
2. `lore_list`의 메시지 발견과 본문 수집을 구현합니다.
3. Android bulletin index 파싱을 구현합니다.
4. 중복 제거 로직과 digest 메일 템플릿을 더 정교하게 만듭니다.
5. mute/promote rule을 다룰 수 있는 관리용 API를 추가합니다.

## 배포

`docker-compose.yml`은 PostgreSQL 기반의 최소 시작 구성을 제공합니다.
