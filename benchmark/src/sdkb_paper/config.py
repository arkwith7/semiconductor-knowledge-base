"""프로젝트 공통 설정: 경로, 네임스페이스, 환경변수.

로컬에서는 .env, Colab에서는 Colab Secrets(userdata)를 사용한다.
"""
from __future__ import annotations

import os
from pathlib import Path

from rdflib import Namespace

# --- 경로 ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW_KIPRIS = DATA / "raw" / "kipris"
RAW_BQ = DATA / "raw" / "bigquery"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
SAMPLES = DATA / "samples"
EXTERNAL_SDKB = DATA / "external" / "sdkb"   # 근간 온톨로지 스냅샷 (vendor.py 가 채운다)
QUERIES_CQ = ROOT / "queries" / "cq"
QUERIES_SHAPES = ROOT / "queries" / "shapes"
# L1 은 두 겹이다. 그래프 전체(레거시 SIRP 포함)에는 완화 제약, 이 논문이 병합하는 델타에는
# 개념 매핑(Process ∪ Device) ≥1 을 요구하는 엄격 제약. 게이트는 델타를 검증하는 것이지
# 상류가 남긴 데이터를 소급 처벌하는 것이 아니다.
SHAPES_GRAPH = QUERIES_SHAPES / "graph"
SHAPES_DELTA = QUERIES_SHAPES / "delta"
MAPPINGS = ROOT / "mappings"
# IPC/CPC 접두어 -> SDKB 개념 IRI. 개념 축은 Process ∪ Device 이므로 공정 전용이 아니다 —
# axis 컬럼이 realizesProcess 와 concernsDevice 를 가른다.
CODE_MAPPING = MAPPINGS / "code_to_concept.csv"
# 신기술 인식 레이어 (PLAN-004). 신기술은 코드로도 이름으로도 잡히지 않는다 — GAA 전용 코드는
# 부여 0건이고, HBM 은 조합으로 잡히는 특허의 대다수가 명세에 이름을 쓰지 않는다.
# 두 파일은 **시계열을 보기 전에 동결**됐다 (외부 원천 = JEDEC · CPC 공식 스킴 원문).
TERM_ALIASES = MAPPINGS / "term_aliases.csv"          # 1층 · 별칭
EMERGING_CONCEPTS = MAPPINGS / "emerging_concepts.csv"  # 2층 · 조합 정의 (strict/base/loose)
SI_CONCEPTS = MAPPINGS / "si_concepts.csv"            # 분류체계 독립 정의 (PLAN-009 · 텍스트 전용)
DART_TERMS = MAPPINGS / "dart_terms.csv"     # DART 준거 용어 (PLAN-009 · 동결)
# H2′ 의 대조군: 기술의 **명칭** 키워드 (PLAN-010 · 동결). 명세 텍스트는 소급 재작성되지
# 않으므로 이 대조군은 **시점 유효**하다 — 분류코드가 무효였던 이유를 피해 간다.
NAME_BASELINE = MAPPINGS / "name_baseline.csv"
# H2 의 검증 사례 7건 (PLAN-006). 개념 시계열과 대조할 CPC 코드가 사례마다 하나씩 고정돼 있다.
# **시계열을 보기 전에 동결**됐다 — 사례 선정은 우리 데이터 분포가 아니라 SDKB 어휘 · CPC 공식
# 스킴 원문 · 외부 부상 근거(JEDEC 표준 · 양산 발표)만으로 이루어졌다. 커밋 해시가 사전등록이다.
H2_CASES = MAPPINGS / "h2_cases.csv"
# H1 의 두 번째 표본 집합: SemiKong Table 7 복원 **이전**의 공정 20개.
# 복원된 단계는 G₀ 에서 C₀(s)=0 이라 H1 에 유리하다 — 그 편향을 독자가 판별할 수 있도록
# 확장 49 와 병기 보고한다 (scripts/freeze_legacy_scope.py 가 커밋 스냅샷에서 생성).
LEGACY_SCOPE = MAPPINGS / "process_scope_legacy20.csv"
# C-2 소부장 G₂ (RQ3): KSIA 장비 94사 → 기존 G₀ organization 노드 크로스워크.
# 사전동결 CSV — 결과를 보기 전에 확정했다(h2_cases.csv 와 같은 규율). match_key 는 KIPRIS
# applicantName 정확일치 필터의 키다(clean.normalize_company_name 로 생성). 94사 전량이 기존
# G₀ 노드에 매핑되므로 신규 organization 노드는 만들지 않는다 — 정체성 재분열이 없다.
KSIA_CROSSWALK = MAPPINGS / "ksia_applicant_crosswalk.csv"
# v0.9 정본 산출물(C2 검색결과·C3 결함매트릭스)만 여기 쓴다.
FIGURES = ROOT / "paper" / "figures"
TABLES = ROOT / "paper" / "tables"

