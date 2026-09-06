.PHONY: all install venv parse owl convert align validate test clean \
        ingest-sirp sirp-pairs sirp-problems sirp experts \
        compliance curated-experts curated-ratings expdataset abox abox-patents \
        abox-prior-art abox-claim-features abox-full refetch-fulltext cq \
        public-release check-public signature signature-inject signature-check \
        superordinate-concepts concept-mapping \
        semiconto-fetch semiconto-analyze semiconto-align semiconto-enrich semiconto-phase0 \
        pipeline pipeline-sirp pipeline-full pipeline-with-expdataset help

PYTHON ?= python3

# ═══════════════════════════════════════════════════════════════════
# SDKB v1.0 — Build Pipeline
# Two tracks: (1) baseline curation, (2) SIRP patent layer.
# ═══════════════════════════════════════════════════════════════════

help:
	@echo "Targets:"
	@echo "  venv            Create .venv with Python 3.11"
	@echo "  install         Install package into the active env with dev+priorart+notebook extras"
	@echo "  parse           Baseline JSON → schema_report + parquet"
	@echo "  owl             Build sdkb-core.ttl ontology"
	@echo "  convert         JSON → RDF/JSON-LD"
	@echo "  align           Generate mapping candidates"
	@echo "  validate        SHACL validation"
	@echo "  test            Run pytest"
	@echo "  ingest-sirp     SIRP JSONL → patents/*.parquet"
	@echo "  sirp-pairs      Build 7,500 prior-art pairs"
	@echo "  sirp-problems   50 problems + 25 scenarios"
	@echo "  sirp            ingest-sirp + sirp-pairs + sirp-problems"
	@echo "  experts         Build 100 synthetic expert profiles"
	@echo "  compliance      Seed KR+US governance instances from ExpDataSet"
	@echo "  curated-experts Ingest curated 110-expert pool"
	@echo "  curated-ratings Ingest 7,800 3-rater ratings + compute kappa/ICC"
	@echo "  expdataset      compliance + curated-experts + curated-ratings"
	@echo "  abox            convert + lift experts/problems → A-Box TTL (notebook 06)"
	@echo "  abox-patents    convert + ingest-sirp + lift patents → A-Box TTL (notebook 07)"
	@echo "  abox-prior-art  cited prior-art documents → A-Box TTL (needs refetch-fulltext)"
	@echo "  abox-claim-features  claim features + judgments → A-Box TTL (needs refetch-fulltext)"
	@echo "  abox-full       all A-Box layers (needs KIPRIS key)"
	@echo "  refetch-fulltext  re-fetch KIPRIS full text into the emptied A-Box inputs"
	@echo "  cq              run the competency-question suite → report"
	@echo "  public-release  build the public tree (KIPRIS full text emptied) into PUBLIC_OUT"
	@echo "  check-public    scan that tree with fingerprints from the private canonical"
	@echo "  signature       count classes / predicates / instances → data/reports/graph_signature.json"
	@echo "  signature-inject  + rewrite the signature block in README.md and README.ko.md"
	@echo "  signature-check   fail if that block is stale (do not write)"
	@echo "  semiconto-fetch    Download SemicONTO v0.2 TTL into ontology/imports/"
	@echo "  semiconto-analyze  Parse SemicONTO TTL → data/reports/semiconto_analysis.json"
	@echo "  semiconto-align    Build SDKB↔SemicONTO SKOS alignment (mappings/)"
	@echo "  semiconto-enrich   Identify enrichment candidates (Bucket A/B)"
	@echo "  semiconto-phase0   fetch + analyze + align + enrich (SDKB-centric Phase 0)"
# sdkb:private-begin
	@echo "  viz             Build interactive GitHub Pages site → site/"
	@echo "  viz-open        Build viz and open site/index.html in default browser"
	@echo "  viz-clean       Remove site/ build artifacts"
# sdkb:private-end
	@echo "  pipeline        parse + owl + convert + validate + test"
	@echo "  pipeline-sirp   pipeline + sirp"
	@echo "  pipeline-full   pipeline + sirp + experts"
	@echo "  pipeline-with-expdataset   pipeline-full + expdataset"
	@echo "  clean           Remove generated artifacts"
	@echo ""
	@echo "Tip: prefix targets with PATH=.venv/bin:\$\$PATH or source .venv/bin/activate first."

