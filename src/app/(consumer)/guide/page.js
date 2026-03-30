'use client';
import { useState } from 'react';

const STEPS = [
  {
    id: 'hosting',
    title: '워드프레스 호스팅 준비',
    icon: '1',
    subtitle: '블로그를 설치할 서버가 필요합니다',
    content: HostingStep,
  },
  {
    id: 'wordpress',
    title: '워드프레스 설치',
    icon: '2',
    subtitle: '클릭 몇 번이면 완료됩니다',
    content: WordPressStep,
  },
  {
    id: 'app-password',
    title: '앱 비밀번호 생성',
    icon: '3',
    subtitle: 'AutoBlog이 글을 발행하려면 필요합니다',
    content: AppPasswordStep,
  },
  {
    id: 'signup',
    title: '회원가입',
    icon: '4',
    subtitle: '30초면 완료, 7일 무료 체험 포함',
    content: SignupStep,
  },
  {
    id: 'onboarding',
    title: '초기 설정 (온보딩)',
    icon: '5',
    subtitle: '워드프레스 연결 + 카테고리 + 스케줄',
    content: OnboardingStep,
  },
  {
    id: 'initial-setup',
    title: '블로그 초기 세팅',
    icon: '6',
    subtitle: '메뉴/CSS/첫 글 발행 — 꼭 실행하세요!',
    content: InitialSetupStep,
  },
  {
    id: 'daily',
    title: '일상 사용법',
    icon: '7',
    subtitle: 'AI가 알아서 합니다. 확인만 하세요',
    content: DailyStep,
  },
  {
    id: 'monetization',
    title: '수익화 로드맵',
    icon: '8',
    subtitle: '애드센스 → 쿠팡 → 텐핑 → 자동 수익',
    content: MonetizationStep,
  },
  {
    id: 'faq',
    title: '자주 묻는 질문',
    icon: '?',
    subtitle: '궁금한 점은 여기서 확인하세요',
    content: FaqStep,
  },
];

export default function GuidePage() {
  const [activeStep, setActiveStep] = useState('hosting');
  const currentStep = STEPS.find(s => s.id === activeStep);
  const CurrentContent = currentStep?.content;

  return (
    <div>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', margin: 0 }}>
          시작 가이드
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 6 }}>
          처음부터 끝까지, 단계별로 따라하세요. 10분이면 블로그 자동 발행이 시작됩니다.
        </p>
      </div>

      {/* Step Navigation */}
      <div style={s.stepNav}>
        {STEPS.map((step, i) => {
          const isActive = step.id === activeStep;
          const stepIdx = STEPS.findIndex(s => s.id === activeStep);
          const isDone = i < stepIdx;
          return (
            <button
              key={step.id}
              onClick={() => setActiveStep(step.id)}
              style={{
                ...s.stepBtn,
                background: isActive ? 'var(--accent-bg)' : isDone ? 'rgba(16,185,129,0.06)' : 'var(--card)',
                borderColor: isActive ? 'var(--accent)' : isDone ? 'rgba(16,185,129,0.3)' : 'var(--card-border)',
              }}
            >
              <div style={{
                ...s.stepIcon,
                background: isActive ? 'var(--accent)' : isDone ? '#10b981' : 'var(--bg)',
                color: isActive || isDone ? '#fff' : 'var(--text-dim)',
              }}>
                {isDone ? '\u2713' : step.icon}
              </div>
              <div style={{ flex: 1, textAlign: 'left' }}>
                <div style={{
                  fontSize: 13, fontWeight: isActive ? 700 : 500,
                  color: isActive ? 'var(--accent)' : 'var(--text)',
                }}>
                  {step.title}
                </div>
                <div className="guide-step-subtitle" style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                  {step.subtitle}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Content Area */}
      <div style={s.contentCard}>
        {CurrentContent && <CurrentContent />}

        {/* Navigation Buttons */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 32, paddingTop: 20, borderTop: '1px solid var(--card-border)' }}>
          {STEPS.findIndex(st => st.id === activeStep) > 0 ? (
            <button
              onClick={() => {
                const idx = STEPS.findIndex(st => st.id === activeStep);
                setActiveStep(STEPS[idx - 1].id);
              }}
              style={s.navBtn}
            >
              \u2190 이전
            </button>
          ) : <div />}
          {STEPS.findIndex(st => st.id === activeStep) < STEPS.length - 1 ? (
            <button
              onClick={() => {
                const idx = STEPS.findIndex(st => st.id === activeStep);
                setActiveStep(STEPS[idx + 1].id);
              }}
              style={{ ...s.navBtn, ...s.navBtnPrimary }}
            >
              다음 \u2192
            </button>
          ) : <div />}
        </div>
      </div>

      {/* Contact */}
      <div style={s.contactBox}>
        막히는 부분이 있으신가요? <strong>planxsol@gmail.com</strong>으로 문의주세요. 영업일 24시간 이내 답변드립니다.
      </div>
    </div>
  );
}