# S-시리즈(구 커버리지 S1·시계열 S2·이식성 S3) 산출물의 출력 경로.
# **왜 분리하는가.** 이 CLI 들(s1_coverage·s2_timeseries·ksia_strata·applicant·robustness)은
# 구 패러다임 표·그림을 만든다. 예전에는 v0.9 정본과 같은 `paper/{tables,figures}` 에 썼고,
# 그래서 `make s1` 한 번이면 구 패러다임 산출물이 v0.9 표 옆에 되살아났다(2026-07-31 실측:
# 표 10건·그림 4건 재오염). CLAUDE.md §0 S-시리즈 규약상 두 패러다임의 산출물은 섞이면 안 된다.
#
# **왜 `paper/archive/{tables,figures}` 가 아니라 `regenerated/` 인가.** 그쪽은 v0.5/v0.7 원고가
# 인용하는 **동결 기록**이다. 재계산 값으로 덮으면 "교정 전 상태"의 인용 가능성이 사라진다 —
# 실제로 `robustness_family_dedup.md`·`h2_census.md`·fig7/8/8b/8c 는 현행 코드 출력과 값이 다르다.
# 동결본은 보존하고, 재생성물은 여기로 격리해 **차이를 눈에 보이게** 둔다.
ARCHIVE_FIGURES = ROOT / "paper" / "archive" / "regenerated" / "figures"
ARCHIVE_TABLES = ROOT / "paper" / "archive" / "regenerated" / "tables"

# vendoring 원본. 스냅샷을 갱신할 때만 쓰인다 — 분석/게이트는 EXTERNAL_SDKB 만 본다.
SDKB_HOME = Path(os.environ.get("SDKB_HOME", Path.home() / "Dev" / "sdkb"))

# baseline: 보강 전 그래프 (H1 의 "before")
GRAPH_V0 = PROCESSED / "graph_v0.ttl"
# 보강 후 그래프 — 읽기 전용 소비자(explore 등)만 참조한다. 조립은 merge 가 한다.
GRAPH_V1 = PROCESSED / "graph_v1.ttl"  # G₁ 삼성·SK하이닉스 보강 후
GRAPH_V2 = PROCESSED / "graph_v2.ttl"  # G₂ KSIA 소부장 188사 보강 후

# 청구항 분해 중심축 데이터셋 (11.6M 트리플). 분석 그래프에 **병합하지 않는다** — H1 엣지
# 중립이고, rdflib 인메모리로 올리면 피크 15GB·4분이라 OOM 위험이다(실측 2026-07-23).
# pyoxigraph 온디스크 스토어로만 적재/질의한다. 소스는 상류 SDKB, 스토어는 여기서 결정적 재빌드.
CENTRAL_AXIS_SRC = SDKB_HOME / "ontology" / "sdkb-abox-claim-features.ttl"  # ABox 887MB
CENTRAL_AXIS_TBOX = SDKB_HOME / "ontology" / "sdkb-patent.ttl"              # 동반 TBox 22KB
CENTRAL_AXIS_STORE = PROCESSED / "central_axis.oxstore"                     # 온디스크 스토어(gitignore)
CENTRAL_AXIS_PROVENANCE = DATA / "external" / "sdkb-central-axis" / "PROVENANCE.json"  # 커밋 가능 핀

# --- IR 벤치마크 코퍼스 (v0.9 · PLAN-017 M1) ------------------------------
# 통합 문서 코퍼스와 심사관 qrel. 특허 전문(abstract/claim)을 담으므로 license_restricted →
# data/processed/* 는 gitignore, `make corpus` 로 로컬 재생성한다(CLAUDE.md §1.4·§1.5).
# 커밋되는 것은 프로파일(집계·서명)과 MANIFEST 뿐. 청구항 본문 = sidecar featureText 재구성이
# 정본, firstClaimText(원문 claim1) 병기 (PLAN-017 §7 M1 확정).
IR_DIR = PROCESSED / "ir"
IR_CORPUS = IR_DIR / "ir_corpus_v09.parquet"          # 통합 문서 코퍼스
QREL_EXAMINER = IR_DIR / "qrel_examiner.parquet"      # 심사관 인용 qrel (등급1)
IR_PROFILE = DATA / "profiles" / "ir_corpus_v09.md"   # §4 데이터 프로파일 (커밋 가능)