all: parse owl convert

# ── Setup ─────────────────────────────────────────────────────────
venv:
	python3.11 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip setuptools wheel
	.venv/bin/python -m pip install -e ".[dev,priorart,notebook]"

install:
	$(PYTHON) -m pip install -e ".[dev,priorart,notebook]"

# ── Baseline track ────────────────────────────────────────────────
parse:
	$(PYTHON) scripts/parse_baseline.py

owl:
	$(PYTHON) scripts/build_owl.py

convert:
	$(PYTHON) scripts/convert_rdf.py

# Lift curated experts + SME problems into an RDF A-Box linked to the
# ontology node URIs emitted by `convert` (consumed by notebook 06).
abox: convert
	$(PYTHON) scripts/build_abox_experts_problems.py

# Lift the SIRP rejected-patent corpus into an RDF A-Box (consumed by
# notebook 07 — ontology-driven prior-art retrieval).
abox-patents: convert ingest-sirp
	$(PYTHON) scripts/build_abox_patents.py

# ── CR-012 · B층 확증분할 질의 (하류 논문 평가자산) ────────────────────
# 별도 파일로 둔다. 이유 둘 — ⓐ CR-012 요구 ⓑ 의 층 구분을 새 술어 없이(T-Box 델타 0)
# 주는 가장 싼 형태가 파일이고, ⓑ 이 저장소는 공개되는 기반 온톨로지라 논문 평가자산을
# 도메인 지식과 같은 파일에 섞으면 공개본 정리 때 다시 갈라내야 한다.
# 수집은 네트워크를 타므로 빌드와 분리한다 — 재실행해도 이미 받은 건은 건너뛴다.
collect-b-layer-queries:
	$(PYTHON) scripts/collect_b_layer_queries.py

abox-b-layer-queries: convert
	$(PYTHON) scripts/build_abox_b_layer_queries.py

# ── 인용 선행기술 · 청구항 feature A-Box (CR-016 §2 출력 (1)) ──────────
# 두 생성기는 2026-05 부터 실재했는데 **진입점이 없었다** — 사람이 손으로
# `python scripts/…` 를 치는 것만이 방법이었고, 그래서 외부인에게는 존재하지 않는
# 빌드였다. 산출 TTL 둘은 gitignore 된 대용량이므로(라이선스 · 899 MB/21 MB)
# **진입점이 곧 재현 경로**다. 비워 두고 채우는 방법을 주는 설계는 채우는 명령이
# 있어야 성립한다.
#
# 입력은 네트워크 수집분(cited_enriched · claim_features)이라 `make refetch-fulltext`
# 가 선행한다. 그래서 두 타깃을 pipeline 계보에 **직접 걸지 않는다** — 키 없는
# 체크아웃에서 pipeline 이 죽으면 T-Box 재현까지 함께 막힌다.
# B층 인용문헌(CR-008 · 479 건)은 **생성기 기본값**으로 들어온다 — 인자를 여기에만
# 적어 두면 `python scripts/…` 직접 실행 경로가 다시 갈리고, 그 갈림이 D-52 였다.
abox-prior-art: convert
	$(PYTHON) scripts/build_abox_prior_art.py

abox-claim-features: convert
	$(PYTHON) scripts/build_abox_claim_features.py

# 비운 A-Box 를 채우는 진입점 — KIPRIS 키가 필요하다(§ README "무엇이 비어 있고
# 어떻게 채우는가"). 수집 규칙의 정본은 흡수된 수집기이고, 여기서 새로 짜지 않는다.
refetch-fulltext:
	$(PYTHON) scripts/refetch_rejected_patents.py
	$(PYTHON) scripts/collect_cited_biblio_claims.py

# A-Box 전량 — 자격(KIPRIS 키)과 시간이 드는 경로를 한 이름으로 묶는다.
abox-full: abox abox-patents abox-vendors abox-prior-art abox-claim-features

# ── CQ 스위트 (CR-016 §2 출력 (3)) ─────────────────────────────────────
# CQ 는 평가 하네스가 아니라 **온톨로지가 무엇에 답할 수 있는가의 명세**, 즉 도메인
# 자산이다. 하류 논문 저장소에만 있으면 "CQ 를 공개한다"는 서술이 거짓이 된다.
cq: convert
	$(PYTHON) scripts/run_cq.py