/* ─── Step Content Components ─── */

function HostingStep() {
  return (
    <div>
      <h2 style={s.h2}>워드프레스 호스팅 준비하기</h2>
      <p style={s.p}>
        AutoBlog은 <strong>자체 호스팅 워드프레스</strong>에서 작동합니다.
        wordpress.com 무료 플랜은 사용할 수 없습니다.
      </p>

      <div style={s.tipBox}>
        <div style={s.tipTitle}>이미 워드프레스 블로그가 있으신가요?</div>
        <p style={s.tipText}>다음 단계로 바로 넘어가세요!</p>
      </div>

      <h3 style={s.h3}>추천 호스팅: Cloudways</h3>
      <p style={s.p}>
        초보자에게 가장 쉽고 안정적인 호스팅입니다.
        서버 관리를 자동으로 해주기 때문에 블로그 운영에만 집중할 수 있습니다.
      </p>

      <div style={s.ctaBox}>
        <a
          href="https://www.cloudways.com/en/?id=2126105"
          target="_blank"
          rel="noopener noreferrer"
          style={s.ctaBtn}
        >
          Cloudways 시작하기 (3일 무료 체험)
        </a>
        <p style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 8, textAlign: 'center' }}>
          월 $14부터 시작 / 신용카드 없이 3일 체험 가능
        </p>
      </div>

      <h3 style={s.h3}>Cloudways 가입 방법</h3>
      <StepList steps={[
        '위 링크를 클릭하여 Cloudways 사이트에 접속합니다',
        '"Start Free" 버튼을 클릭합니다',
        '이름, 이메일, 비밀번호를 입력하고 가입합니다',
        '이메일 인증을 완료합니다',
      ]} />

      <h3 style={s.h3}>서버 생성하기</h3>
      <StepList steps={[
        '로그인 후 "Add Server" 클릭',
        'Application: WordPress 선택',
        'Server: DigitalOcean 선택 (가장 저렴)',
        'Server Size: 1GB ($14/월) 선택 — 블로그에 충분합니다',
        'Location: Singapore 선택 (한국에서 가장 빠름)',
        '"Launch Now" 클릭 → 2~3분 후 서버 완성!',
      ]} />

      <div style={s.warnBox}>
        <strong>중요!</strong> 서버가 생성되면 나오는 정보를 메모하세요:
        <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
          <li>Application URL (예: wordpress-123456.cloudways.com)</li>
          <li>Admin Panel URL</li>
          <li>Username / Password</li>
        </ul>
      </div>

      <h3 style={s.h3}>내 도메인 연결하기 (선택)</h3>
      <p style={s.p}>
        나만의 도메인(예: myblog.com)을 사용하고 싶다면:
      </p>
      <StepList steps={[
        '도메인 구입 (가비아, 카페24, Namecheap 등에서 연 1~2만원)',
        'Cloudways → Application → Domain Management에서 도메인 추가',
        '도메인 업체에서 DNS를 Cloudways IP로 설정',
        'SSL 인증서 자동 적용 확인',
      ]} />
      <p style={s.p}>
        도메인 없이도 Cloudways가 제공하는 기본 URL로 시작할 수 있습니다.
        나중에 언제든 연결 가능합니다.
      </p>
    </div>
  );
}

function WordPressStep() {
  return (
    <div>
      <h2 style={s.h2}>워드프레스 설치 확인</h2>
      <p style={s.p}>
        Cloudways를 사용하셨다면 워드프레스가 <strong>이미 설치</strong>되어 있습니다!
        다른 호스팅을 사용하셨다면 "원클릭 설치" 기능으로 설치하세요.
      </p>

      <h3 style={s.h3}>워드프레스 관리자 접속</h3>
      <StepList steps={[
        '브라우저에서 내 블로그 주소 뒤에 /wp-admin 입력 (예: myblog.com/wp-admin)',
        'Cloudways에서 받은 Username / Password로 로그인',
        '대시보드가 보이면 성공!',
      ]} />

      <h3 style={s.h3}>기본 설정 (1분)</h3>
      <StepList steps={[
        '설정 → 일반: 사이트 제목을 내 블로그 이름으로 변경',
        '설정 → 읽기: "검색 엔진이 이 사이트를 색인하지 않도록" 체크 해제',
        '설정 → 고유주소: "글 이름" 선택 → 변경사항 저장',
      ]} />

      <div style={s.tipBox}>
        <div style={s.tipTitle}>왜 "글 이름" 고유주소인가요?</div>
        <p style={s.tipText}>
          URL이 myblog.com/ai-tools-review 처럼 깔끔해져서
          검색엔진(SEO)에 유리합니다. 애드센스 승인에도 도움이 됩니다.
        </p>
      </div>

      <h3 style={s.h3}>필수 플러그인 설치</h3>
      <p style={s.p}>워드프레스 관리자 → 플러그인 → 새로 추가:</p>
      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>플러그인</th>
            <th style={s.th}>용도</th>
            <th style={s.th}>필수 여부</th>
          </tr>
        </thead>
        <tbody>
          <tr><td style={s.td}>Yoast SEO</td><td style={s.td}>검색엔진 최적화</td><td style={s.td}>강력 추천</td></tr>
          <tr><td style={s.td}>Site Kit by Google</td><td style={s.td}>애드센스/GA 연동</td><td style={s.td}>애드센스 준비 시</td></tr>
          <tr><td style={s.td}>WP Super Cache</td><td style={s.td}>사이트 속도 향상</td><td style={s.td}>추천</td></tr>
        </tbody>
      </table>
    </div>
  );
}

