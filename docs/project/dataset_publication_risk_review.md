# 데이터셋 논문 투고 — 시비 리스크 검토의견

> **목적.** 본 프로젝트 데이터셋을 이용한 학술 논문 작성 시 발생 가능한
> 데이터셋 관련 시비(법률·윤리·방법론·재현성)를 사전 식별하고 완화책을 고정.
> **범위 한정.** 학술·방법론·라이선스 **리스크 평가**이며 **법률 자문이 아니다**.
> KIPRIS/KIPO 항목은 [dataset_rejected_patents_card.md](../dataset_rejected_patents_card.md)
> §6에 명시된 대로 SKKU 산학협력단·법무팀 자문 사안이다.
> **작성.** 2026-05-17 · lab-internal · 근거: 저장소 직접 검증(아래 각 항목 evidence).

---

## 0-0. 2026-08-09 재판정 — 전제 셋이 바뀌었다 (CR-015 §3 (6))

**이 문서의 본문은 2026-05-17 판단이고 고치지 않는다.** 아래는 그 위에 얹는 재판정이다 —
근거가 바뀐 항목만 상태를 옮기고, 판단의 출처를 지우지 않는다.

| | 2026-05-17 전제 | 2026-08-09 실제 |
|---|---|---|
| 논문 구성 | **방법론 트랙 먼저 · 데이터셋 트랙 분리**(§0·§3 권고) | **단일 논문**(AEI · 설계과학). 데이터셋 트랙 분리는 없다 — 데이터셋은 산출물의 일부로 함께 나간다 |
| §6 라이선스 | SKKU 산학협력단·법무팀 **자문 대기** | **자문을 이 경로에서 제외**하고 **(B) 확정**. 결정은 이미 원고 §10.3 에 있었다 — 리포를 그 문장에 맞추는 것은 법적 판단이 아니라 정합성 작업이다 |
| 공개 형태 | 미정 | **공개본은 별도 트리**(생성기 + 푸시 전 검사기) · **새 리포에 orphan 루트 1개** |

**체크리스트 재판정(§4).** 9항 중 **6항이 닫혔고 3항은 열려 있으며, 열린 셋은 전부
원고 쪽 소관**이다 — 이 저장소가 더 할 수 있는 일이 없다는 뜻이지 무시한다는 뜻이 아니다.

| # | 2026-08-09 상태 | 근거 |
|---|---|---|
| **#1** KIPRIS | ✅ **닫힘** — 자문 대기가 아니라 **(B) 확정**. 공개본 생성기·재인출 스크립트·검사기가 실물로 있다 | card §6 · `build_public_release.py` · `refetch_rejected_patents.py` · `check_public_release.py`(실측 적중 **0**) |
| **#2** 합성 ≠ 전문가 | ✅ **닫힘** — 이 항목이 "문서 측 반영 ✅" 라 적어 놓고 **미체크로 남아 있던 것은 표기 오류**였다. 금지 서술의 대상 문서 셋(card §5-2·§7-1 · datasheet §8 · README)에 전부 반영돼 있고, 원고도 3-rater 를 전문가 평가로 서술하지 않는다 | card §5-2 · README 결손 표("**synthetic**, generated for method evaluation") |
| **#3** 수치 일관성 | ✅ 닫힘(2026-05-17 · `46230c6`) | 본문 그대로 |
| **#4** 순환성 | ⏳ **원고 소관** — examiner-grounded 를 주 평가축으로 두는 서술은 원고에 있다. 이 저장소에서 닫을 항목이 아니다 | — |
| **#5** 혼합 라이선스 | ✅ **닫힘** — README "Curation sources" 표가 원천별 라이선스를 명시한다(Wikidata CC0 등) · SHACL 이 `dcterms:license` 를 요구한다 | README:170 · README:151 |
| **#6** 합성 전문가/IRB | ⏳ **원고·기관 소관** — 프로필은 합성이고 개인정보가 없다(README 결손 표에 명시). IRB 면제 확인과 실명 자문가 동의는 저장소 밖 절차다 | `docs/deidentification_protocol.md` |
| **#7** 누수 평가 | ✅ **닫힘 — 다만 위치가 바뀌었다.** 이 저장소의 `leakage_protocol.md` 는 여전히 설계뿐이지만, **누수 측정은 하류 논문 저장소에서 실제로 수행됐다**(`make leakage` · 금지 간선 0). 이 저장소가 "미측정"을 주장할 근거가 사라졌다 | 하류 CR-008 §④ 회신 |
| **#8** Dual-use | ⏳ **원고 소관** — Broader-Impact 문단은 원고에 쓴다 | — |
| 익명 스냅샷 | ✅ **해소 — 필요 없어졌다.** 더블블라인드 익명 스냅샷은 **데이터셋 트랙 분리**를 전제한 워크플로우였다. 단일 논문 경로에서는 공개본 릴리스 하나로 갈음된다 | 위 전제 표 |