# ── 공개본 (CR-015) ────────────────────────────────────────────────────
# 공개할 트리를 **매번 코드가 만든다.** 손으로 지우면 다음에 또 어긋난다 — 원고 §10.3 이
# "재배포할 수 없다"고 쓰는데 리포는 초록·청구항 전문 1,000건을 담고 있었던 것이 정확히
# 그 어긋남이었다.
#
# 푸시는 이 Makefile 이 하지 않는다. 되돌릴 수 없는 단계이므로 사람이 검사기 통과를
# 확인한 뒤에 한다 — 공개된 커밋은 지워도 포크·캐시·PR ref 로 남는다.
PUBLIC_OUT ?= build/public

public-release:
	$(PYTHON) scripts/build_public_release.py --out $(PUBLIC_OUT) --force
# CQ 실행 결과는 **공개 트리 안에서 다시 낸다.** 리포지토리의 cq_report.json 은 원문이 전량
# 있는 개발 환경의 값(2026-08-15 실측 0.871)인데, 공개본을 받은 사람이 그대로 돌리면 0.452 가
# 나온다 — 특허 A-Box 가 없어 특허를 묻는 질의가 실패하기 때문이다. 개발 환경 값을 그대로
# 실으면 **발행된 숫자가 소비 가능한 상태를 기술하지 않는다**(D-19 계열).
# 재인출 뒤에는 0.871 로 올라가며 그 쌍을 CHANGELOG 에 적는다.
# **cd 하지 않는다.** run_cq.py 는 경로를 `__file__` 기준으로 잡으므로(`ROOT = parents[1]`)
# 공개 트리 안의 사본을 부르면 그 트리가 곧 ROOT 다. cd + $(abspath $(PYTHON)) 조합은
# PYTHON 이 경로가 아닐 때 `$(CURDIR)/python3` 를 만들어 빌드를 세웠고(기본값이 `python3` 다),
# uv 처럼 프로젝트를 탐색하는 러너에서는 공개 트리 안에 새 환경을 만든다.
	$(PYTHON) $(PUBLIC_OUT)/scripts/run_cq.py
# 무결성 기록은 **공개 트리의 바이트로** 낸다 — 비공개 원본은 복사되며 변형되므로(사설 블록·
# 죽은 링크·원문 스크럽) 원본 해시를 실으면 심사자가 계산한 값과 영원히 어긋난다.
	$(PYTHON) scripts/build_provenance.py --tree $(PUBLIC_OUT)

check-public:
	$(PYTHON) scripts/check_public_release.py --tree $(PUBLIC_OUT) \
		--report data/reports/public_release_check.json
	$(PYTHON) scripts/build_provenance.py --tree $(PUBLIC_OUT) --check

# ── 그래프 서명 (R4 · CLAUDE.md §4) ────────────────────────────────
# §4 는 "릴리스를 만들 때 그래프 서명을 CHANGELOG 에 남긴다" 고 요구하는데 그것을
# 이행하는 코드가 없어서 README 수치가 손으로 관리됐고 넷이 어긋났다(점검 F4·F5).
# 이제 세는 것은 코드다. `signature-check` 는 README 블록이 낡았으면 실패한다.
signature:
	$(PYTHON) scripts/report_graph_signature.py

signature-inject:
	$(PYTHON) scripts/report_graph_signature.py --inject

signature-check:
	$(PYTHON) scripts/report_graph_signature.py --check

# KSIA 회원사 명부 → ont:Vendor A-Box. abox-patents 뒤에 와야 한다 —
# 이미 특허 출원인(Organization)으로 존재하는 회사를 알아보고 중복 노드를 만들지 않으려면
# sdkb-abox-patents.ttl 이 먼저 있어야 한다.
abox-vendors: convert abox-patents
	$(PYTHON) scripts/build_abox_vendors_ksia.py

align:
	$(PYTHON) scripts/align_candidates.py

# ── 개념 매핑 자산 (CR-007) ───────────────────────────────────────
# 하류는 동결 스냅샷만으로 개념 링크를 재현할 수 있어야 한다(D-16). 그 재현에
# 필요한 규칙·사전이 이 자산이다. 상위 개념 주입이 먼저다 — 없으면 재지정이
# 붙을 자리가 없다.
superordinate-concepts:
	$(PYTHON) scripts/add_superordinate_concepts.py

