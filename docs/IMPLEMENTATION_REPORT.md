# 구현 보고서

## 1. 목적

리눅스 커널과 안드로이드 커널/보안 소식을 서버에서 주기적으로 수집하고,
분류한 뒤 메일로 보내는 감시 서비스를 실제 동작하는 수준까지 구현했다.

이번 구현의 목표는 다음 4가지였다.

1. 공식 소스에서 실제 데이터를 가져온다.
2. 수집 결과를 DB에 저장한다.
3. 위험도에 따라 분류한다.
4. 운영자가 API로 상태를 확인하고 수동 poll을 실행할 수 있게 한다.

## 2. 이번에 실제 구현한 범위

### 수집기

- `kernel.org` 릴리즈 JSON 수집
- `lore.kernel.org` Atom 수집
  - `linux-cve-announce`
  - `stable`
  - 같은 어댑터로 `lkml`도 확장 가능
- Android Security Bulletin overview 및 월별 bulletin 수집
- Android common kernel Gitiles 로그 수집

### 저장

- 정규화된 아이템 저장
- raw ingest 이벤트 저장
- poll 실행 이력 저장
- 메일 발송 이력 저장

### 분류

- `confirmed_security`
- `security_candidate_high`
- `security_candidate_medium`
- `general_patch`
- `release_only`

### API

- `GET /healthz`
- `GET /sources`
- `POST /poll/{source_id}`
- `GET /poll-runs/recent`
- `GET /items/recent`
- `GET /raw-events/recent`

## 3. 핵심 구현 파일

- 앱 진입점: [app/main.py](C:/Users/RYZEN1/Desktop/rss/app/main.py)
- API 라우트: [app/api/routes.py](C:/Users/RYZEN1/Desktop/rss/app/api/routes.py)
- 수집기 레지스트리: [app/collectors/registry.py](C:/Users/RYZEN1/Desktop/rss/app/collectors/registry.py)
- kernel.org 수집기: [app/collectors/kernel_org.py](C:/Users/RYZEN1/Desktop/rss/app/collectors/kernel_org.py)
- lore 수집기: [app/collectors/lore.py](C:/Users/RYZEN1/Desktop/rss/app/collectors/lore.py)
- Android/Gitiles 수집기: [app/collectors/android.py](C:/Users/RYZEN1/Desktop/rss/app/collectors/android.py)
- 공통 파싱 유틸: [app/collectors/utils.py](C:/Users/RYZEN1/Desktop/rss/app/collectors/utils.py)
- 분류 서비스: [app/services/classifier.py](C:/Users/RYZEN1/Desktop/rss/app/services/classifier.py)
- 수집/저장 서비스: [app/services/collector.py](C:/Users/RYZEN1/Desktop/rss/app/services/collector.py)
- digest 서비스: [app/services/digest.py](C:/Users/RYZEN1/Desktop/rss/app/services/digest.py)
- DB 모델: [app/db/models.py](C:/Users/RYZEN1/Desktop/rss/app/db/models.py)
- 소스 설정: [config/sources.example.yaml](C:/Users/RYZEN1/Desktop/rss/config/sources.example.yaml)

## 4. 어떻게 만들었는가

### 4.1 수집 방식

소스별로 어댑터를 분리했다.

- `kernel_org_releases`
  - `https://www.kernel.org/releases.json`
  - `releases[]`를 읽어 moniker, version, released date를 정규화
- `lore_list`
  - `list_url/new.atom`
  - Atom entry에서 title, link, updated, content를 추출
  - CVE와 보안 키워드를 본문에서 추출
- `android_bulletin_index`
  - bulletin overview에서 최신 월별 bulletin 링크를 발견
  - 각 월 페이지를 다시 읽어서 CVE 수, severity 분포, note를 요약
- `gitiles_log`
  - `+log/refs/heads/{branch}?format=JSON`
  - 현재 예시 branch는 `android-mainline`

### 4.2 저장 구조

DB에는 4종류를 저장하게 했다.

- `items`
  - 운영자가 보는 정규화된 결과
- `raw_ingest_events`
  - 원본 payload 저장
- `poll_runs`
  - 어떤 소스를 언제 수집했고 몇 건을 봤는지 저장
- `email_deliveries`
  - 즉시 알림/digest 발송 이력 저장

### 4.3 분류 로직

분류는 완전한 ML이 아니라 운영 친화적인 규칙 기반 점수화로 만들었다.

- 확정 소스면 `+100`
- CVE가 있으면 `+40`
- 위험 키워드면 `+25`
- 문맥 키워드면 `+15`
- `critical`, `high` severity 힌트도 추가 가점

룰 소스는 [config/sources.example.yaml](C:/Users/RYZEN1/Desktop/rss/config/sources.example.yaml)에 두었고, 코드에서는 [app/services/classifier.py](C:/Users/RYZEN1/Desktop/rss/app/services/classifier.py)가 적용한다.