# --- IR 검색 하네스 (v0.9 · PLAN-018 계층 B) ------------------------------
# 색인·순위·산출물 경로. index/run 은 대용량·재생성 가능 → gitignore.
IR_INDEX_DIR = IR_DIR / "index"                        # Lucene(BM25) · FAISS 색인
IR_RUNS_DIR = IR_DIR / "runs"                          # 시스템별 순위 산출(run 파일)
IR_USERDICT = IR_DIR / "userdict_sdkb.txt"             # nori 사용자사전 (SDKB 어휘 시드 · F13)
# 개념→축(axis)·TBox 계층 지도 (M4 온톨로지팔 입력 · PLAN-018 §7.3 M4-3/M4-4). 벤더 TTL 의
# `a ont:X`·subClassOf 에서 결정적 추출 — 커밋 가능(집계·식별자·해시만). concept_axis.py 생성.
IR_CONCEPT_AXIS = IR_DIR / "concept_axis.parquet"
# 개념 적용기(linker) 감사 사이드카 (PLAN-034 · D-19). 문서×표면형×concept_id 링크 전량 —
# **접두어(축) 붙은 정본 concept_id 는 여기에만 있다**(코퍼스 concepts 열은 지역명만 보관).
# 재생성 가능 → gitignore. 코퍼스에 컬럼을 늘리지 않는 이유는 PLAN-034 §3.3 무작동 동치성.
IR_CONCEPT_LINKS = IR_DIR / "concept_links.parquet"
# 상류 CR-007 이 낸 개념 매핑 사전(벤더 스냅샷). 없으면 적용기는 무작동 — 그 상태가 O 팔이다.
SDKB_CONCEPT_MAP = EXTERNAL_SDKB / "concept_mapping.json"
# claim-feature sidecar (P1/P2 · PLAN-018 §7.5). central_axis.oxstore 에서 추출한 특허별 청구항 피처
# (doc_id·claim·is_independent·featureText·seq). **featureText=KIPRIS 원문 → gitignore·재생성**.
IR_FEATURE_SIDECAR = IR_DIR / "feature_sidecar.parquet"
# featureText Titan 임베딩 캐시(P1 FeatureCoverage). 텍스트해시→벡터 sqlite · gitignore.
IR_FEATURE_EMB_CACHE = IR_INDEX_DIR / "feature_titan_cache.sqlite"
# DOCDB family_id 지도 (B2 · F1 family-level 주지표). doc_id→family_id, raw(비커밋).
# 원천은 BigQuery patents-public-data — 공개번호/출원번호 조인. 미조인은 fallback=자기자신(비율 보고).
IR_FAMILY_MAP = RAW_BQ / "ir_family_map.parquet"
# Dense(B2 · F12 Titan Embed v2). 임베딩 캐시(텍스트해시→벡터)·FAISS flat 색인 · gitignore.
IR_DENSE_CACHE = IR_INDEX_DIR / "dense_titan_cache.sqlite"
IR_DENSE_DIM = 1024                                    # Titan v2 지원 256/512/1024 중 최대(동결)
# 거절근거 법조 라벨 (원고 §5.2·§6.4 하위집단 **전용** · 순위 입력 아님). vendor.py 가 상류
# rejected_patents_meta 에서 식별자+법조만 파생해 얼린다 — 원문 0열이라 커밋 가능.
# TTL 스냅샷은 §1×n|§2×m 을 Rejection_Inventiveness 하나로 접어 신규성 축을 잃는다(상류 결함).
REJECTION_BASIS = EXTERNAL_SDKB / "rejection_basis.csv"
# F11 어휘중첩 동결 임계(원고 §5.3). dev Q1 을 low-overlap 경계로 얼린 기록 — analysis/overlap.py.
IR_OVERLAP_THRESHOLD = IR_DIR / "overlap_threshold.json"
# 결정성 시드 (F16 사전등록): 분할·부트스트랩·hard-neg 샘플링 전역 시드.
SEED = 20260726