function AppPasswordStep() {
  return (
    <div>
      <h2 style={s.h2}>앱 비밀번호 생성하기</h2>
      <p style={s.p}>
        AutoBlog이 워드프레스에 글을 자동 발행하려면 <strong>"앱 비밀번호"</strong>가 필요합니다.
        일반 로그인 비밀번호와는 다릅니다.
      </p>

      <div style={s.tipBox}>
        <div style={s.tipTitle}>앱 비밀번호란?</div>
        <p style={s.tipText}>
          비유하면 집 열쇠와 택배함 열쇠의 차이입니다.
          앱 비밀번호는 "택배함 열쇠"처럼 글 발행만 할 수 있는 제한된 접근권한입니다.
          블로그 설정을 바꾸거나 삭제하는 것은 불가능하니 안심하세요.
        </p>
      </div>

      <h3 style={s.h3}>생성 방법</h3>
      <StepList steps={[
        '워드프레스 관리자(wp-admin)에 로그인',
        '좌측 메뉴 → 사용자 → 프로필 클릭',
        '페이지 맨 아래로 스크롤',
        '"앱 비밀번호(Application Passwords)" 섹션 찾기',
        '"새 앱 비밀번호 이름"에 AutoBlog 입력',
        '"새 앱 비밀번호 추가" 버튼 클릭',
      ]} />

      <div style={s.warnBox}>
        <strong>반드시 복사하세요!</strong>
        <p style={{ margin: '6px 0 0', fontSize: 13 }}>
          생성된 비밀번호는 <strong>이 화면에서만 한 번</strong> 보여집니다.
          닫으면 다시 볼 수 없습니다. 메모장에 붙여넣기 해두세요.
        </p>
        <div style={s.codeBlock}>
          형식 예시: ABCD 1234 EFGH 5678 IJKL 9012
        </div>
        <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--text-dim)' }}>
          공백이 포함된 채로 그대로 사용하면 됩니다.
        </p>
      </div>

      <h3 style={s.h3}>"앱 비밀번호" 메뉴가 안 보여요</h3>
      <p style={s.p}>다음을 확인하세요:</p>
      <ul style={s.ul}>
        <li>워드프레스 버전이 <strong>5.6 이상</strong>인지 확인 (설정 → 업데이트)</li>
        <li>HTTPS(SSL)가 적용되어 있는지 확인 (주소가 https://로 시작)</li>
        <li>보안 플러그인(Wordfence 등)이 REST API를 차단하고 있지 않은지 확인</li>
      </ul>
    </div>
  );
}

function SignupStep() {
  return (
    <div>
      <h2 style={s.h2}>AutoBlog 회원가입</h2>
      <p style={s.p}>
        가입 즉시 <strong>7일간 Premium 기능을 무료로 체험</strong>할 수 있습니다.
      </p>

      <h3 style={s.h3}>가입 방법</h3>
      <StepList steps={[
        <span key="1">브라우저에서 <strong>30daysliving.com/login</strong> 접속</span>,
        '"회원가입" 탭 클릭',
        '이름(닉네임), 이메일, 비밀번호(6자 이상) 입력',
        '"회원가입" 버튼 클릭',
        '이메일 수신함 확인 → 인증 메일의 링크 클릭',
        '자동으로 초기 설정 화면으로 이동됩니다',
      ]} />

      <div style={s.tipBox}>
        <div style={s.tipTitle}>인증 메일이 안 오나요?</div>
        <p style={s.tipText}>
          스팸/프로모션 폴더를 확인하세요. Gmail의 경우 "프로모션" 탭에 들어갈 수 있습니다.
          5분이 지나도 안 오면 다시 가입을 시도하세요.
        </p>
      </div>

      <h3 style={s.h3}>7일 무료 체험에 포함되는 것</h3>
      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>기능</th>
            <th style={s.th}>체험 기간 중</th>
            <th style={s.th}>체험 후 (Standard)</th>
          </tr>
        </thead>
        <tbody>
          <tr><td style={s.td}>일일 발행</td><td style={s.td}>20편</td><td style={s.td}>4편</td></tr>
          <tr><td style={s.td}>카테고리</td><td style={s.td}>무제한</td><td style={s.td}>6개</td></tr>
          <tr><td style={s.td}>AI 폴리싱</td><td style={s.td}>Claude Sonnet</td><td style={s.td}>-</td></tr>
          <tr><td style={s.td}>골든 모드</td><td style={s.td}>사용 가능</td><td style={s.td}>-</td></tr>
          <tr><td style={s.td}>커스텀 스케줄</td><td style={s.td}>사용 가능</td><td style={s.td}>-</td></tr>
        </tbody>
      </table>
    </div>
  );
}

