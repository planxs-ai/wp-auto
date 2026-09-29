# deals — 쿠팡 가격 데이터 딜 엔진 (30일 실증)

> 밑그림: `planxs-ai/bid` → `docs/blueprints/20260907-shopping-affiliate-automation.md` (draft-2, 2026-09-08 대표 승인)
> 한 줄: **쿠팡 가격을 매시간 쌓아 "지금이 수집 기간 최저가인지"를 차트로 증명하는 딜 엔진.**

## 현재 검증 상태 (정직 라벨)

| 항목 | 상태 |
|---|---|
| 감지기·라벨·고지문·멱등성 | 🔴 DEV — `pytest tests/test_deals.py` **34건 통과** (API·DB 0콜) |
| 쿠팡 API 실호출 (서명·엔드포인트·필드명) | ⚫ **미검증** — 공식 문서 접근이 막혀 경로·필드가 전부 `[추정]`. 첫 `selftest`→`snapshot` 실행에서 대조 필요 |
| 스냅샷 24시간 무오류 | ⚫ 미착수 |
| 텔레그램·WP 실발행 | ⚫ 미착수 (WP는 `status: draft` 고정) |
| 확정 수수료 | ⚫ 0건 |

**"작동한다"고 말할 수 있는 범위는 로직뿐이다.** 실호출은 한 번도 하지 않았다.

## 명령

```bash
python -m deals.run selftest              # API·DB 0콜 자체점검
python -m deals.run snapshot --mode hourly # 베스트카테고리+골드박스
python -m deals.run snapshot --mode daily  # + 관찰 키워드 검색(일 1회)
python -m deals.run publish --dry-run      # 감지만, 발행 없음
python -m deals.run publish                # 텔레그램·WP 발행
python -m deals.run report                 # 최근 실행·수집 현황
python -m pytest tests/test_deals.py -q    # 회귀 기준선
```

## 구조

| 파일 | 역할 |
|---|---|
| `config.yaml` | **API 스펙·예산·감지 임계·발행 규칙은 전부 여기.** 코드에 필드명 하드코딩 금지 |
| `core.py` | 설정·KST 시간·예산(일/시간당)·서킷브레이커·시간 예산·저장소(PostgREST / 인메모리) |
| `coupang_client.py` | HMAC 서명(`CEA algorithm=HmacSHA256…`)·재시도·원본 보존·응답 매핑 |
| `snapshot.py` | 수집 → `deal_products` / `deal_price_snapshots` 멱등 UPSERT |
| `detector.py` | 순수 함수 감지기 — 신저가 / 할인율 점프. **기준 기간 = 실제 수집 일수** |
| `chart.py` | 의존성 0 가격 차트 SVG (웜톤) |
| `publish.py` | 텔레그램·WP 발행 + **고지문·금지표현 게이트** |
| `run.py` | CLI·실행 기록(`deal_runs`)·신호 처리 |

## 안전장치 (하나라도 빼면 설계가 깨진다)

1. **예산** — 일 400콜 + 오퍼레이션별 시간당. 시작 시 **DB 실사용을 preflight로 차감**한다(프로세스 지역 카운터만 믿으면 잡을 쪼갤 때 두 배가 된다).
2. **서킷브레이커** — 연결 실패·5xx·비JSON 연속 3회 → `UPSTREAM_DOWN`으로 즉시 중단.
3. **시간 예산** — `soft 12분`(수집만 정지, `OK` 유지) < `hard 15분`(중단, `PARTIAL`) < `timeout 17m` < `job 20분`. **넷을 함께 바꾼다.**
4. **멱등성** — 스냅샷 자연키 `(product_id, ts_hour)`, 딜 `(product_id, kind, ts_day, channel)`. 재실행해도 결과 동일.
5. **고지문** — `[광고] 이 게시물은 쿠팡 파트너스…` 가 **첫 줄**에 없으면 발행이 예외로 실패한다(공정위 「첫 노출 화면」).
6. **정직한 라벨** — 수집 90일 미만이면 "수집 N일차 최저가"로만 쓴다. 코드가 강제한다.
7. **noindex 기본** — WP 딜 페이지는 `rank_math_robots: noindex,nofollow` + `status: draft`. thin content 페널티 회피.
8. **시크릿** — 키·토큰은 환경변수/GitHub Secrets만. 레포에 키 파일 금지(`.gitignore`).

## 대표가 할 일 (구현 후 실행 전)

1. **Supabase**: `migrations/deals_001.sql` 을 SQL Editor에 1회 실행
2. **GitHub Secrets 6개**: `COUPANG_ACCESS_KEY` · `COUPANG_SECRET_KEY` · `COUPANG_SUB_ID` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` · (딜 전용 사이트면) `DEALS_WP_URL`/`DEALS_WP_USERNAME`/`DEALS_WP_APP_PASSWORD`
3. **워크플로 수동 실행** → `command: selftest` → 통과 확인 후 `snapshot`(hourly) 1회. 여기서 **API 경로·필드명이 실제와 다르면 `config.yaml`만 고친다**
4. WordPress에 `scripts/rank_math_rest_fix.php` 플러그인이 활성인지 확인(noindex 메타를 REST로 쓰려면 필요)
