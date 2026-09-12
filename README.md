# AutoBlog Engine v5.0 — Cloudways WordPress

AI 자동 글 생성 + 발행 + Supabase 대시보드 연동

## 구조
```
scripts/main.py          — 메인 엔진 (키워드→생성→발행→로깅)
data/keywords.json       — 키워드 풀 (50개 초기)
data/affiliates.json     — 제휴 링크 설정
data/used_keywords.json  — 사용 완료 키워드
.github/workflows/publish.yml — 하루 4회 자동 실행
```

## GitHub Secrets 필수
- `WP_URL` — WordPress 사이트 URL
- `WP_USERNAME` — WordPress 관리자 아이디
- `WP_APP_PASSWORD` — WordPress 앱 비밀번호
- `DEEPSEEK_API_KEY` — DeepSeek API 키
- `CLAUDE_API_KEY` — Claude API 키 (선택, 폴리싱용)
- `UNSPLASH_ACCESS_KEY` — Unsplash API 키 (선택, 이미지용)
- `SUPABASE_URL` — Supabase 프로젝트 URL
- `SUPABASE_KEY` — Supabase anon key

## 실행
```bash
# 수동 실행
python scripts/main.py --count 3

# 드라이런 (발행 없이 테스트)
python scripts/main.py --count 1 --dry-run
```

## 애드센스 심사 준비

자동 생성 글은 기본적으로 WordPress **초안**으로 저장합니다. 공개는 WordPress에서 근거를 확인한 후 진행하세요. 내부 품질 점수는 사실 확인이나 Google 승인 판정이 아닙니다.

- [변경 범위·적용 순서·현재 미검증 항목](docs/adsense-readiness.md)
- 회귀 테스트: `python -m unittest discover -s tests -v`
- 공개 글 점검: `python scripts/audit_adsense.py --url https://planx-ai.com`
- 페이지 생성: `python scripts/setup_pages.py` (기존 페이지 보존, 누락된 정보 페이지 초안만 생성)
- 페이지 초안에 필요한 환경변수: `WP_URL`, `WP_USERNAME`, `WP_APP_PASSWORD`, `BLOG_OWNER`, `BLOG_DESC`, `CONTACT_EMAIL`. 대시보드 운영정보 연동은 `SITE_ID`, `SUPABASE_URL`, `SUPABASE_KEY`를 사용합니다.
- `--dry-run`은 공개를 생략하지만 AI 생성 등 읽기/API 호출 비용은 발생할 수 있습니다.

실제 사이트 반려 대응: [700편 공개 목록 조사·수정 적용 절차](docs/adsense/site-application.md). WordPress 수정본·홈/목록 플러그인·원문 백업/복구 도구를 포함합니다. GitHub 병합과 실제 WordPress 적용은 별도입니다.