# 시점 분할 산출물(B8). doc_id→split(train/dev/test) · family-disjoint. gitignore(파생·재생성).
IR_SPLIT = IR_DIR / "split.parquet"
# 봉인된 test qrel(F9 사전등록). 최종 비교 전까지 열지 않는다 — 개발은 dev 로만.
IR_QREL_TEST_SEALED = IR_DIR / "qrel_test_sealed.parquet"

# --- B층 제2 확증분할 수집 (PLAN-031 §3 🔒사전등록 · PLAN-032 §5 설계) -----
# A층(기존 1,000건)은 1회 개봉·공표됐고 자원까지 바뀌므로 확증에 쓸 수 없다. B층은
# **오염되지 않은** 질의 200건을 같은 규칙으로 새로 모은다. 아래 값은 전부 PLAN-031 §3의
# 전사(轉寫)이며 **결과를 본 뒤 바꾸지 않는다** — 코드에서 고치면 사전등록 위반이다.
#
# 동결 IPC 21종 = A층 주분류 상위 20(누적 89.4%) + H10K(2023 IPC 개편 반영분).
# 정렬은 검색 응답의 **선두** IPC 를 주분류로 본다(§2.5(3) 실측).
B_LAYER_IPC = frozenset({
    "H01L", "C23C", "H01J", "H10D", "H10P", "G11C", "H10B", "C09G", "B23K", "C04B",
    "C07F", "B22F", "G02F", "H10W", "C09K", "H10F", "C22C", "G03F", "B82Y", "B81B", "H10K",
})
# 표집 창 — PLAN-031 **§9 개정**(2026-08-01 승인 · 봉인 개봉 전 · 재수집 착수 전).
# 구 창은 20050101~20251231 이었고 "출원일 오름차순 앞에서부터"의 귀결로 채택 200건이 전부
# 2005-01~02 가 됐다. 그 시점의 후보 코퍼스에서 **공개일 < 질의 출원일** 을 만족하는 문서가
# 40,552 중 **2건**뿐이라(§9.1 실측) 건초더미가 사라졌다 — 그 R@100 은 A층의 R@100 과 같은
# 양이 아니다. 창을 옮겨 마스크 후 후보를 13,801~17,209 로 되살린다(A층 test 의 60–75 %).
# **바뀐 것은 이 두 값뿐이다** — IPC 21종·포함기준·목표 200·호출 캡·평가 프로토콜은 불변.
B_LAYER_DATE_FROM = "20180101"   # PLAN-031 §9.2 개정 (구 20050101)
B_LAYER_DATE_TO = "20201231"     # PLAN-031 §9.2 개정 (구 20251231)
B_LAYER_TARGET = 200             # §3 목표. 미달해도 기준을 완화하지 않는다(정지 규칙)
B_LAYER_MAX_DETAIL = 500         # §8.1 승인 파일럿 예산 — r 의 분모
B_LAYER_MAX_SEARCH = 300         # 별도 계정(§1 호출 회계 동결)
B_LAYER_MAX_AUDIT = 50           # registerStatus 감사(§6.1 결정 E) — r 의 분모에서 제외
# §3 포함 1: register_status=거절 또는 examination_status 가 아래 집합에 듦.
B_LAYER_REJECTED_STATUS = "거절"
B_LAYER_EXAMINATION_REJECTED = frozenset({
    "거절결정(일반)", "거절결정(재심사)", "원결정유지(심사전치)",
})
# 응답 캐시는 A층(kipris_cache.sqlite)과 **분리**한다 — 섞으면 A층 재현 좌표가 흔들린다.
B_LAYER_CACHE = RAW_KIPRIS / "b_layer_cache.sqlite"
B_LAYER_DIR = IR_DIR / "b_layer"
B_LEDGER = B_LAYER_DIR / "screening_ledger.jsonl"      # 1행=1후보 · 인용 식별자 없음 · gitignore
B_ACCEPTED = B_LAYER_DIR / "accepted.parquet"          # claim1 원문 포함 → gitignore(§1-5)
# 집계만 담지만 data/processed/* 가 gitignore 이므로 파일 자체는 커밋되지 않는다 —
# 내용(콜 회계·r·사유 분포)은 프로파일과 MANIFEST 로 전사해 커밋한다.
B_BUDGET_REPORT = B_LAYER_DIR / "call_budget.json"
# 봉인 qrel. 파일럿 단계에서 **어떤 코드도 읽지 않는다**(PLAN-032 §1 성공기준 ⑤).
# **개봉 이후에도 아무나 읽지 않는다** — 이 파일을 여는 유일한 통로는
# `validate.seal_audit.open_sealed()` 이고 기본은 거부다(PLAN-047 §13.3).
B_QREL_SEALED = IR_DIR / "qrel_b_sealed.parquet"
# 봉인 열람 원장(추가전용). 여기 0행이면 "봉인을 열지 않았다"가 증명된다 — PLAN-047 G7 의
# 증거다. 집계·해시뿐이라 커밋 가능하나 data/processed 아래라 실제로는 gitignore 이며,
# 내용은 계획 문서에 전사한다(B_BUDGET_REPORT 와 같은 규율).
SEAL_ACCESS_LOG = IR_DIR / "seal_access.jsonl"
B_LAYER_PROFILE = DATA / "profiles" / "ir_split_b_pilot.md"   # §4 데이터 프로파일(커밋)
# KR 출원번호 → DOCDB family 지도. BigQuery 스캔은 **쿼리당 5.22 GB 고정**이고 파라미터
# 개수와 무관하다(2026-08-01 dry-run 실측) — 후보 1건마다 조회하면 같은 5.22 GB 를 수백 번
# 다시 낸다. 1회 적재해 재사용한다. §5.1 ③ "배치 조회"의 집행이며 판정 규칙은 불변이다.
B_LAYER_KR_FAMILY_MAP = INTERIM / "kr_family_map.parquet"