function OnboardingStep() {
  return (
    <div>
      <h2 style={s.h2}>초기 설정 (온보딩)</h2>
      <p style={s.p}>
        회원가입 후 자동으로 5단계 설정 화면이 나타납니다. 3~5분이면 완료됩니다.
      </p>

      <h3 style={s.h3}>1단계: 워드프레스 연결</h3>
      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>입력 항목</th>
            <th style={s.th}>입력할 내용</th>
            <th style={s.th}>예시</th>
          </tr>
        </thead>
        <tbody>
          <tr><td style={s.td}>사이트 URL</td><td style={s.td}>내 블로그 주소</td><td style={s.td}>https://myblog.com</td></tr>
          <tr><td style={s.td}>사용자명</td><td style={s.td}>워드프레스 로그인 ID</td><td style={s.td}>admin</td></tr>
          <tr><td style={s.td}>앱 비밀번호</td><td style={s.td}>STEP 3에서 생성한 비밀번호</td><td style={s.td}>ABCD 1234 EFGH...</td></tr>
        </tbody>
      </table>
      <p style={s.p}>"연결 테스트" 버튼을 눌러서 <strong>성공 메시지가 나오면</strong> 다음으로 진행합니다.</p>

      <div style={s.warnBox}>
        <strong>연결 실패 시 체크리스트:</strong>
        <ul style={{ margin: '6px 0 0', paddingLeft: 20, fontSize: 13 }}>
          <li>URL에 <code style={s.code}>https://</code> 를 빼먹지 않았는지</li>
          <li>앱 비밀번호를 일반 로그인 비밀번호와 헷갈리지 않았는지</li>
          <li>Cloudways에서 받은 URL이 맞는지 (오타 확인)</li>
        </ul>
      </div>

      <h3 style={s.h3}>2단계: 카테고리 선택</h3>
      <p style={s.p}>블로그에 쓸 주제를 <strong>최소 2개</strong> 선택합니다.</p>
      <div style={s.tipBox}>
        <div style={s.tipTitle}>수익화에 유리한 인기 조합</div>
        <ul style={{ margin: '6px 0 0', paddingLeft: 20, fontSize: 13 }}>
          <li><strong>AI 도구 + 재테크</strong> — ROI 최고 조합</li>
          <li><strong>스마트홈 + 가전</strong> — 쿠팡 연동에 유리</li>
          <li><strong>건강 + 뷰티</strong> — 텐핑 CPA 전환율 높음</li>
          <li><strong>정부지원 + 세금</strong> — 검색량 안정적</li>
        </ul>
      </div>

      <h3 style={s.h3}>3단계: 발행 스케줄</h3>
      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>옵션</th>
            <th style={s.th}>발행 시간</th>
            <th style={s.th}>추천 대상</th>
          </tr>
        </thead>
        <tbody>
          <tr><td style={s.td}>하루 2회</td><td style={s.td}>08:00, 18:00</td><td style={s.td}>느긋한 운영</td></tr>
          <tr><td style={{...s.td, fontWeight: 600}}>하루 4회 (추천)</td><td style={s.td}>07:00, 12:00, 17:00, 22:00</td><td style={s.td}>빠른 성장</td></tr>
          <tr><td style={s.td}>평일만 1회</td><td style={s.td}>08:00 (월~금)</td><td style={s.td}>보수적 운영</td></tr>
        </tbody>
      </table>

      <h3 style={s.h3}>4단계: 블로그 단계</h3>
      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>선택</th>
            <th style={s.th}>나의 상황</th>
          </tr>
        </thead>
        <tbody>
          <tr><td style={s.td}>신규 블로그</td><td style={s.td}>글이 거의 없는 새 블로그</td></tr>
          <tr><td style={s.td}>애드센스 준비 중</td><td style={s.td}>글은 있지만 애드센스 미승인</td></tr>
          <tr><td style={s.td}>애드센스 승인 완료</td><td style={s.td}>이미 애드센스 수익 발생 중</td></tr>
          <tr><td style={s.td}>수익화 단계</td><td style={s.td}>쿠팡/텐핑 등 다채널 운영 중</td></tr>
        </tbody>
      </table>
      <p style={s.p}>AI가 이 단계에 맞춰 글 스타일과 제휴 링크 포함 여부를 자동 조절합니다.</p>

      <h3 style={s.h3}>5단계: 확인 및 시작</h3>
      <p style={s.p}>설정을 검토하고 "시작하기"를 누르면 대시보드로 이동합니다!</p>
    </div>
  );
}

