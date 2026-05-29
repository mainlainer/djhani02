# 핸드오프 — 주간 결산 카카오톡 자동 알림

> 작성: 2026-05-29 / 상태: **미착수 (다음 세션에서 이어서)**

## 목표
매주 월요일 포트폴리오 갱신 후, **주간 순위 결산을 카카오톡으로 자동 전송**.

## 결정사항 & 핵심 제약 (중요)
- 사용자가 **카카오톡** 채널로 보내기를 선택함.
- ⚠️ **카카오 공식 API로는 임의의 단톡방에 봇이 글을 못 쏜다** (스팸 방지 정책).
  - 가능한 것: **"나에게 보내기"**(카카오톡 메모 API) → 내 카톡으로만 자동 전송.
  - 따라서 현실적 방식 = **자동으로 내 카톡에 전송 → 내가 단톡방에 수동 공유(전달)**.
- (대안) 진짜 단톡방 자동 전송이 꼭 필요하면 텔레그램/디스코드/슬랙으로 변경해야 함.
  다음 세션 시작 시 이 한계를 한 번 더 확인받을 것.

## 구현 방식 (카카오 "나에게 보내기")
### 1. 카카오 개발자 준비 (사용자 직접, 1회)
- https://developers.kakao.com 에서 앱 생성.
- **카카오 로그인** 활성화 + 동의항목에서 **"카카오톡 메시지 전송(talk_message)"** scope 추가.
- OAuth로 **access token + refresh token** 발급 (Redirect URI 등록 필요).
  - access token 만료 짧음 → 매 실행 시 **refresh token으로 재발급**해야 함.
  - refresh token은 약 2개월 유효(사용 시 갱신될 수 있음).

### 2. 전송 API
```
POST https://kapi.kakao.com/v2/api/talk/memo/default/send
Authorization: Bearer {access_token}
body: template_object={text 템플릿 JSON}
```
- 토큰 재발급: `POST https://kauth.kakao.com/oauth/token`
  (grant_type=refresh_token, client_id=REST_API_KEY, refresh_token=...)

### 3. 새 스크립트 `kakao_notify.py` (작성 예정)
- `history.json`(최신 스냅샷 + 직전 주 대비 변동) + `portfolio.json`/시세로 메시지 본문 생성.
  - 순위 계산/변동 로직은 `generate.py`의 `build_rows`, `_delta_html`, `update_history` 재사용 가능.
- refresh token으로 access token 재발급 → 메모 API 호출.
- 메시지 예시:
  ```
  📊 우리 모임 주간 결산 (5/29)
  총 손익 +243,347원 (+XX%)

  🏆 이번 주 순위
  1 현대차 +152% (▲1)
  2 신세계 +104% (NEW)
  ...
  👉 https://mainlainer.github.io/djhani02/rank.html
  ```

### 4. GitHub Actions 연결
- `.github/workflows/update.yml`의 generate 단계 **이후**에 전송 스텝 추가
  (또는 별도 workflow). generate.py가 history.json을 갱신한 뒤 실행되어야 함.
- 필요한 **GitHub Secrets**:
  - `KAKAO_REST_API_KEY`
  - `KAKAO_REFRESH_TOKEN`
- 주의: refresh token이 만료/회전되면 갱신된 값을 Secret에 다시 저장해야 함
  (Actions에서 Secret 자동 갱신은 안 되므로, 재발급 시 워크플로 로그로 경고만 남기는 방안 고려).

## 다음 세션 TODO 체크리스트
- [ ] 사용자에게 "내 카톡 자동전송 + 단톡방 수동공유" 방식 OK인지 재확인 (아니면 텔레그램으로 전환)
- [ ] 카카오 앱/토큰 발급 (사용자) → REST_API_KEY, REFRESH_TOKEN 확보
- [ ] `kakao_notify.py` 작성 (history.json 기반 메시지 빌드 + 토큰 재발급 + 전송)
- [ ] GitHub Secrets 등록
- [ ] update.yml에 전송 스텝 추가
- [ ] 수동 트리거(workflow_dispatch)로 1회 테스트

## 참고 파일
- `generate.py` — 순위/변동 로직, history.json 누적 (`update_history`, `_delta_html`, `build_rows`)
- `history.json` — 주차 스냅샷 (메시지 데이터 소스)
- `.github/workflows/update.yml` — 매주 월 09:00 KST 실행