concept-mapping: convert
	$(PYTHON) scripts/build_concept_mapping.py

# 검사되지 않는 shape 은 shape 이 아니다. 세 번 데었다:
#   · Shape_CoreNode 가 Expert·Problem 을 대상에서 빼먹었다 (라벨 규약 위반이 통과)
#   · validate 가 core-data 만 읽어 A-Box 에 걸리는 shape 이 아예 안 돌았다
#   · shapes_patent.ttl 은 **어떤 타깃도 실행하지 않았다** (특허 제목 결측이 통과)
# 그래서 A-Box 를 전부 싣고, 특허 shape 도 함께 돌린다.
# 2026-08-09(CR-016 성공기준 ①): 빈 체크아웃에서 `make pipeline` 이 **여기서 죽었다** —
# 두 A-Box 는 gitignore 된 빌드 산출물인데 pipeline 이 그것을 만들지 않는다. 파일이
# 없으면 검증기가 "Data file not found" 로 종료하고, T-Box 재현까지 함께 막혔다.
# 고친 방향은 **건너뛰기가 아니라 짓기**다 — 이 둘은 자격이 필요 없다(커밋된 원천에서
# 만든다). 없을 때만 짓고, 그래도 없으면 그때는 건너뛰되 **무엇을 빌드해야 하는지 말한다**
# (B층 질의에 이미 쓰던 방식). 검증 자체는 한 칸도 느슨하게 하지 않는다(§1.6).
validate:
	@test -f ontology/sdkb-abox-experts-problems.ttl || $(MAKE) PYTHON=$(PYTHON) abox
	@test -f ontology/sdkb-abox-patents.ttl || $(MAKE) PYTHON=$(PYTHON) abox-patents
	$(PYTHON) scripts/validate_shacl.py --data ontology/sdkb-core-data.ttl ontology/sdkb-abox-experts-problems.ttl
	$(PYTHON) scripts/validate_shacl.py --shapes validation/shapes_patent.ttl \
		--data ontology/sdkb-abox-patents.ttl ontology/sdkb-core-data.ttl ontology/sdkb-patent.ttl
	@# CR-012 B층 질의도 같은 shape 을 탄다. A층과 **따로** 돌리는 이유는 인용 면제가
	@# B층에만 걸린다는 것을 실행으로 보이기 위해서다 — 합쳐 돌리면 A층이 통과시켜 준
	@# 것인지 면제가 걸린 것인지 출력만 봐서는 갈리지 않는다.
	@test -f ontology/sdkb-abox-b-layer-queries.ttl && \
		$(PYTHON) scripts/validate_shacl.py --shapes validation/shapes_patent.ttl \
			--data ontology/sdkb-abox-b-layer-queries.ttl ontology/sdkb-core-data.ttl ontology/sdkb-patent.ttl \
		|| echo "  (B층 질의 A-Box 미빌드 — 건너뜀. 빌드: make abox-b-layer-queries)"
	@# PLAN-005 단계 2-B — `shapes_claim_features.ttl` 은 **어디에도 배선되어 있지 않았다.**
	@# 부채 대장 4번(특허 shape 미배선)과 같은 양식이며, 쓰여만 있고 돌지 않는 shape 은
	@# 게이트가 아니라 장식이다(§4). 판단 승격(635→1,812)으로 이 층이 커진 지금 배선한다.
	@# 추론은 none — 근거는 validate_shacl.py 의 `--inference` 주석(실측 수치 포함).
	@test -f ontology/sdkb-abox-claim-features.ttl && \
		$(PYTHON) scripts/validate_shacl.py --shapes validation/shapes_claim_features.ttl \
			--inference none \
			--data ontology/sdkb-abox-claim-features.ttl ontology/sdkb-patent.ttl \
		|| echo "  (claim-features A-Box 미빌드 — 건너뜀. 빌드: make abox-claim-features)"

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

# ── SIRP (patent) track ───────────────────────────────────────────
ingest-sirp:
	$(PYTHON) scripts/ingest_rejected_patents.py

sirp-pairs: ingest-sirp
	$(PYTHON) scripts/build_prior_art_pairs.py