function InitialSetupStep() {
  return (
    <div>
      <h2 style={s.h2}>블로그 초기 세팅</h2>
      <p style={s.p}>
        대시보드에 들어왔다면, <strong>설정 페이지에서 3가지를 반드시 실행</strong>하세요.
        이것을 해야 애드센스 승인에 필요한 필수 페이지와 초기 글이 생성됩니다.
      </p>

      <div style={s.actionCard}>
        <div style={s.actionHeader}>
          <span style={s.actionIcon}>1</span>
          <div>
            <div style={s.actionTitle}>메뉴 설정</div>
            <div style={s.actionDesc}>소개, 개인정보처리방침, 연락처 페이지 + 상단 메뉴 자동 생성</div>
          </div>
        </div>
        <div style={s.actionMeta}>소요시간: 1~2분 / 설정 → "메뉴 설정" 버튼 클릭</div>
      </div>

      <div style={s.actionCard}>
        <div style={s.actionHeader}>
          <div>
            <span style={s.actionIcon}>2</span>
          </div>
          <div>
            <div style={s.actionTitle}>CSS 주입</div>
            <div style={s.actionDesc}>블로그 테마 스타일링 적용 — 깔끔하고 전문적인 디자인</div>
          </div>
        </div>
        <div style={s.actionMeta}>소요시간: 1~2분 / 설정 → "CSS 주입" 버튼 클릭</div>
      </div>

      <div style={s.actionCard}>
        <div style={s.actionHeader}>
          <div>
            <span style={s.actionIcon}>3</span>
          </div>
          <div>
            <div style={s.actionTitle}>첫 글 발행 (3편)</div>
            <div style={s.actionDesc}>AI가 3편의 글을 자동 작성하여 워드프레스에 발행</div>
          </div>
        </div>
        <div style={s.actionMeta}>소요시간: 5~10분 / 설정 → "발행" 버튼 클릭</div>
      </div>

      <div style={s.warnBox}>
        <strong>3개 모두 반드시 실행하세요!</strong>
        <p style={{ margin: '6px 0 0', fontSize: 13 }}>
          메뉴 설정을 안 하면 소개/개인정보/연락처 페이지가 없어서 애드센스 승인이 거부됩니다.
          CSS를 안 넣으면 블로그가 밋밋하게 보입니다.
        </p>
      </div>

      <div style={s.tipBox}>
        <div style={s.tipTitle}>실행 후 확인하기</div>
        <p style={s.tipText}>
          각 버튼을 누른 후 1~2분 기다리면 블로그에 반영됩니다.
          내 블로그 주소를 새로고침해서 메뉴가 생겼는지, 글이 올라왔는지 확인하세요.
        </p>
      </div>
    </div>
  );
}

