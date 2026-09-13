# CLAUDE.md — wp-auto Project Guide

## Project Overview
AutoBlog Engine v5.0 + Dashboard — AI 기반 자동 블로그 콘텐츠 생성/발행 및 모니터링 시스템

## Tech Stack
- **Frontend:** Next.js 14 (App Router) + React 18 + Recharts
- **Backend:** Python 3.11 (scripts/main.py)
- **Database:** Supabase (PostgreSQL) with Realtime
- **AI Models:** DeepSeek V3 (primary), Claude Sonnet 4 (polish), Grok/Gemini/GPT (fallback)
- **CI/CD:** GitHub Actions (4 daily scheduled runs at KST 07/12/17/22)
- **Deployment:** Vercel (auto-deploy from planxs-ai/wp-auto, git author: planxsol@gmail.com)
- **Domain:** 30daysliving.com (consumer), wp-auto.vercel.app (admin)
- **Monetization:** Adsense, Coupang CPS, Tenping CPA

## Architecture
```
scripts/main.py              → Content generation & WordPress publishing (Python)
src/app/page.js              → Admin monitoring dashboard (React, "use client")
src/app/(auth)/login/        → Admin login only (no signup; consumer SaaS removed 2026-09-13)
src/app/api/setup/route.js   → GitHub Actions trigger API (publish/menu/pages/css) — admin JWT required
src/app/api/etf-report/      → ETF report workflow trigger — admin JWT required
src/app/api/admin/me/        → AdminGate check (server-side requireAdmin; returns live_publish switch)
src/app/api/health/          → Env presence check (booleans only)
src/components/ui.js         → Shared UI components (Card, InputField, ActionButton, etc.)
src/lib/admin-api.js         → Server-only: requireAdmin (JWT + ADMIN_USER_IDS allowlist + user_profiles.role),
                               live-publish switch (PUBLISH_DISPATCH_ENABLED), dispatchWorkflow
src/lib/hooks.js             → Admin dashboard hooks for Supabase data fetching
src/lib/supabase.js          → Supabase client + auth helpers
migrations/                  → Supabase SQL migrations
data/                        → keywords.json, used_keywords.json, affiliates.json
.github/workflows/           → publish.yml, setup-menu.yml, inject-css.yml, etf-report.yml
```

## Key Commands
```bash
# Frontend
npm run dev           # Dev server (localhost:3000)
npm run build         # Production build

# Backend
python scripts/main.py --count 3              # Publish 3 posts
python scripts/main.py --count 1 --dry-run    # Test without publishing
python scripts/main.py --pipeline hotdeal      # Specific pipeline
```

## Code Conventions
- **Python:** snake_case, class-based (KeywordManager, ContentGenerator, etc.), logging module
- **React:** Functional components, "use client", inline styles, CSS variables
- **Language:** Korean for UI/content, English for code identifiers
- **Timezone:** KST (UTC+9) throughout

## Database Tables
- **Core:** sites, publish_logs, api_costs, revenue, seo_health, email_stats, sns_stats, alerts, dashboard_config
- **Consumer:** plans, user_profiles (extends auth.users), user_sites, user_milestones (RLS enabled)

## Environment Variables
- Frontend: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
- Backend (GitHub Secrets): WP_URL, WP_USERNAME, WP_APP_PASSWORD, DEEPSEEK_API_KEY, CLAUDE_API_KEY, UNSPLASH_ACCESS_KEY, SUPABASE_URL, SUPABASE_KEY, SITE_ID