# --- T-gate 승인 규칙 (v0.9 · PLAN-019 W3 · 원고 §4.9) ---------------------
# Accept(ΔG) = 1[L0=L1=L2=L3=pass] · 1[LB95(ΔR100) > −ε]_T1 · 1[max_s Drop_s < δ]_T2
#              · 1[∀f∈{em,tf,core}: PassRate_f(new) ≥ PassRate_f(old)]_T3
# ε·δ 는 **테스트 개봉 전 동결**된 사전등록 값이다(F2·F3). 결과를 본 뒤 바꾸지 않는다.
T_EPSILON = 0.02        # T1 비열등 마진 (family Recall@100)
T_DELTA = 0.05          # T2 하위집단 최대 허용 하락
T2_MIN_N = 20           # 차단 규칙에 쓸 수 있는 하위집단 최소 질의수(미달=확정결론 금지)
T2_DIMS = ("pos_lang", "proc_group", "rejection")   # 사전 지정 하위집단 축(원고 §4.9 s)
# CQ 스위트 배정 (PLAN-019 §3.2 · 2026-07-28 동결). `.rq` 헤더 `# suite:` 가 정본이며 여기는
# 유효값 목록일 뿐이다. T3 는 **주 태스크(pa)를 제외한** 타 태스크·공유 스위트만 본다 —
# pa 의 회귀는 T1 이 통계적으로 담당하기 때문이다.
CQ_SUITES = ("pa", "em", "tf", "core")
T3_SUITES = ("em", "tf", "core")
# --- L3 검출 표면 분리 (PLAN-022 · 2026-07-28 동결 · N5c) ------------------
# W4b 실측: T3 발화 ∧ L3 미발화 인스턴스가 τ 세 값 전량(135개)에서 **0건**이었다. L3 가 전
# 스위트를 세고 T3 가 그 부분집합을 보므로 **L3 ⊇ T3 가 정의상 성립**해, H1 의 "T3 단독검출"은
# CQ 를 아무리 세분화해도 충족될 수 없는 기준이었다(원고 §6.5.2).
#   개정: L3 = 주 태스크(pa) 기능 검증 · T3 = 교차 태스크 비회귀 → 두 집합은 **서로소**다.
# **검출력은 불변이다** — 두 집합의 합집합이 여전히 CQ_SUITES 전량이고 승인식은 곱이므로,
# 개정 전 거부되던 델타가 개정 후 승인되는 일은 없다(PLAN-022 §0.1 · 불변량 테스트로 강제).
# 바뀌는 것은 검출력이 아니라 **귀속**이다.
L3_SUITES = ("pa",)
# --- CQ 조회 대상 (PLAN-023 §1 · 2026-07-28 동결 · N5d) --------------------
# 청구항 층(Claim 586,567 · ClaimFeature 1,289,300)은 G₀ 가 아니라 **사이드카**
# `central_axis.oxstore` 에만 있다 — CQ 러너가 읽는 graph_v0.ttl 에는 인스턴스가 0 건이다.
# `.rq` 헤더 `# target:` 으로 조회 대상을 선언한다(기본 graph · 하위호환).
#   **희석 금지(규칙 A).** 사이드카 CQ 는 시험 대상 그래프에 **무반응인 상수항**이라, L3 분모에
#   넣으면 항상 통과하는 CQ 가 실패를 희석해 검출력이 떨어진다(pa 1개 실패: 5개 중 0.800 →
#   8개 중 0.875). 그것은 PLAN-022 §0.1 의 검출력 불변량을 정면으로 깬다. 그래서 **L3·T3 판정
#   분모는 target=="graph" 로 한정**하고, 사이드카 CQ 는 **게이트가 아니라 측정**으로 운용한다
#   (CLAUDE.md §5 가 어휘 커버리지를 측정으로 둔 것과 같은 규율). 사이드카의 회귀는 델타 단위가
#   아니라 **세대 간 비교**로 잡는다(상류 재벤더 시 PROVENANCE 핀이 함께 움직인다).
CQ_TARGETS = ("graph", "sidecar")
CQ_GATE_TARGET = "graph"            # L3·T3 분모에 드는 유일한 대상
# --- 델타 유형과 중복제거 면제 (PLAN-022 §2 · 2026-07-28 동결) --------------
# W4b 불리한 실측: 정상 델타 N03(완전중복 병합)이 τ=0 에서 3/27(11.1%) 거부됐다(사전등록
# 기준 5% 초과). 분포검사는 **행이 준 이유**를 구분하지 못한다 — 지식 소실과 중복 정리를
# 같게 본다. τ 를 올리는 것은 처방이 아니다(검출력 55→34→18 붕괴).
#   면제: delta_type == "dedup" 이고 **자동 검증**(제거 개체의 나가는·들어오는 간선 서명이
#   보존 개체와 완전 동일)을 통과할 때에만 **분포검사만** 면제한다. 존재검사는 면제하지 않는다.
#   정당성을 사람이 판단하지 않는다 — 라벨 유사도는 동의어의 증거가 아니다(PLAN-021 §3).
DELTA_TYPES = ("generic", "dedup")
# --- CQ 판정 규칙 v2 (PLAN-021 · 2026-07-28 동결 · W4b) --------------------
# v1 은 존재검사(rows ≥ expect-min)뿐이라 결함이 CQ 를 **0행으로 만들어야만** 발화했다 —
# W4 에서 T3 가 0/108 을 낸 원인이다(PLAN-020 §8.2). v2 는 존재검사에 **기준선 대비 분포
# 검사**를 더한다:
#     pass_v2 = (rows ≥ expect_min) ∧ ¬regress,
#     regress = rows < (1−τ)·base           (monotone: up   — 행이 곧 능력)
#             = rows > (1+τ)·base           (monotone: down — 공백 탐색 질의는 증가가 회귀)
#             = |rows − base| > τ·base      (monotone: flat — 구조 불변량)
# 극성은 `.rq` 헤더 `# monotone:` 이 정본이다. 극성 선언 없이 "행수 하락=회귀"로 두면
# CQ03·CQ06 같은 **공백 탐색 질의**에서 정당한 보강이 회귀로 오판된다(실측 근거 PLAN-021 §3).
CQ_MONOTONE = ("up", "down", "flat")
CQ_RULE_VERSION = "v2"
CQ_TAU = 0.05                       # 주값 — 결과를 보기 전 동결
CQ_TAU_GRID = (0.0, 0.05, 0.10)     # 사전 동결 민감도 격자 (CLAUDE.md §1-2)
# 세대별 CQ 통과율 아티팩트(표 6.6 의 원천)와 waiver 로그. **집계·해시만** 담으므로 커밋 가능
# (data/processed 와 달리 gitignore 되지 않는다 · CLAUDE.md §1-5).
CQ_GEN_DIR = DATA / "cq_generations"
T3_WAIVER_LOG = CQ_GEN_DIR / "waiver_log.jsonl"
# 중복제거 면제 사용 이력 — waiver 와 같은 규율이다. 조용한 면제는 게이트를 장식으로 만든다.
DEDUP_EXEMPTION_LOG = CQ_GEN_DIR / "dedup_exemption_log.jsonl"
# T3 예외 토큰. 커밋 메시지에 이 토큰이 있을 때만 통과율 하락을 승인하며 횟수를 로그에 남긴다.
T3_WAIVER_TOKEN = "T3-WAIVER:"
# T-gate 종합 판정 산출(JSON)의 **구 고정 경로** — 더 이상 쓰기 대상이 아니다.
# 고정 경로 하나에 쓴 탓에 2026-08-15 시스템 비교 실행이 EP3(통제된 자원 교체)의 판정을
# 덮었고, data/processed 는 gitignore 라 복구 경로가 없었다. 지금 기본 경로는 실행 정체성이
# 들어간 이름이다(`validate.t_gate.report_path` · PLAN-060 §10). 이 상수는 그 사고 이전
# 산출물을 가리키기 위해서만 남긴다.
TGATE_REPORT = PROCESSED / "tgate_report.json"
# --- 자원 델타(O/O′) 비교 아티팩트 (D-19 · CLAUDE.md §0 델타 유형표) -----------
# H2(갱신 승인 안전성)는 **변경 없는 동일 파이프라인에 O 와 O′ 를 넣은** 비교로만 잰다.
# 그런데 run 경로에는 자원 차원이 없어(IR_RUNS_DIR 플랫) `make vendor` 뒤 재실행하면 O 의
# run 이 덮어써진다 — 그래서 O 를 **재벤더 전에** 얼려 둔다. run 사본은 특허 본문 파생이라
# gitignore, 매니페스트는 해시·집계뿐이라 커밋 가능(CQ 세대 동결과 같은 규율).
IR_RUNSETS_DIR = IR_DIR / "runsets"          # run 사본 (재생성 가능 · gitignore)
RUNSET_DIR = DATA / "runsets"                # 매니페스트 JSON (커밋 가능)
# --- C2′ 전달 실험 (RQ5 · PLAN-038 §12 동결) -----------------------------------
# 생성 원문은 특허 본문 파생이라 커밋 금지(§1-5) — data/processed 는 gitignore 이며,
# 커밋되는 것은 채점 집계 표와 해시뿐이다(PLAN-038 §8-4).
RAG_DIR = IR_DIR / "rag"
RAG_GEN_DIR = RAG_DIR / "generations"        # 1파일 = (팔 × 회차) · JSONL · 원문 전량 보존
RAG_SCORE_DIR = RAG_DIR / "scores"           # 결정적 채점 산출(JSON) · 재채점 시 바이트 동일
RAG_TABLE = TABLES / "rag_transfer_test.md"  # 원고 §6.8 탐색적 표 (A층)
# 델타 유형표 ①T-Box·②개념층만 H2 자격이 있다. ③A-Box 코퍼스 델타는 비교 불성립이다.
H2_ELIGIBLE_DELTA_TYPES = ("tbox", "concept")
# ── W9 홀드아웃 결함 사전등록 동결 (PLAN-025 v2 · 2026-07-28 · 주입 실행 전) 🔒 ──────────
# H1‴ 확증. 1차(W4·W4b·W4c)는 **같은 결함 인스턴스를 세 번 판정**했으므로 확증이 아니다 —
# 층 정의(L3_SUITES ⊥ T3_SUITES)를 동결한 채 **아직 판정한 적 없는 인스턴스**로 복제한다.
#   축 A(복제): F11·F12 를 새 rep 으로 · 축 B(일반화): 신규 교차결함 F13·F14·F15.
# `run_matrix` 의 rep 은 `range(reps)` = {0,1,2} 이므로 홀드아웃은 offset 3 → {3,4,5} 다.
# `seed_for` 가 sha256(key,rate,rep) 이라 rep 이 다르면 다른 결함 그래프다(테스트로 강제).
FAULT_HOLDOUT_RUN_ID = "w9_holdout"
FAULT_HOLDOUT_REP_OFFSET = 3        # 1차 rep {0,1,2} 와 겹치지 않는 첫 인덱스
FAULT_HOLDOUT_REPS = 3              # rep ∈ {3,4,5}
FAULT_HOLDOUT_CROSS_KEYS = ("F11", "F12", "F13", "F14", "F15")   # 교차결함 45 = H1‴ 판정 대상
FAULT_HOLDOUT_NORMAL_KEYS = ("N01", "N02", "N03")                # 정상 델타 27 = 위양성 분모
# 위양성 임계 — 정상 델타 거부 비율이 이 값을 넘으면 H1‴ 기각(PLAN-025 §3.4-3). 하드코딩 금지.
FAULT_FP_MAX_RATE = 0.05
# 비교차 결함군 F01–F10 은 재주입하지 않는다(판정식에 들어가지 않는다). 이 절단은 §6.5.4 에
# 명시한다 — 조용한 축소는 "전량 커버"로 읽힌다(CLAUDE.md §8).
# ── F9 사전등록 동결 (2026-07-27 · 데이터감사 후 확정 · 테스트 개봉 전) 🔒 ──────────────
# 질의(거절특허 1,000)를 filingDate 순 60/20/20 로 나누되 **family 단위**(family-disjoint)로 배정한다.
# family 대표일 = 그 family 질의들의 최소 출원일 · 동률은 family_id 사전순(결정적). 경계는 데이터
# 감사 결과이지 자의 선택이 아니다(정확히 600/200/200 로 떨어졌다). CLAUDE 규칙 #3: 결과 보고 불변.
F9_SPLIT_FRACTIONS = (0.60, 0.20, 0.20)                       # train / dev / test
F9_BOUNDARY_TRAIN_DEV = "2016-11-21"                          # train ≤ 경계 < dev
F9_BOUNDARY_DEV_TEST = "2021-07-21"                           # dev ≤ 경계 < test