function DailyStep() {
  return (
    <div>
      <h2 style={s.h2}>일상 사용법</h2>
      <p style={s.p}>
        초기 설정만 끝나면 <strong>AI가 스케줄에 맞춰 매일 자동으로 글을 발행</strong>합니다.
        여러분이 할 일은 가끔 대시보드를 확인하는 것뿐입니다.
      </p>

      <h3 style={s.h3}>홈 (대시보드)</h3>
      <p style={s.p}>한눈에 블로그 상태를 파악할 수 있습니다:</p>
      <ul style={s.ul}>
        <li><strong>오늘 발행 수</strong> — 오늘 몇 편이 발행되었는지</li>
        <li><strong>이번 달 수익</strong> — 현재까지 누적 수익</li>
        <li><strong>블로그 건강 점수</strong> — 0~100점, 높을수록 좋음</li>
        <li><strong>마일스톤</strong> — 첫 글, 10편, 30편, 애드센스 승인, 첫 수익 등 달성 현황</li>
        <li><strong>스마트 가이드</strong> — 현재 상태에 맞는 다음 행동 안내</li>
      </ul>

      <h3 style={s.h3}>내 블로그</h3>
      <ul style={s.ul}>
        <li>발행된 글 목록과 품질 점수 확인</li>
        <li>카테고리 분포 차트</li>
        <li>글 제목 옆 링크를 클릭하면 실제 블로그에서 확인 가능</li>
      </ul>

      <h3 style={s.h3}>수익</h3>
      <ul style={s.ul}>
        <li>월별 수익 추이 그래프</li>
        <li>채널별 수익 비교 (애드센스/쿠팡/텐핑)</li>
        <li>수익화 로드맵 — 현재 단계와 다음 할 일</li>
      </ul>

      <h3 style={s.h3}>설정</h3>
      <ul style={s.ul}>
        <li>카테고리, 스케줄 변경 가능</li>
        <li>프로필 수정</li>
        <li>사이트 추가 (Premium 이상)</li>
      </ul>

      <div style={s.tipBox}>
        <div style={s.tipTitle}>품질 점수란?</div>
        <p style={s.tipText}>
          AI가 글을 작성할 때 자동으로 품질을 평가합니다.
          90점 이상 = 우수 (녹색), 80~89점 = 양호 (노란색), 80점 미만 = 개선 필요 (빨간색).
          대부분의 글은 90점 이상입니다.
        </p>
      </div>
    </div>
  );
}

function MonetizationStep() {
  return (
    <div>
      <h2 style={s.h2}>수익화 로드맵</h2>
      <p style={s.p}>
        블로그 수익화는 3단계로 진행됩니다. AI가 현재 단계에 맞게 자동으로 글 스타일을 조절합니다.
      </p>

      <div style={s.stageCard('#3b82f6')}>
        <div style={s.stageHeader}>
          <span style={s.stageBadge('#3b82f6')}>1단계</span>
          <strong>콘텐츠 축적</strong>
        </div>
        <div style={s.stageContent}>
          <p><strong>목표:</strong> 20편 이상 발행 + 필수 페이지 완비</p>
          <p><strong>기간:</strong> 1~2주</p>
          <p><strong>AI 전략:</strong> 제휴 링크 없는 순수 정보 콘텐츠만 작성</p>
          <p><strong>할 일:</strong></p>
          <ul style={{ paddingLeft: 20, margin: 0 }}>
            <li>매일 자동 발행 확인</li>
            <li>20편 쌓이면 구글 애드센스 신청</li>
            <li>필수 페이지 확인 (소개/개인정보/연락처 — 초기 세팅에서 자동 생성됨)</li>
          </ul>
        </div>
      </div>

      <div style={s.stageCard('#f59e0b')}>
        <div style={s.stageHeader}>
          <span style={s.stageBadge('#f59e0b')}>2단계</span>
          <strong>수익 시작</strong>
        </div>
        <div style={s.stageContent}>
          <p><strong>목표:</strong> 월 5~15만원 수익</p>
          <p><strong>기간:</strong> 2~4주차</p>
          <p><strong>할 일:</strong></p>
          <ul style={{ paddingLeft: 20, margin: 0 }}>
            <li>애드센스 승인 후 설정에서 "애드센스 승인 완료" 단계로 변경</li>
            <li>텐핑 가입 → 보험/카드 오퍼가 건당 3,000~8,000원</li>
            <li>쿠팡 파트너스 가입 → 수동 링크 삽입 시작</li>
            <li>쿠팡 매출 15만원 달성 시 → API 자동화 신청 가능</li>
          </ul>
        </div>
      </div>

      <div style={s.stageCard('#10b981')}>
        <div style={s.stageHeader}>
          <span style={s.stageBadge('#10b981')}>3단계</span>
          <strong>수익 극대화</strong>
        </div>
        <div style={s.stageContent}>
          <p><strong>목표:</strong> 월 30만원 이상 자동 수익</p>
          <p><strong>기간:</strong> 1개월 이후~</p>
          <p><strong>할 일:</strong></p>
          <ul style={{ paddingLeft: 20, margin: 0 }}>
            <li>쿠팡 API 자동화 (AI가 제품 추천 링크 자동 삽입)</li>
            <li>AI 도구 리뷰 시 레퍼럴 프로그램 활용</li>
            <li>Premium 플랜으로 일일 20편 + 골든 모드 활성화</li>
            <li>고RPM 카테고리(재테크, AI) 비중 확대</li>
          </ul>
        </div>
      </div>

      <div style={s.tipBox}>
        <div style={s.tipTitle}>현실적인 수익 기대치</div>
        <ul style={{ margin: '6px 0 0', paddingLeft: 20, fontSize: 13 }}>
          <li><strong>1개월:</strong> 애드센스 승인 + 월 1~3만원</li>
          <li><strong>2개월:</strong> 텐핑/쿠팡 추가 → 월 5~15만원</li>
          <li><strong>3개월+:</strong> 자동화 안정 → 월 20~50만원</li>
        </ul>
        <p style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 8 }}>
          * 카테고리, 발행량, 검색 트렌드에 따라 달라질 수 있습니다.
        </p>
      </div>
    </div>
  );
}

