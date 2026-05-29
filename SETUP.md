# GitHub 자동화 세팅 가이드 (15분, 한 번만)

이거 한 번 따라하면 **평생 손 안 댐**. 매주 월요일 9AM에 GitHub가 자동으로 시세 가져와서 페이지 갱신.

---

## 0단계 — GitHub 계정 (이미 있으면 건너뛰기)

1. https://github.com/signup 접속
2. 이메일·비밀번호·username 입력 (username은 URL에 들어가니 깔끔하게 — 예: `juhyun-dr`)
3. 이메일 인증

---

## 1단계 — 새 저장소(repo) 만들기

1. GitHub 우상단 **`+` → New repository**
2. 입력값:
   - **Repository name**: `portfolio` (또는 원하는 이름)
   - **Public** 선택 ← Pages 무료로 쓰려면 Public 필수
   - **Add a README file** 체크 해제 (아래에서 직접 올릴 거임)
3. **Create repository** 클릭

---

## 2단계 — 파일 5개 업로드

1. 방금 만든 repo 페이지에서 **"uploading an existing file"** 링크 클릭
2. `portfolio-cloud/` 폴더의 **모든 파일**을 드래그앤드롭:
   - `portfolio.json`
   - `generate.py`
   - `requirements.txt`
   - `.gitignore`
   - `.github/workflows/update.yml` ← **숨김 폴더**라 보일 수도 안 보일 수도. 안 보이면 폴더 채로 끌어다 놓으면 됨
3. 아래 **Commit changes** 클릭

---

## 3단계 — GitHub Pages 켜기

1. repo의 **Settings** 탭 → 왼쪽 메뉴 **Pages**
2. **Source**: `Deploy from a branch` 선택
3. **Branch**: `main` / `/ (root)` 선택 → **Save**
4. 1-2분 기다리면 상단에 **"Your site is live at https://USERNAME.github.io/portfolio/"** 떠야 함
5. 이게 모임에 공유할 **고정 URL**

---

## 4단계 — Actions 권한 확인

1. **Settings** → 왼쪽 **Actions** → **General**
2. 아래 **Workflow permissions** 섹션:
   - **Read and write permissions** 선택
   - **Save** 클릭

이거 안 하면 자동 commit이 권한 없어서 실패함.

---

## 5단계 — 첫 실행 (지금 바로 작동 확인)

1. **Actions** 탭 클릭
2. 왼쪽 **Weekly Portfolio Update** 선택
3. 우측 **Run workflow** → **Run workflow** 버튼
4. 30초~1분 기다리면 ✅ 초록 체크 → repo에 `index.html`이 생겨있어야 함
5. https://USERNAME.github.io/portfolio/ 접속 → 카드 보여야 정상

---

## 끝. 이제부턴 자동.

- **매주 월요일 9AM KST** GitHub가 알아서 시세 가져와서 페이지 갱신
- 본인 PC 꺼져 있어도 됨
- 모임방에 URL 한 번만 공지: *"항상 최신: https://USERNAME.github.io/portfolio/"*

---

## 멤버가 새로 매수했을 때

`portfolio.json`만 수정하면 즉시 갱신됨.

1. repo에서 `portfolio.json` 클릭 → 우측 연필(✏️) 아이콘
2. 해당 멤버의 `qty`, `avg_price`, `buy_amount` 수정
3. 아래 **Commit changes** → Actions가 자동 실행되어 페이지 갱신

---

## 트러블슈팅

**Q. URL 접속하면 404 뜸**
→ Pages 활성화 후 첫 빌드까지 2-3분. 좀 기다려.

**Q. Actions가 빨간 X로 실패**
→ Actions 탭에서 클릭하면 에러 보임. 보통 4단계 권한 누락. `Read and write permissions` 확인.

**Q. 시세가 안 맞음**
→ yfinance 무료 데이터라 가끔 지연. 종가 기준이라 장중엔 전일 종가 보일 수 있음.

**Q. 종목 자체를 바꾸고 싶음 (예: 필○이 카카오 → 삼성전자로 갈아탐)**
→ `portfolio.json`에서 해당 라인의 `stock`/`code`/`market` 수정. `market`은 KOSPI=`KS`, KOSDAQ=`KQ`.

---

## 비용

- GitHub Pages: **무료** (Public repo면)
- GitHub Actions: **무료** (Public repo는 무제한, 매주 1분 × 4 = 월 4분 사용)
- yfinance: **무료**

**총 운영비: 0원/월**