def java_home() -> str:
    """pyserini(JVM) 부팅용 JAVA_HOME 을 확정한다 (PLAN-018 E1).

    장비에 JRE 만 있고 javac(JDK) 가 없으면 pyjnius 자동탐지가 실패한다. 환경변수
    JAVA_HOME 이 있으면 존중하고, 없으면 libjvm.so 를 담은 표준 경로를 탐지해 설정한다.
    하드코딩이 아니라 탐지 — 실패 시 명시적 예외로 사용자에게 알린다(CLAUDE §1.9 정신).
    """
    env = os.environ.get("JAVA_HOME")
    if env and (Path(env) / "lib" / "server" / "libjvm.so").exists():
        return env
    for cand in (
        "/usr/lib/jvm/java-21-openjdk-amd64",
        "/usr/lib/jvm/default-java",
    ):
        if (Path(cand) / "lib" / "server" / "libjvm.so").exists():
            os.environ["JAVA_HOME"] = cand
            return cand
    raise RuntimeError(
        "JAVA_HOME 미확정: libjvm.so 를 담은 JDK/JRE 경로를 찾지 못했다. "
        "JAVA_HOME 환경변수를 명시하라 (PLAN-018 §9 E1)."
    )

# --- 온톨로지 네임스페이스 ------------------------------------------------
# SDKB v1.0 실물과 일치 (semiconductor-knowledge-base). slash 네임스페이스 3분리:
#   ont:  TBox 어휘        ont:Patent, ont:Process, ont:realizesProcess …
#   data: ABox 인스턴스    data:subprocess/plasma_etch …
#   gov:  거버넌스 모듈    (이 논문에서는 사용하지 않음)
SDKB = Namespace("https://w3id.org/sdkb/")
ONT = Namespace("https://w3id.org/sdkb/ont/")
SDKB_DATA = Namespace("https://w3id.org/sdkb/data/")
GOV = Namespace("https://w3id.org/sdkb/gov/")