sirp-problems: ingest-sirp
	$(PYTHON) scripts/sample_problems.py

sirp: ingest-sirp sirp-pairs sirp-problems

experts:
	$(PYTHON) scripts/gen_experts.py

# ── Curated ExpDataSet integration ───────────────────────────────
compliance:
	$(PYTHON) scripts/seed_compliance_governance.py

curated-experts:
	$(PYTHON) scripts/ingest_curated_experts.py

curated-ratings:
	$(PYTHON) scripts/ingest_curated_ratings.py

expdataset: compliance curated-experts curated-ratings

# ── SemicONTO Phase 0 (SDKB-centric curation) ────────────────────
SEMICONTO_TTL := ontology/imports/SemicONTO-0.2.ttl
SEMICONTO_URL := https://huanyu-li.github.io/SemicONTO/0.2/SemicONTO.ttl
SEMICONTO_SHA := 4c53544de016b2d1147d41ba68094c7849999494378cd2c68674334b0e2e8d52

semiconto-fetch:
	@mkdir -p ontology/imports
	@if [ ! -f $(SEMICONTO_TTL) ]; then \
	  echo "Fetching SemicONTO v0.2 TTL from $(SEMICONTO_URL)"; \
	  curl -sSL -A "SDKB-curation/0.1" -H "Accept: text/turtle" \
	    -o $(SEMICONTO_TTL) $(SEMICONTO_URL); \
	else \
	  echo "$(SEMICONTO_TTL) already cached — skipping fetch"; \
	fi
	@echo "$(SEMICONTO_SHA)  $(SEMICONTO_TTL)" | sha256sum -c

semiconto-analyze: semiconto-fetch
	$(PYTHON) scripts/analyze_semiconto.py

semiconto-align: semiconto-analyze
	$(PYTHON) scripts/build_semiconto_alignment.py

semiconto-enrich: semiconto-align
	$(PYTHON) scripts/identify_enrichment_candidates.py

semiconto-phase0: semiconto-fetch semiconto-analyze semiconto-align semiconto-enrich

# sdkb:private-begin
# ── Visualization (GitHub Pages demo) ─────────────────────────────
# .PHONY 를 여기 둔다 — 위쪽 목록은 `\` 로 이어져 있어 그 사이에 주석을 넣으면
# 이어붙이기가 깨진다(실측: "missing separator"). 공개본에서는 이 블록째 사라진다.
.PHONY: viz viz-clean viz-open

viz:
	$(PYTHON) scripts/build_viz.py

viz-open: viz
	@if command -v xdg-open >/dev/null 2>&1; then xdg-open site/index.html; \
	elif command -v open >/dev/null 2>&1; then open site/index.html; \
	else echo "open site/index.html manually"; fi

viz-clean:
	rm -rf site/
# sdkb:private-end

# ── Composed pipelines ────────────────────────────────────────────
pipeline: parse owl convert validate test

pipeline-sirp: pipeline sirp

pipeline-full: pipeline sirp experts

pipeline-with-expdataset: pipeline-full expdataset

# ── Clean ─────────────────────────────────────────────────────────
clean:
	rm -f data/schema_report.json data/nodes.parquet data/edges.parquet
	rm -f data/problems.parquet data/regulatory_scenarios.parquet data/problems_report.json
	rm -f data/expert_profiles.parquet data/experts_report.json
	rm -f data/patents/rejected_patents_meta.parquet
	rm -f data/patents/ipc_links.parquet
	rm -f data/patents/prior_art_edges.parquet
	rm -f data/patents/prior_art_pairs.parquet
	rm -f data/patents/ingest_report.json data/patents/pairs_report.json
	rm -f data/compliance/technology_controls.parquet data/compliance/seed_report.json
	rm -f data/experts/curated_profiles.parquet data/experts/curated_profiles_report.json
	rm -f data/experts/curated_ratings.parquet data/experts/curated_ratings_pivot.parquet
	rm -f data/experts/reliability_report.md data/experts/reliability_report.json
	rm -f ontology/sdkb-core.ttl ontology/sdkb-core-data.ttl ontology/sdkb-core-data.jsonld
	rm -f ontology/sdkb-governance-kr-instances.ttl ontology/sdkb-governance-us-instances.ttl
	rm -f mappings/mapping_candidates.tsv
	rm -rf site/
