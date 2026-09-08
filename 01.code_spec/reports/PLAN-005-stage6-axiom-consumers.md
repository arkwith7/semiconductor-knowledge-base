# PLAN-005 단계 6-A — 공리↔소비자 대조표 (V1 절제 · 기계 산출)

> 생성: `scripts/report_v1_ablation.py` · 2026-09-08 · **손으로 고치지 않는다** — `make v1-ablation` 이 다시 만든다. 정의는 스크립트 docstring, 예측은 `FROZEN` 표.

**결론.** 공리 37건 중 소비 **8** · 미소비 29. pa: 모듈의 R-Box 미소비: 12건. 예측 불일치: 0건.

| 기준선 | 값 |
|---|---:|
| CQ 수 / 행 합 | 32 / 9670 |
| CQ32 행 (LIMIT 200) | 200 |
| coveredBy 쌍 (술어별) | 16 {'exactMatch': 0, 'broaderConcept': 16, 'substitutableWith': 0} |
| 바인딩 개념 / 클래스 | 147 / 11 |
| ④ (p,u) / (p,d,u) | 4,306 / 40,024,841 |

| # | 공리 | 모듈 | 종류 | 역할 | ② CQ 변화 | ③ coveredBy Δ · bound Δ | ④ (p,u) Δ | 경로 | 유량 | 예측 | 제안 | 사유 |
|---:|---|---|---|---|---|---|---:|:-:|:-:|:-:|---|---|
| 1 | `legacy:core:TransitiveProperty:ont:hasSubStep` | legacy:core | TransitiveProperty | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (§7-2 · 하류 핀) | 단계 1 재현 · legacy T-Box 는 제자리 불변 · sdkb-patent.ttl 0a317389… 핀 |
| 2 | `legacy:core:equivalentClass:ont:Dopant→_:bnode` | legacy:core | equivalentClass | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (§7-2 · 하류 핀) | 단계 1 재현 · legacy T-Box 는 제자리 불변 · sdkb-patent.ttl 0a317389… 핀 |
| 3 | `legacy:patent:TransitiveProperty:ont:broaderClassification` | legacy:patent | TransitiveProperty | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (§7-2 · 하류 핀) | 단계 1 재현 · legacy T-Box 는 제자리 불변 · sdkb-patent.ttl 0a317389… 핀 |
| 4 | `legacy:patent:subPropertyOf:ont:hasCPC→ont:hasClassification` | legacy:patent | subPropertyOf | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (§7-2 · 하류 핀) | 단계 1 재현 · legacy T-Box 는 제자리 불변 · sdkb-patent.ttl 0a317389… 핀 |
| 5 | `legacy:patent:subPropertyOf:ont:hasFTerm→ont:hasClassification` | legacy:patent | subPropertyOf | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (§7-2 · 하류 핀) | 단계 1 재현 · legacy T-Box 는 제자리 불변 · sdkb-patent.ttl 0a317389… 핀 |
| 6 | `legacy:patent:subPropertyOf:ont:hasIPC→ont:hasClassification` | legacy:patent | subPropertyOf | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (§7-2 · 하류 핀) | 단계 1 재현 · legacy T-Box 는 제자리 불변 · sdkb-patent.ttl 0a317389… 핀 |
| 7 | `legacy:patent:subPropertyOf:ont:hasPriorArtApplicant→ont:hasPriorArt` | legacy:patent | subPropertyOf | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (§7-2 · 하류 핀) | 단계 1 재현 · legacy T-Box 는 제자리 불변 · sdkb-patent.ttl 0a317389… 핀 |
| 8 | `legacy:patent:subPropertyOf:ont:hasPriorArtExaminer→ont:hasPriorArt` | legacy:patent | subPropertyOf | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (§7-2 · 하류 핀) | 단계 1 재현 · legacy T-Box 는 제자리 불변 · sdkb-patent.ttl 0a317389… 핀 |
| 9 | `core:TransitiveProperty:pa:broaderConcept` | core | TransitiveProperty | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 삭제 (6-B) | skos:broader 18쌍 중 길이-2 사슬 0 · 전이는 동결 깊이 {0,1}(§3.3) 과 모순 |
| 10 | `core:SymmetricProperty:pa:substitutableWith` | core | SymmetricProperty | rbox | — | +0 · +0 | +0 | ✓ | — | 미소비 | 보존 + 일몰 (D2) | 경로 有(생성기가 읽음) · 유량 0 — PLAN-002 채굴 쌍 없음 · 단계 7 착수까지 Prec 미착수면 삭제 |
| 11 | `core:subPropertyOf:skos:exactMatch→pa:coveredBy` | core | subPropertyOf | rbox | — | +0 · +0 | +0 | ✓ | — | 미소비 | 삭제 (6-B) | 유량 0 (core-data exactMatch 0) · 가능한 유량은 클래스 정렬 23 + LegalGround 2 = 오염뿐 |
| 12 | `core:subPropertyOf:pa:broaderConcept→pa:coveredBy` | core | subPropertyOf | rbox | — | -16 · +0 | -4306 | ✓ | ✓ | 소비 | 유지 | 생성기가 읽어 coveredBy 16쌍 실체화 · ④ 4,306 쌍이 이 공리에 걸린다 |
| 13 | `core:subPropertyOf:pa:substitutableWith→pa:coveredBy` | core | subPropertyOf | rbox | — | +0 · +0 | +0 | ✓ | — | 미소비 | 보존 + 일몰 (D2) | 경로 有(생성기가 읽음) · 유량 0 — PLAN-002 채굴 쌍 없음 · 단계 7 착수까지 Prec 미착수면 삭제 |
| 14 | `core:inverseOf:pa:conceptOfFeature→pa:featureConcept` | core | inverseOf | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 삭제 (6-B · 술어 포함) | 역술어를 읽는 소비자 없음 — run_cq 무추론 · SHACL inference none |
| 15 | `semi:subPropertyOf:ont:aboutClaim→pa:concernsClaim` | semi | subPropertyOf | binding-property | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (바인딩 재분류) | V6b 이식용 슬롯 바인딩 — R-Box 가 아니라 subClassOf 11건과 같은 급 |
| 16 | `semi:subPropertyOf:ont:featureConcept→pa:featureConcept` | semi | subPropertyOf | binding-property | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (바인딩 재분류) | V6b 이식용 슬롯 바인딩 — R-Box 가 아니라 subClassOf 11건과 같은 급 |
| 17 | `semi:subPropertyOf:ont:onGround→pa:onGround` | semi | subPropertyOf | binding-property | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (바인딩 재분류) | V6b 이식용 슬롯 바인딩 — R-Box 가 아니라 subClassOf 11건과 같은 급 |
| 18 | `semi:inverseOf:ont:claimOf→ont:hasClaim` | semi | inverseOf | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 삭제 (6-B · 술어 포함) | 역술어를 읽는 소비자 없음 — run_cq 무추론 · SHACL inference none |
| 19 | `semi:inverseOf:ont:featureOf→ont:hasFeature` | semi | inverseOf | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 삭제 (6-B · 술어 포함) | 역술어를 읽는 소비자 없음 — run_cq 무추론 · SHACL inference none |
| 20 | `semi:disjointWith:ont:StructuralElement→ont:Material` | semi | disjointWith | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 불변식 C 신설 (D3) | 현 파이프라인에 소비자 없음 → 6-B 가 배제쌍 동시 타이핑 검사를 validate 에 배선 |
| 21 | `semi:disjointWith:ont:StructuralElement→ont:Process` | semi | disjointWith | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 불변식 C 신설 (D3) | 현 파이프라인에 소비자 없음 → 6-B 가 배제쌍 동시 타이핑 검사를 validate 에 배선 |
| 22 | `semi:disjointWith:ont:TechnicalEffect→ont:StructuralElement` | semi | disjointWith | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 불변식 C 신설 (D3) | 현 파이프라인에 소비자 없음 → 6-B 가 배제쌍 동시 타이핑 검사를 validate 에 배선 |
| 23 | `semi:disjointWith:ont:TechnicalFunction→ont:StructuralElement` | semi | disjointWith | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 불변식 C 신설 (D3) | 현 파이프라인에 소비자 없음 → 6-B 가 배제쌍 동시 타이핑 검사를 validate 에 배선 |
| 24 | `semi:subClassOf:ont:Device→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | +0 · -34 | +0 | ✓ | ✓ | 소비 | 보존 (바인딩) | 생성기 technical_concept_classes · SHACL sh:class 가 읽음 |
| 25 | `semi:subClassOf:ont:EquipmentClass→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | +0 · -12 | +0 | ✓ | ✓ | 소비 | 보존 (바인딩) | 생성기 technical_concept_classes · SHACL sh:class 가 읽음 |
| 26 | `semi:subClassOf:ont:Material→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | -15 · -31 | -3945 | ✓ | ✓ | 소비 | 보존 (바인딩) | 생성기 technical_concept_classes · SHACL sh:class 가 읽음 |
| 27 | `semi:subClassOf:ont:Parameter→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | +0 · -5 | +0 | ✓ | ✓ | 소비 | 보존 (바인딩) | 생성기 technical_concept_classes · SHACL sh:class 가 읽음 |
| 28 | `semi:subClassOf:ont:Problem→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | +0 · +0 | +0 | ✓ | — | 미소비 | 보존 (바인딩 · 인스턴스 대기) | 경로 有 · core-data 인스턴스 0 이라 유량 0 |
| 29 | `semi:subClassOf:ont:Process→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | -1 · -12 | -361 | ✓ | ✓ | 소비 | 보존 (바인딩) | 생성기 technical_concept_classes · SHACL sh:class 가 읽음 |
| 30 | `semi:subClassOf:ont:ProcessCondition→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | +0 · +0 | +0 | ✓ | — | 미소비 | 보존 (바인딩 · 인스턴스 대기) | 경로 有 · core-data 인스턴스 0 이라 유량 0 |
| 31 | `semi:subClassOf:ont:StructuralElement→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | +0 · -15 | +0 | ✓ | ✓ | 소비 | 보존 (바인딩) | 생성기 technical_concept_classes · SHACL sh:class 가 읽음 |
| 32 | `semi:subClassOf:ont:SubProcess→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | -1 · -38 | -361 | ✓ | ✓ | 소비 | 보존 (바인딩) | 생성기 technical_concept_classes · SHACL sh:class 가 읽음 |
| 33 | `semi:subClassOf:ont:TechnicalEffect→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | +0 · +0 | +0 | ✓ | — | 미소비 | 보존 (바인딩 · 인스턴스 대기) | 경로 有 · core-data 인스턴스 0 이라 유량 0 |
| 34 | `semi:subClassOf:ont:TechnicalFunction→pa:TechnicalConcept` | semi | subClassOf | binding-class | skip | +0 · +0 | +0 | ✓ | — | 미소비 | 보존 (바인딩 · 인스턴스 대기) | 경로 有 · core-data 인스턴스 0 이라 유량 0 |
| 35 | `kr:differentFrom:pa/kr:NoticeOfReasons→pa/kr:FinalRejection` | kr | differentFrom | rbox | — | +0 · +0 | +0 | — | — | 미소비 | 삭제 (6-B) | 개체 상이성을 읽는 소비자 없음 |
| 36 | `kr:exactMatch:pa/kr:Ground_29_1→ont:Rejection_Novelty` | kr | exactMatch | binding-match | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (크로스워크 바인딩) | C5 제거 후 R-Box 아님 · LegalGround↔RejectionType 해소 |
| 37 | `kr:exactMatch:pa/kr:Ground_29_2→ont:Rejection_Inventiveness` | kr | exactMatch | binding-match | — | +0 · +0 | +0 | — | — | 미소비 | 보존 (크로스워크 바인딩) | C5 제거 후 R-Box 아님 · LegalGround↔RejectionType 해소 |

## 한계

- ② 는 추론기 없는 rdflib 라 구조적으로 0 이다 — §5 문면대로 실행하되 판정은 ③④ 가 진다.
- ④ 는 프로파일·개시집합을 고정하고 coveredBy 만 바꾼다. 바인딩(subClassOf) 절제는 ③ 의 bound_concepts 로 검출하며 프로파일 재파생은 하지 않는다(생성기 재실행 30초 × 11).
- CQ32 는 LIMIT 200 포화라 행 수가 움직이지 않는다 — cq32_rows 는 기록용이다.
- legacy 8건은 §7-2·하류 핀(sdkb-patent.ttl 0a317389…)으로 삭제 대상이 아니다 — 결과와 무관하게.