### 4.4 메일

SMTP host가 설정되지 않으면 실제 발송 대신 로그 preview를 남긴다.
즉, 서버를 먼저 올린 뒤 메일 계정 없이도 수집/분류 검증이 가능하다.

## 5. 실제 동작 검증 결과

검증 일시:

- 2026-03-24 Asia/Seoul 기준

검증 환경:

- Python 3.10 가상환경
- FastAPI `TestClient`
- SQLite 데모 DB

실제 poll을 돌린 소스:

- `kernel_releases`
- `linux_cve_announce`
- `linux_stable`
- `android_bulletin_overview`
- `android_common_kernel`

실행 결과:

- `kernel_releases`: `inserted=9`, `seen=9`
- `linux_cve_announce`: `inserted=20`, `seen=20`
- `linux_stable`: `inserted=20`, `seen=20`
- `android_bulletin_overview`: `inserted=3`, `seen=3`
- `android_common_kernel`: `inserted=20`, `seen=20`

데모 DB 집계:

- 총 `items`: `72`
- 총 `raw_ingest_events`: `72`
- 총 `poll_runs`: `5`

severity 분포:

- `confirmed_security`: `23`
- `security_candidate_high`: `1`
- `security_candidate_medium`: `14`
- `general_patch`: `25`
- `release_only`: `9`

이 결과는 소스 응답이 바뀌면 달라질 수 있으므로, 위 수치는 2026-03-24 데모 실행 시점의 결과다.

## 6. 테스트 결과

자동 테스트:

- 총 `6`개 테스트 통과

포함한 테스트:

- kernel.org 릴리즈 파싱
- lore Atom 파싱 및 CVE 추출
- Android bulletin 요약 파싱
- Gitiles JSON 로그 파싱
- 소스 설정 로딩
- `RSS_SMTP_TO` 문자열 환경변수 파싱

테스트 파일:

- [tests/test_collectors.py](C:/Users/RYZEN1/Desktop/rss/tests/test_collectors.py)
- [tests/test_source_loader.py](C:/Users/RYZEN1/Desktop/rss/tests/test_source_loader.py)
- [tests/test_settings.py](C:/Users/RYZEN1/Desktop/rss/tests/test_settings.py)

## 7. 운영 방법

### 로컬 실행

```bash
py -3.10 -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

### 수동 poll

```bash
curl -X POST http://127.0.0.1:8000/poll/kernel_releases
curl -X POST http://127.0.0.1:8000/poll/linux_cve_announce
curl -X POST http://127.0.0.1:8000/poll/android_bulletin_overview
```

### 상태 확인

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/items/recent
curl http://127.0.0.1:8000/poll-runs/recent
curl http://127.0.0.1:8000/raw-events/recent
```

## 8. 이번에 해결한 실제 문제

구현 중 잡아낸 운영성 이슈:

- `kernel.org` JSON 구조가 최초 가정보다 달라서 실제 구조에 맞게 수정
- `lore`는 HTML 파싱 대신 `new.atom`으로 바꿔 안정성 향상
- Android bulletin 제목에서 UI 문구가 섞이던 문제를 정제
- `RSS_SMTP_TO=alerts@example.com` 같은 평범한 환경변수가 깨지던 문제 수정
- SQLite 스레드 제약 대응을 위해 `check_same_thread=False` 적용
- raw ingest 저장 추가로 사후 분석 가능하게 개선

## 9. 현재 한계

- 첫 실행 시 `linux-cve-announce`는 즉시 알림이 많이 발생할 수 있다.
- `stable`과 `lkml`은 현재 제목/본문 키워드 기반 분류라 정밀도가 더 올라갈 여지가 있다.
- Android bulletin은 현재 월별 bulletin 단위로 저장한다.
  - CVE 개별 row 단위 추적은 다음 단계에서 추가 가능
- digest는 현재 텍스트 중심이다.
  - HTML 템플릿화 여지가 있다

## 10. 다음 단계 제안

우선순위 순서:

1. `linux_stable`과 `lkml`에 대한 false positive 감소
2. Android bulletin에서 CVE row 개별 엔티티화
3. `android_common_kernel` 보안 키워드 스코어 개선
4. 메일 템플릿 HTML화
5. 관리용 UI 추가

## 11. 결론

이번 작업으로 이 저장소는 더 이상 설계 문서만 있는 상태가 아니다.

현재 기준으로는:

- 실제 공식 소스를 수집하고
- 정규화된 아이템과 raw 이벤트를 저장하고
- 위험도를 분류하고
- 메일 preview 또는 SMTP 발송으로 연결할 수 있으며
- API로 상태와 최근 결과를 확인할 수 있다

즉, 운영 가능한 MVP 단계까지 올라온 상태다.