**남은 게이트는 하나다 — 공개 리포를 만들고 태그·DOI 를 원고 §10 에 기입하는 것.**
그것은 리스크가 아니라 절차이며, 이 문서가 아니라 CR-015 §5 · CR-016 §5 가 추적한다.

---

## 0. 한 줄 결론

KIPRIS 라이선스 미해결(#1) + 합성 평점의 표현 정밀성(#2) + 수치 비일관(#3)이
**투고 전 게이트**다. **방법론 트랙(온톨로지 큐레이션·provenance·정합)으로
먼저 투고**하고 데이터셋 트랙은 #1 해결 후로 분리하는 것이 현 자산 기준 가장
안전한 1차 경로다.

## 1. 리스크 매트릭스 (심각도 순)

| # | 시비 영역 | 심각도 | 근거(evidence) | 핵심 위험 |
|---|---|---|---|---|
| 1 | KIPRIS/KIPO 특허데이터 라이선스·재배포 | 🔴 Critical | card §6 — 라이선스 미해결, (A)/(B)/(C) 분기, jsonl abstract/claim1 "보류" 승계 | 데이터 공개 가능성 자체 미확정 → 데이터셋 논문 투고 차단 |
| 2 | 합성 평점을 '전문가 평점'으로 오기 | 🔴 Critical | v2 §9.3 "전문가 3인 교차평가 7,500" vs 실제 examiner-grounded 7,500(객관) + `curated_ratings_3rater.csv` 7,800(**합성 crowd**, script docstring "synthetic crowd labels") | 인간 전문가 주석으로 서술 시 데이터 조작·허위표시(retraction급) |
| 3 | 계획-산출물 불일치·수치 비일관 | 🟠 High | 773 vs 1,000 / 198·264 vs 229·268 / weighted κ 0.550<0.60 게이트 / "46/46" vs 실제 24 fail | 재현성·신뢰성 공격 표면 |
| 4 | 합성 데이터 순환성·구성타당도 | 🟠 High | 합성 전문가(gen_experts.py) + 합성 3-rater | "LLM이 만든 정답으로 LLM 평가" 비판 |
| 5 | CC-BY-4.0 혼합 라이선스 attribution / CDLA 호환 | 🟡 Medium | provenance_sources 13종(SemicONTO/MatKG CC-BY-4.0, SemiKong **Apache-2.0**, Wikidata CC0) | attribution 누락·혼합 조건 위반 |
| 6 | 합성 전문가 — 실재 파생 아님 입증·IRB/PIPA | 🟡 Medium | gen_experts.py "de-identified synthetic, deterministic SEED, not real PII" | 입증책임 + 자문 전문가 실명 동의 |
| 7 | 누수(leakage) 평가 미완 | 🟡 Medium | leakage_protocol.md **v0.1 draft**, target은 2026-2 알고리즘 단계 | 미측정 leakage 결과 주장 |
| 8 | Dual-use / 수출통제 메타데이터 공개 | 🟢 Low-Med | BIS§744.23·산업기술보호법·ECHA SCIP 임계값 코드화 | 윤리위·리뷰어 dual-use 질의 |

## 2. 항목별 완화 조치

### #1 KIPRIS/KIPO (Critical — 투고 전 해결 필수)
보수적 조치는 이미 적용됨(외부 특허 본문 공개 제외, 거절결정서 OCR excerpt
스크럽, 구조화 GT만 유지 — card §6 2026-05-17 항목). **잔여**: jsonl
abstract/claim1 "보류". 데이터셋 논문이라면 **§6 (B)를 기본값으로 확정**
(본문 Link-Only, 메타+`ground_truth_*`만 공개) + 재현용 재인출 스크립트 제공.
법무 자문 결과를 **투고 시점에 문서화**. 미해결 상태로 데이터셋 트랙 투고 금지.

### #2 합성 vs 전문가 (Critical — 표현 정밀성)
- **금지**: 합성 3-rater(`curated_ratings_3rater.csv`)를 "expert/도메인 전문가
  평가"로 서술.
- **정확한 framing**: 1차 GT = examiner-grounded 7,500(KIPO 심사관 인용,
  datasheet "examiner records, not crowd"); 합성 3-rater 7,800 = **보조 일관성
  레이어, 알고리즘 시뮬레이션** — 생성 절차·모델·시드 명시. 전문가는 *프로필
  설계 자문*(expert_validation_log)에만 참여, 7,500 평점 미산출. 이 구분을
  본문·datasheet·card에 명문화. → datasheet §8 / card §5-2·§7 보강 완료.

### #3 수치 일관성 (High — 저비용·치명적)
투고 전 **단일 검증 스냅샷 고정** 후 전 수치를 논문·README·CHANGELOG·card·
datasheet에 **일괄 동기화**: 노드 **229 / 엣지 268**, SIRP **1,000**,
weighted κ **0.550** / ICC(2,k) **0.787** / (투명성) Fleiss κ 0.258 ·
ICC(2,1) 0.552. `test_owl` 24 fail은 `make build-owl` 재생성으로 해소 후
"SHACL PASS + N/N tests" 정확 기재. (상세: [project_status_2026_1.md](project_status_2026_1.md)
§0-1·§6·§10, [reliability_report.md](../../data/experts/reliability_report.md))

### #4 순환성 (High — 방법론 방어)
examiner-grounded 트랙을 **주 평가축**으로 전면 배치. 합성 트랙은 보조·한계
명시. 합성 평점 weighted κ=0.55(moderate)·dominant prevalence 0.539를
Limitations에 정직 보고. "합성 정답 구성타당도 한계 → 후속 인간 검증" 선언.

### #5 혼합 라이선스 (Medium)
릴리스에 `provenance_sources` license/author 보존 검증(13종 기재 — 양호).
CC-BY-4.0(SemicONTO/MatKG) attribution을 README/datasheet에 명시. SemiKong은
**Apache-2.0**(MIT 아님) — 레지스트리 일치 유지.

### #6 합성 전문가/IRB (Medium)
논문에 **IRB 면제 사유 명문**(합성·비식별·실재 미파생·deterministic) +
생성 방법론(아키타입·시드·거절률 캘리브레이션). 자문 전문가 실명(예: 김범수)
언급 시 사전 동의·감사표기 확보.

### #7 누수 평가 (Medium)
leakage는 v0.1 **설계만** 완료. 논문에 측정 수치 주장 금지. "프로토콜 제시,
정량 평가는 2026-2 알고리즘 단계"로 기여 범위 한정. → card §7 보강 완료.

### #8 Dual-use (Low-Med)
윤리/Broader-Impact 1문단: "공개 규제 텍스트(EAR/CCL·산업기술보호법·SCIP)의
**메타데이터 구조화**이며 수출통제 기술 사양 자체 미포함" 명시.

## 3. 권고 투고 전략

| 트랙 | #1 노출 | 권고 |
|---|---|---|
| **방법론**(온톨로지 큐레이션·PROV-O·SHACL·이종정합) | 낮음 | **1차 투고 권장** — IP&M/Scientometrics. 데이터는 방법 예시로만 인용, examiner-grounded 주축, #2·#3·#4를 정직 한계로 |
| **데이터셋 리소스**(SIRP/SDKB 공개) | 높음 | #1 법무 확정 후로 분리. NeurIPS D&B 등은 datasheet·라이선스 엄격 |

## 4. 투고 전 체크리스트

- [ ] #1 KIPRIS 법무 자문 결과 문서화 + §6(B) 확정 (데이터셋 트랙 한정 게이트)
- [ ] #2 본문·datasheet·card에서 합성 3-rater ≠ 전문가 명문화 (✅ 문서 측 반영)
- [x] #3 단일 스냅샷 수치 일괄 동기화 (2026-05-17 완료, 커밋 46230c6) + `test_owl` 해소 (`make owl` → 75 passed/10 skipped/0 failed)
- [ ] #4 examiner-grounded 주축 + 합성 한계 Limitations 명문
- [ ] #5 CC-BY attribution README/datasheet 명시
- [ ] #6 IRB 면제 + 생성방법론 + 실명 자문가 동의
- [ ] #7 leakage = 프로토콜만, 미측정 명시 (✅ card 반영)
- [ ] #8 dual-use/Broader-Impact 문단
- [ ] 익명 스냅샷(더블블라인드) + 원본 비공개(선행공개) — 별도 워크플로우 진행 중

### 4-1. 익명 스냅샷 제외 목록 (lab-internal·독점·식별 문서)

스냅샷 재빌드 시 rsync `--exclude` 고정 (제출 직전 재빌드 필수):
`.git/ .venv/ site/ .env *.pdf CITATION.cff` +
`docs/project/project_status_2026_1.md`, `docs/project/plan_amendment_v{1,2,3}.md`,
`docs/project/architecture_amendment_sdkb_centric.md`, `docs/expert_validation_log.md`,
`docs/project/feedback/`, `docs/project/dataset_publication_risk_review.md`,
`docs/project/plan_amendment_v3_bis.md`,
**`docs/project/commercialization_strategy_v1.md`** (2026-05-17 추가 — 실제 ARKWITH
IPBridge 시장·가격·로드맵 독점정보로 재작성됨).

## 5. 관련 문서

- [project_status_2026_1.md](project_status_2026_1.md) §0 점검 분석 / §0-1 갭 / §10 후속
- [dataset_rejected_patents_card.md](../dataset_rejected_patents_card.md) §6 라이선스
- [datasheet.md](../datasheet.md) §8 publication-integrity notes
- [reliability_report.md](../../data/experts/reliability_report.md) κ/ICC 측정 정합
- [leakage_protocol.md](../leakage_protocol.md) v0.1
