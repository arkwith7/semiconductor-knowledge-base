# Commercialization Strategy v1 (Deliverable ⑤)

> v0.1 skeleton — 2026-05-12. **To be completed in W6 (2026-06-16–22).** Each section is sized to the depth that satisfies the signed plan + Amendment v2.

## 1. Executive summary
*(W6 final)*
- 한 문단: 시장 기회, 우리가 가진 데이터 자산(SDKB + SIRP), 첫 6개월 사업화 가설.

## 2. Problem & opportunity (W1 source — original plan §3)

### 2.1 Macro driver
- 숙련 엔지니어 은퇴 가속 → 암묵지 단절
- 소부장 SME의 정보 비대칭
- 다중 관할 수출통제 강화 (EAR + 산업기술보호법)

### 2.2 What current services miss
- 컴플라이언스를 사후 필터로 처리 → 구조적 누수
- IP-R&D와 인력 매칭이 분리되어 있음
- 감사가능성(auditability) 부재

## 3. Solution — AFCP-EM (dual track)

| Track | Customer | Pain | Our edge |
|---|---|---|---|
| **AFCP-EM-Expert** | 소부장 SME, 컨설팅 | 적합 전문가를 찾을 역량 부족 | SDKB+합성 100 + 도메인 자문 + 컴플라이언스 게이트 |
| **AFCP-EM-PriorArt** | 변리사, 기업 IP 부서 | 다국가 선행기술 누락 | SIRP 773 + examiner-grounded 7,500 평가 + 다중관할 게이트 |

## 4. Market sizing (W6 — 정량)

### 4.1 TAM / SAM / SOM — Expert track
- TAM (글로벌 반도체 전문가 매칭 시장): *(채울 수치 + 출처)*
- SAM (한국 소부장 SME 매칭): *(채울 수치)*
- SOM (초기 3년): *(채울 수치)*

### 4.2 TAM / SAM / SOM — PriorArt track
- TAM (글로벌 IP-R&D / 선행기술조사 시장): *(채울 수치)*
- SAM (국내 변리사·기업 IP 부서): *(채울 수치)*
- SOM: *(채울 수치)*

### 4.3 Method note
- 수치 산출 근거: KISTEP/KIAT 통계 + 변리사회 통계 + IP-R&D 시장 보고서

## 5. Target customers / personas (W6)
- **소부장 SME 기획팀** — 30–300명 규모, R&D 인력 부족, 외주 컨설팅 빈도 ≥ 2회/년
- **변리사 사무소** — 5–50인, 반도체 출원·심사대응 전문, 다국가 사건 비율 ≥ 30%
- **대기업 IP 부서** — 사내 선행기술조사 수요 연 N건 이상

## 6. Resource view (RBV anchor)

| Resource | VRIO | We own? | Path |
|---|---|---|---|
| SDKB 그래프 | V/R/I/O | ✅ | 본 프로젝트 |
| SIRP examiner GT | V/R/-/-  | ✅ | SIRP 통합 |
| 다중관할 컴플라이언스 게이트 | V/R/I/-  | 부분 | sdkb-governance-kr + SHACL |
| 도메인 전문가 자문 네트워크 | V/-/I/-  | 부분 | 자문 로그 |
| 변리사·법무 자문 | V/-/-/-  | 미보유 | 파트너십 필요 |

## 7. Revenue model (W6)
- Option A — Subscription (SaaS): 월 정액 × 좌석 / 쿼리 쿼터
- Option B — Per-engagement: 매칭 1건 당 수수료 (Expert는 채용 성사 시 %, PriorArt는 보고서 패키지 단가)
- Option C — Hybrid (권장): 기본 SaaS + 고가 사례 per-engagement
- 가격 가설 — 30% 탐색비용 절감 약속에 부합하도록 역산 (업체당 연 5,000만원 절감 → 가격 임계)

## 8. Competitive landscape (W6)
- Expert: 사람인/잡코리아 (도메인 깊이 부족), LinkedIn (한국 SME 미매칭), 컨설팅펌
- PriorArt: WIPS, KIPRIS, IP-NEX, Cipher (이중관할 게이트 부재)
- 차별점: SDKB+SIRP, 다중관할 게이트, PROV-O 감사가능성

## 9. Go-to-market (W6)
- Phase 1 (2027-1): SKKU MOT 인력양성 사업 + 인근 소부장 SME 파일럿 3사
- Phase 2: 변리사회·KIAT 협력 → PriorArt 트랙 베타
- Phase 3: 정식 출시

## 10. Risks
- KIPRIS 라이선스 제약 — `dataset_rejected_patents_card.md` §6 의 3-option 분기에 따라 시나리오별 사업화 가능성 재산정.
- 컴플라이언스 규정 변동 — 월간 갱신 파이프라인으로 대응.
- 합성 평가의 외부타당성 — 부분 인간 검증 + examiner GT로 보강.

## 11. Funding ask & next-step asks (W6)
*(공란 — 신 교수 미팅 시 토의)*

---

### W6 작성자 체크리스트
- [ ] 4.1, 4.2 수치 채우기 (KISTEP·변리사회 출처 명시)
- [ ] 6 표 모든 행 채우기
- [ ] 7 가격 임계 정량 계산
- [ ] 8 경쟁사 표에 각 1줄 근거 명시
- [ ] 11 펀딩·다음 단계 합의