function FaqStep() {
  const faqs = [
    {
      q: '글을 직접 쓰지 않아도 되나요?',
      a: '네. AI가 키워드 선정 → 글 작성 → 이미지 삽입 → 워드프레스 발행까지 전부 자동으로 합니다. 설정만 해두면 매일 스케줄에 맞춰 발행됩니다.',
    },
    {
      q: '애드센스 승인은 얼마나 걸리나요?',
      a: '보통 20편 이상 + 필수 페이지(소개/개인정보/연락처) 완비 후 신청하면 1~2주 내 승인됩니다. 초기 세팅에서 메뉴 설정을 실행하면 필수 페이지가 자동 생성됩니다.',
    },
    {
      q: '글 품질이 걱정됩니다.',
      a: 'Premium 이상 플랜에서는 "골든 모드"가 활성화되어 가짜 통계나 날조된 정보가 포함되지 않습니다. 품질 점수 90점 이상이 대부분이며, AI 폴리싱(Claude)으로 문장이 자연스럽게 다듬어집니다.',
    },
    {
      q: '여러 블로그를 운영할 수 있나요?',
      a: 'Standard는 1개, Premium은 최대 3개, MaMa는 무제한으로 운영할 수 있습니다.',
    },
    {
      q: '중간에 카테고리를 바꿀 수 있나요?',
      a: '네. 설정 → 카테고리 선택에서 언제든 변경 가능합니다.',
    },
    {
      q: '워드프레스 연결이 안 됩니다.',
      a: '1) URL에 https:// 포함 확인 2) "앱 비밀번호"를 사용했는지 확인 (일반 비밀번호 아님!) 3) 워드프레스 버전 5.6 이상인지 확인 4) 보안 플러그인이 REST API를 차단하고 있지 않은지 확인',
    },
    {
      q: '발행된 글을 수정할 수 있나요?',
      a: '네. 워드프레스 관리자 페이지(wp-admin)에서 직접 수정 가능합니다. 대시보드 "내 블로그" 탭에서 글 제목 옆 링크를 클릭하면 해당 글로 바로 이동합니다.',
    },
    {
      q: '체험 기간이 끝나면 어떻게 되나요?',
      a: '자동으로 Standard 플랜으로 전환됩니다. 일일 4편, 카테고리 6개 제한이 적용되며, 기존에 발행된 글은 그대로 유지됩니다.',
    },
    {
      q: '환불이 가능한가요?',
      a: '7일 무료 체험 중에는 비용이 청구되지 않습니다. 유료 플랜 전환 후 환불 정책은 별도 문의해주세요.',
    },
    {
      q: '호스팅 추천이 있나요?',
      a: 'Cloudways를 추천합니다. 초보자도 쉽게 사용할 수 있고, 3일 무료 체험이 가능합니다. 이 가이드의 첫 번째 단계에서 자세히 안내합니다.',
    },
  ];

  return (
    <div>
      <h2 style={s.h2}>자주 묻는 질문</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {faqs.map((faq, i) => (
          <FaqItem key={i} q={faq.q} a={faq.a} />
        ))}
      </div>
    </div>
  );
}

/* ─── Reusable Sub-components ─── */

function StepList({ steps }) {
  return (
    <ol style={s.ol}>
      {steps.map((step, i) => (
        <li key={i} style={s.olLi}>{step}</li>
      ))}
    </ol>
  );
}