# 이 논문이 KIPRIS 에서 새로 만들어 넣는 특허 인스턴스의 IRI 접두어.
# TBox 는 SDKB 것을 그대로 쓰되(ont:Patent / ont:realizesProcess), 인스턴스는
# SDKB 의 data: 공간에 특허 서브트리를 새로 판다 — 상류 병합 시 충돌하지 않는다.
PATENT_NS = Namespace("https://w3id.org/sdkb/data/patent/")

# 네임스페이스 바인딩 헬퍼 (직렬화 시 prefix 를 SDKB 와 동일하게 유지)
NAMESPACES = {
    "sdkb": SDKB, "ont": ONT, "data": SDKB_DATA, "gov": GOV, "pat": PATENT_NS,
}


def bind_namespaces(g) -> None:
    """rdflib Graph 에 SDKB 표준 prefix 를 바인딩한다."""
    for prefix, ns in NAMESPACES.items():
        g.bind(prefix, ns)


def get_secret(name: str) -> str:
    """환경변수 → .env → Colab Secrets 순으로 시크릿을 찾는다."""
    val = os.environ.get(name)
    if val:
        return val
    try:  # .env (로컬)
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        val = os.environ.get(name)
        if val:
            return val
    except ImportError:
        pass
    try:  # Colab Secrets
        from google.colab import userdata  # type: ignore

        return userdata.get(name)
    except ImportError:
        pass
    raise KeyError(f"secret '{name}' not found in env, .env, or Colab secrets")