function FaqItem({ q, a }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      border: '1px solid var(--card-border)',
      borderRadius: 10,
      overflow: 'hidden',
      background: open ? 'var(--card)' : 'transparent',
    }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%', padding: '14px 16px', border: 'none', background: 'transparent',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          fontSize: 14, fontWeight: 600, color: 'var(--text)', textAlign: 'left',
        }}
      >
        <span>{q}</span>
        <span style={{ fontSize: 12, color: 'var(--text-dim)', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
          {'\u25BC'}
        </span>
      </button>
      {open && (
        <div style={{ padding: '0 16px 14px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          {a}
        </div>
      )}
    </div>
  );
}

/* ─── Styles ─── */

const s = {
  h2: { fontSize: 18, fontWeight: 700, color: 'var(--text)', margin: '0 0 12px' },
  h3: { fontSize: 15, fontWeight: 600, color: 'var(--text)', margin: '24px 0 10px' },
  p: { fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, margin: '0 0 12px' },
  ul: { paddingLeft: 20, margin: '0 0 12px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 },
  ol: { paddingLeft: 20, margin: '0 0 12px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 },
  olLi: { marginBottom: 6 },

  stepNav: {
    display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 24,
  },
  stepBtn: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
    borderRadius: 10, border: '1px solid var(--card-border)', cursor: 'pointer',
    transition: 'all 0.15s', width: '100%', textAlign: 'left',
  },
  stepIcon: {
    width: 32, height: 32, borderRadius: '50%', display: 'flex', alignItems: 'center',
    justifyContent: 'center', fontSize: 13, fontWeight: 700, flexShrink: 0,
  },
  contentCard: {
    background: 'var(--card)', border: '1px solid var(--card-border)', borderRadius: 14,
    padding: 28,
  },
  navBtn: {
    padding: '10px 24px', borderRadius: 8, border: '1px solid var(--card-border)',
    background: 'var(--card)', cursor: 'pointer', fontSize: 13, fontWeight: 600,
    color: 'var(--text-secondary)',
  },
  navBtnPrimary: {
    background: 'var(--accent)', color: '#fff', border: 'none',
  },
  contactBox: {
    marginTop: 24, padding: '16px 20px', borderRadius: 10,
    background: 'var(--card)', border: '1px solid var(--card-border)',
    fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center',
  },

  tipBox: {
    background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)',
    borderRadius: 10, padding: '14px 16px', margin: '16px 0',
  },
  tipTitle: { fontSize: 13, fontWeight: 700, color: 'var(--accent)', marginBottom: 4 },
  tipText: { fontSize: 13, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6 },

  warnBox: {
    background: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.2)',
    borderRadius: 10, padding: '14px 16px', margin: '16px 0',
    fontSize: 13, color: 'var(--text)',
  },

  ctaBox: {
    margin: '20px 0', padding: 20, borderRadius: 12,
    background: 'linear-gradient(135deg, rgba(124,58,237,0.06), rgba(59,130,246,0.06))',
    border: '1px solid rgba(124,58,237,0.15)', textAlign: 'center',
  },
  ctaBtn: {
    display: 'inline-block', padding: '14px 32px', borderRadius: 10,
    background: 'linear-gradient(135deg, #7c3aed, #3b82f6)', color: '#fff',
    fontSize: 15, fontWeight: 700, textDecoration: 'none',
    boxShadow: '0 4px 14px rgba(124,58,237,0.3)',
  },

  codeBlock: {
    background: 'var(--bg)', padding: '10px 14px', borderRadius: 8,
    fontFamily: 'monospace', fontSize: 13, marginTop: 8,
    border: '1px solid var(--card-border)', color: 'var(--text)',
  },
  code: {
    background: 'var(--bg)', padding: '2px 6px', borderRadius: 4,
    fontFamily: 'monospace', fontSize: 12,
  },

  table: {
    width: '100%', borderCollapse: 'collapse', margin: '12px 0',
    fontSize: 13, borderRadius: 8, overflow: 'hidden',
  },
  th: {
    padding: '10px 14px', background: 'rgba(59,130,246,0.08)',
    fontWeight: 600, color: 'var(--text)', textAlign: 'left',
    borderBottom: '1px solid var(--card-border)',
  },
  td: {
    padding: '10px 14px', borderBottom: '1px solid var(--card-border)',
    color: 'var(--text-secondary)',
  },

  actionCard: {
    border: '1px solid var(--card-border)', borderRadius: 12, padding: 16,
    margin: '12px 0', background: 'var(--bg)',
  },
  actionHeader: {
    display: 'flex', alignItems: 'flex-start', gap: 14,
  },
  actionIcon: {
    display: 'inline-flex', width: 28, height: 28, borderRadius: '50%',
    background: 'var(--accent)', color: '#fff', alignItems: 'center',
    justifyContent: 'center', fontSize: 13, fontWeight: 700, flexShrink: 0,
  },
  actionTitle: { fontSize: 14, fontWeight: 700, color: 'var(--text)' },
  actionDesc: { fontSize: 12, color: 'var(--text-dim)', marginTop: 4 },
  actionMeta: {
    marginTop: 10, fontSize: 12, color: 'var(--text-dim)',
    paddingTop: 10, borderTop: '1px solid var(--card-border)',
  },

  stageCard: (color) => ({
    border: `1px solid ${color}30`,
    borderLeft: `4px solid ${color}`,
    borderRadius: 10, padding: 16, margin: '16px 0',
    background: `${color}08`,
  }),
  stageHeader: {
    display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
    fontSize: 15, color: 'var(--text)',
  },
  stageBadge: (color) => ({
    display: 'inline-block', padding: '3px 10px', borderRadius: 20,
    background: color, color: '#fff', fontSize: 11, fontWeight: 700,
  }),
  stageContent: {
    fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7,
  },
};
