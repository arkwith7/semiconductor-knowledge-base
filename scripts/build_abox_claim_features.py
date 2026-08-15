#!/usr/bin/env python3
"""청구항 feature + 거절-판단 패턴 A-Box 빌드 — 중심축 데이터셋의 실체화.

입력:
  data/interim/claim_features.jsonl            (decompose_corpus.py 산출: 청구항→feature)
  data/patents/prior_art_edges.parquet         (evidence_v2: 거절-판단쌍 · cited_doc_id→cited_id)
출력:
  ontology/sdkb-abox-claim-features.ttl

각 feature 텍스트를 SDKB 개념에 정규화(featureConcept)한다 — build_abox_patents 와 **동일한**
브리지를 써서 어휘를 발명하지 않는다. 심사관 판단(evidence_v2)은 PriorArtJudgment 로 실체화한다.
결정적: 같은 입력이면 같은 그래프.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sdkb_nb as S  # noqa: E402

ROOT = S.find_root(Path(__file__).resolve().parent)
FEATURES = ROOT / "data" / "interim" / "claim_features.jsonl"
EDGES = ROOT / "data" / "patents" / "prior_art_edges.parquet"
# CR-011 — B층 인용 문헌은 EDGES 에 없다(CR-008 비목표 ⓒ · 질의–인용 대응 미이관).
# 503건 중 EDGES 정규형 맵에 있는 것은 3건뿐이라, 이 맵 없이는 500건이 patent_unresolved 로 버려진다.
B_LAYER_POP = ROOT / "data" / "patents" / "b_layer_cited_population.parquet"
OUT_TTL = ROOT / "ontology" / "sdkb-abox-claim-features.ttl"
OUT_REPORT = ROOT / "data" / "reports" / "abox_claim_features_report.json"
# CR-017 — 소비 가능한 투영. TTL 은 899 MB 라 벤더할 수 없다(하류 §1-5 · 저장소 실무 양쪽).
# 자산을 새로 만들지 않고, 같은 빌드가 들고 있는 것을 **전달 가능한 형태로** 함께 낸다.
OUT_PARQUET = ROOT / "mappings" / "claim_features.parquet"
OUT_PROJ_META = ROOT / "mappings" / "claim_feature_release_meta.json"
B_LOSS_REPORT = ROOT / "data" / "reports" / "b_layer_claim_decomposition_loss.json"

ONT = S.ONT
DCTERMS = Namespace("http://purl.org/dc/terms/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
LICENSE = "KIPRIS terms — academic use, no redistribution of full text"

# feature 정규화에 계상할 개념 축(build_abox_patents PATENT_ROUTING 과 정합).
CONCEPT_TYPES = {"Process", "SubProcess", "Device", "Material", "Skill", "FailureMode", "EquipmentClass"}
# §29 항 → 기존 RejectionType 개체
GROUND = {"§29①": "Rejection_Novelty", "§29②": "Rejection_Inventiveness"}


def _u(curie_or_path: str) -> URIRef:
    return URIRef(S.DATA + curie_or_path.replace(":", "/"))


def _patent_iri(field: str, cited_map: dict[str, str]) -> URIRef | None:
    """분해 patent 필드 → 그래프 특허 IRI.

    rej:{appno} → data:patent/kr_{appno} · cited:{doc_id} → cited_id 맵 ·
    g2:{slug}·g1:{slug} → data:patent/{slug} (둘 다 patent/kr_{appno} 슬러그)
    """
    kind, _, rest = field.partition(":")
    if kind == "rej":
        return _u(f"patent/kr_{rest}")
    if kind in ("g2", "g1"):
        return _u(f"patent/{rest}")
    if kind == "cited":
        cid = cited_map.get(rest)          # 'patent:kr_KR..A'
        return _u(cid.replace("patent:", "patent/")) if cid else None
    return None


def _slug(field: str) -> str:
    """Claim/Feature IRI 용 안정 슬러그."""
    return re.sub(r"[^A-Za-z0-9]+", "_", field).strip("_")


# CR-011 성공기준 ② — 본문 자체가 없어 분모에서 빼는 US 2건.
# 1968년 출원·1970년 등록이라 어느 원천에도 OCR 전문이 없다(재시도 1회 실패 · 하류 §1.6a).
B_US_NO_FULLTEXT = ("US-P-03517643", "US-P-03530092")
ENRICHED = ROOT / "data" / "patents" / "cited_enriched"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _duplicate_key_stats(rows: list[dict]) -> dict:
    """CR-019 — 원천의 중복 `(patent, claim_no)` 키를 **버리지 않고 센다**.

    `decompose_corpus.py` 산출에 같은 키가 두 번 실리면 그 행의 feature 가 다시 방출된다.
    그래프는 rdflib 가 합쳐 멀쩡하지만 계수기는 겹세기를 했고, 그 숫자가 발행돼 하류의
    판단을 틀리게 만들었다(D-41). 원인을 고치는 것은 이 함수가 아니라 원천 생성기 소관이며,
    여기서는 **얼마나 겹쳤는지를 리포트에 남기는 것**까지만 한다.
    """
    seen: set[tuple] = set()
    dup_keys: set[tuple] = set()
    by_side: Counter = Counter()
    dup_rows = 0
    for r in rows:
        key = (r["patent"], r["claim_no"])
        if key in seen:
            dup_rows += 1
            if key not in dup_keys:
                dup_keys.add(key)
                side = r["patent"].split(":")[0] if ":" in r["patent"] else "rej"
                by_side[side] += 1
        seen.add(key)
    return {"input_duplicate_keys": len(dup_keys), "input_duplicate_rows": dup_rows,
            "duplicate_keys_by_side": dict(sorted(by_side.items()))}


def _assert_count_integrity(report: dict) -> None:
    """계수와 투영이 어긋난 리포트는 **쓰지 않는다** — CR-019 의 재발 방지선.

    틀린 숫자를 발행하느니 산출물이 없는 편이 낫다. 발행된 틀린 숫자가 정확히 D-41 의
    피해였고, 하류는 자기 쪽에서 정확히 세고도 자기 계수를 의심했다.
    """
    counts, proj = report["counts"], report["projection_cr017"]
    problems = []
    if counts["features"] != proj["rows_features"]:
        problems.append(f"counts.features {counts['features']:,} != "
                        f"projection.rows_features {proj['rows_features']:,}")
    by_type = sum(report["feature_concept_by_type"].values())
    if by_type != proj["concept_links"]:
        problems.append(f"Σfeature_concept_by_type {by_type:,} != "
                        f"projection.concept_links {proj['concept_links']:,}")
    if problems:
        raise SystemExit("CR-019 계수 무결성 위반 — 리포트를 쓰지 않는다:\n  "
                         + "\n  ".join(problems))


def _emit_projection(proj: list[dict], input_sha: str) -> dict:
    """CR-017 — 투영 2종 발행. **원문(feature_text)은 넣지 않는다**(KIPRIS 비재배포).

    행 = ClaimFeature 하나. 개념은 feature 당 여럿이므로 리스트 열로 두고 grain 을 지킨다 —
    explode 하면 행이 더 이상 ClaimFeature 가 아니라 하류 조인에서 중복 계수가 난다.

    결정성(성공기준 ①): 행은 (publication_id, claim_number, feature_seq) 로, 리스트는 사전순으로
    정렬한다. 메타에 **시각을 넣지 않는다** — 타임스탬프가 들어가면 두 번 돌린 sha256 이 갈린다.
    """
    df = pd.DataFrame(proj).sort_values(
        ["publication_id", "claim_number", "feature_seq"], kind="mergesort"
    ).reset_index(drop=True)

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False, compression="zstd")

    # 개념별 df — CR-009 `concept_meta` 와 **같은 형식**이다(새 형식을 만들지 않는다).
    # 분모를 둘 낸다: feature 단위와 특허 단위. 어느 쪽으로 가중할지는 하류 소관(비목표 ⓑ).
    df_feature: Counter = Counter()
    df_patent: dict[str, set] = {}
    for pid, concepts in zip(df["publication_id"], df["feature_concept"]):
        for c in concepts:
            df_feature[c] += 1
            df_patent.setdefault(c, set()).add(pid)

    # 커버리지 — 질의측(rej)·후보측(cited·g1·g2)과 관할별로 나눠 센다.
    cov: dict[str, Counter] = {"by_side": Counter(), "by_jurisdiction": Counter(),
                               "features_with_concept_by_side": Counter()}
    for side, pid, concepts in zip(df["side"], df["publication_id"], df["feature_concept"]):
        cov["by_side"][side] += 1
        cov["by_jurisdiction"][pid.split("_")[0]] += 1
        if concepts:
            cov["features_with_concept_by_side"][side] += 1

    meta = {
        "_README": "CR-017 청구항 한정요소 투영. 행 = ClaimFeature. **원문 없음** — 구조와 개념 "
                   "IRI 만 싣는다(KIPRIS 비재배포). 개념 df 는 CR-009 concept_meta 와 같은 형식이며 "
                   "가중식은 상류가 정하지 않는다(하류 사전등록 소관).",
        "schema_version": "1.0",
        "source": {
            "ttl": OUT_TTL.name,
            "ttl_sha256": input_sha,
            "generator": Path(__file__).name,
        },
        "counts": {
            "rows_features": int(len(df)),
            "claims": int(df["claim_id"].nunique()),
            "patents": int(df["publication_id"].nunique()),
            "features_with_concept": int((df["feature_concept"].str.len() > 0).sum()),
            "concept_links": int(sum(df_feature.values())),
            "distinct_concepts": len(df_feature),
        },
        "df_denominator": {"features": int(len(df)), "patents": int(df["publication_id"].nunique())},
        "concepts": {c: {"df_feature": df_feature[c], "df_patent": len(df_patent[c])}
                     for c in sorted(df_feature)},
        "coverage": {k: dict(sorted(v.items())) for k, v in cov.items()},
    }
    OUT_PROJ_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=False))

    sizes = {"parquet_bytes": OUT_PARQUET.stat().st_size,
             "meta_bytes": OUT_PROJ_META.stat().st_size}
    print(f"✓ CR-017 투영 → {OUT_PARQUET.name} ({sizes['parquet_bytes']/1e6:,.1f} MB) · "
          f"{OUT_PROJ_META.name} ({sizes['meta_bytes']/1e6:,.1f} MB)")
    print(f"  행 {len(df):,} · 특허 {meta['counts']['patents']:,} · "
          f"개념 보유 feature {meta['counts']['features_with_concept']:,} · "
          f"개념 링크 {meta['counts']['concept_links']:,}")
    print(f"  parquet sha256 {_sha256(OUT_PARQUET)}")
    return {**meta["counts"], **sizes}


def _b_loss_report(b_pop: "pd.DataFrame", b_claims: Counter) -> None:
    """CR-011 출력 (2) — 청구항 문자열은 있으나 분해되지 않은 B층 문헌을 **건별로** 남긴다.

    자원 지표만으로 합격을 선언하지 않기 위한 장치다. 관할별 분해율은 성공기준 ①② 의 값이고,
    `unresolved` 목록은 "조용히 빠뜨리지 않았다"의 증거다.
    """
    def _claim_len(v: object) -> int:
        """청구항 문자열의 길이. **결측은 0 이다.**

        `str(v or "")` 로 쓰면 안 된다 — parquet 의 결측은 float `nan` 이고 **`nan` 은 참**이라
        `str(nan)` = `"nan"`(3글자)이 되어 결측이 "청구항 있음"으로 둔갑한다. 실제로 그렇게
        JP 19건이 미분해로 잘못 계상됐다(2026-08-06). 분모를 부풀리는 방향의 오류다.
        """
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0
        return len(str(v).strip())

    have_text: dict[str, int] = {}
    for line in (ENRICHED / "kipris.jsonl").open():
        r = json.loads(line)
        n = _claim_len(r.get("claims"))
        if n:
            have_text[r["cited_doc_id"]] = n
    for pq in ("bigquery.parquet", "bigquery_us.parquet",
               "bigquery_b_layer.parquet", "bigquery_us_b_layer.parquet"):
        df = pd.read_parquet(ENRICHED / pq)
        for _, r in df.iterrows():
            n = _claim_len(r.get("claims"))
            if n and r["cited_doc_id"] not in have_text:
                have_text[r["cited_doc_id"]] = n

    pat = b_pop[~b_pop["is_npl"]]
    per_country: dict[str, dict] = {}
    unresolved: list[dict] = []
    for country, grp in pat.groupby("cited_country"):
        docs = sorted(grp["cited_doc_id"])
        with_text = [d for d in docs if d in have_text and d not in B_US_NO_FULLTEXT]
        decomposed = [d for d in with_text if b_claims.get(d, 0) > 0]
        per_country[str(country)] = {
            "n_documents": len(docs),
            "n_with_claim_text": len(with_text),
            "n_decomposed": len(decomposed),
            "decomposition_rate": round(len(decomposed) / len(with_text), 4) if with_text else None,
            "claims_published": sum(b_claims.get(d, 0) for d in docs),
        }
        for d in sorted(set(with_text) - set(decomposed)):
            unresolved.append({"cited_doc_id": d, "country": str(country),
                               "claim_text_len": have_text[d], "reason": "claim_text present but no Claim published"})

    report = {
        "cr": "CR-011", "denominator_note":
            f"본문 자체가 없는 US {len(B_US_NO_FULLTEXT)}건은 분모에서 뺀다(성공기준 ②): "
            + ", ".join(B_US_NO_FULLTEXT),
        "by_country": dict(sorted(per_country.items())),
        "unresolved": unresolved,
    }
    B_LOSS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    B_LOSS_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    kr, us = per_country.get("KR", {}), per_country.get("US", {})
    print(f"✓ B층 손실 리포트 → {B_LOSS_REPORT.name} "
          f"(KR {kr.get('decomposition_rate')} · US {us.get('decomposition_rate')} · 미분해 {len(unresolved)}건)")


def main() -> int:
    if not FEATURES.exists():
        print(f"ERROR: {FEATURES} 없음 — decompose_corpus.py 먼저", file=sys.stderr)
        return 1
    try:
        br = S.make_bridge(ROOT, morph=True)
    except SystemExit:
        br = S.make_bridge(ROOT)

    edges = pd.read_parquet(EDGES)
    # cited_id 는 source_type 별로 형식이 다르다 — 'all'/'examiner' 는 정규형('patent:kr_..A'),
    # evidence_v2 는 비정규형('KR-P-..'). 인용 노드(A-1)는 정규형 IRI 를 쓰므로 정규형만으로 맵을 만든다.
    canon = edges[edges["cited_id"].astype(str).str.startswith("patent:")]
    cited_map = dict(zip(canon["cited_doc_id"], canon["cited_id"]))
    # CR-011 — B층 모집단 IRI 를 **병합**한다. A층 항목을 덮어쓰지 않는다(A층 IRI 불변 = 성공기준 ③).
    b_pop = pd.read_parquet(B_LAYER_POP)
    b_map = dict(zip(b_pop[~b_pop["is_npl"]]["cited_doc_id"], b_pop[~b_pop["is_npl"]]["cited_id"]))
    for doc, cid in b_map.items():
        cited_map.setdefault(doc, cid)

    g = Graph()
    for p, ns in (("ont", ONT), ("data", S.DATA), ("owl", str(OWL)), ("rdfs", str(RDFS)),
                  ("skos", str(SKOS)), ("dcterms", DCTERMS)):
        g.bind(p, ns)
    R = lambda n: URIRef(ONT + n)  # noqa: E731

    stat = Counter()
    concept_hits = Counter()
    b_claims: Counter = Counter()   # CR-011 — B층 cited_doc_id → 발행된 Claim 수
    # CR-017 투영 — 그래프에 넣는 것과 **같은 값**을 같은 자리에서 모은다. 따로 세면 갈라진다.
    proj: list[dict] = []
    claim_attr: dict[str, dict] = {}   # claim IRI 지역명 → 청구항 수준 속성
    seen_feature: set[str] = set()     # 같은 feature 가 두 행에서 나와도 parquet 행은 하나
    rows = [json.loads(line) for line in FEATURES.open()]
    seen_claim: set[str] = set()
    # CR-019 — 중복 입력 행의 계수. rdflib 는 같은 트리플을 합치므로 **방출 횟수를 세는
    # 계수기는 그래프를 기술하지 않는다.** 고유 기준으로 세되, 버려지는 방출은 지우지 않고
    # 따로 계상한다 — 조용히 합치면 다음 진단이 막힌다(D-25).
    seen_row: set[tuple] = set()
    dupstat = _duplicate_key_stats(rows)
    # 실재하는 청구항 IRI 집합 — dependsOnClaim 이 매달린 부모(존재하지 않는 참조 번호)를
    # 만들지 않도록. 일부 거절특허는 청구항 재번호/OCR 로 존재하지 않는 부모항을 참조한다.
    present_claims = {f"claim/{_slug(r['patent'])}_c{r['claim_no']}" for r in rows}

    for r in rows:
        pat = _patent_iri(r["patent"], cited_map)
        if pat is None:
            stat["patent_unresolved"] += 1
            continue
        pslug = _slug(r["patent"])
        cno = r["claim_no"]
        # CR-019 — 같은 (patent, claim_no) 가 두 번 오면 아래 루프들이 같은 트리플을 다시
        # add 한다. 그래프는 합쳐져 멀쩡하므로 **add 는 그대로 두고 계수만 가른다.**
        row_first = (r["patent"], cno) not in seen_row
        seen_row.add((r["patent"], cno))
        claim = _u(f"claim/{pslug}_c{cno}")
        if str(claim) not in seen_claim:
            dep = r.get("depends_on") or []
            g.add((claim, RDF.type, R("Claim")))
            g.add((claim, R("claimNumber"), Literal(int(cno), datatype=XSD.integer)))
            g.add((claim, R("isIndependent"), Literal(not dep, datatype=XSD.boolean)))
            g.add((pat, R("hasClaim"), claim))
            # 종속항 → 부모 청구항(같은 특허, claims_full 의 depends_on). 완전 한정요소집합의 상속 축.
            # 실재하는 부모에만 연결 — 존재하지 않는 참조 번호는 매달린 IRI 를 낳으므로 버리고 계상.
            for parent_no in dep:
                pkey = f"claim/{pslug}_c{parent_no}"
                if pkey in present_claims:
                    g.add((claim, R("dependsOnClaim"), _u(pkey)))
                    stat["depends_on_claim"] += 1
                else:
                    stat["depends_on_claim_dangling"] += 1
            claim_attr[f"{pslug}_c{cno}"] = {
                "is_independent": not dep,
                "depends_on_claim": sorted(f"{pslug}_c{p}" for p in dep
                                           if f"claim/{pslug}_c{p}" in present_claims),
            }
            seen_claim.add(str(claim))
            stat["claims"] += 1
            stat["claims_dependent" if dep else "claims_independent"] += 1
            # CR-011 출력 (2) — B층 문헌별 발행 청구항 수. 조용히 빠뜨리지 않기 위한 계수다.
            if r["patent"].startswith("cited:"):
                doc = r["patent"][len("cited:"):]
                if doc in b_map:
                    b_claims[doc] += 1

        feat_iris: list[tuple[URIRef, dict]] = []
        for f in r["features"]:
            fi = _u(f"feature/{pslug}_c{cno}_f{f['seq']}")
            # CR-019 — dedup 판정을 **계수와 투영이 공유한다.** 판정을 둘 두면 다시 갈리고,
            # 갈린 상태가 D-41 이었다(계수기는 방출을, 투영은 고유를 셌다).
            fkey = f"{pslug}_c{cno}_f{f['seq']}"
            first = fkey not in seen_feature
            g.add((fi, RDF.type, R("ClaimFeature")))
            g.add((fi, R("featureSeq"), Literal(int(f["seq"]), datatype=XSD.integer)))
            g.add((fi, R("featureText"), Literal(f["text"])))
            g.add((fi, R("decompositionMethod"), Literal(r["method"])))
            g.add((fi, DCTERMS.license, Literal(LICENSE, datatype=XSD.string)))
            g.add((claim, R("hasFeature"), fi))
            if first:
                stat["features"] += 1
            else:
                stat["features_duplicate_emissions"] += 1
            # feature → 개념 정규화
            fconcepts: set[str] = set()
            fconcept_type: dict[str, str] = {}
            for term, hits in br.extract_from_text(f["text"]).items():
                for nid, typ in hits:
                    if typ in CONCEPT_TYPES:
                        g.add((fi, R("featureConcept"), _u(nid)))
                        fconcepts.add(nid)
                        # 한 개념이 두 유형으로 오면 **먼저 온 것을 쓴다** — 마지막 승자
                        # 방식은 추출 순서에 흔들려 결정성을 깬다.
                        fconcept_type.setdefault(nid, typ)
                        stat["concept_hits_raw"] += 1
            # 개념 계수는 **(feature, concept) 고유**로 센다. 한 feature 가 같은 개념을 여러
            # 표면형으로 맞추면("EUV 포토레지스트"·"포토레지스트") 적중은 여럿이지만 그래프에
            # 남는 트리플은 하나다. 계수는 그래프가 세는 것과 같은 것을 세야 한다.
            if first:
                for nid in sorted(fconcepts):
                    concept_hits[fconcept_type[nid]] += 1
            # CR-017 투영 행. 원문(f["text"])은 **싣지 않는다** — 비목표 ⓐ.
            if first:
                seen_feature.add(fkey)
                ca = claim_attr.get(f"{pslug}_c{cno}", {})
                proj.append({
                    "publication_id": str(pat).rsplit("/", 1)[-1],
                    "side": pslug.split("_", 1)[0],
                    "claim_id": f"{pslug}_c{cno}",
                    "claim_number": int(cno),
                    "is_independent": bool(ca.get("is_independent", True)),
                    "feature_seq": int(f["seq"]),
                    "feature_concept": sorted(fconcepts),
                    "depends_on_claim": list(ca.get("depends_on_claim", [])),
                    "decomposition_method": r["method"],
                })
            feat_iris.append((fi, f))
        # dependsOnFeature — '상기 X' 참조를 같은 청구항 내 앞선 feature 에 best-effort 연결
        for idx, (fi, f) in enumerate(feat_iris):
            for ref in f.get("refs", []):
                for pj, pf in feat_iris[:idx]:
                    if ref and ref in pf["text"]:
                        g.add((fi, R("dependsOnFeature"), pj))
                        # CR-019 — 중복 행은 같은 트리플을 다시 add 한다. 그래프는 불변이고
                        # 계수만 겹쳤으므로 계수를 가른다.
                        stat["depends" if row_first else "depends_duplicate_emissions"] += 1
                        break

    # 거절-판단 패턴 → PriorArtJudgment. 두 원천을 union 한다:
    #  evidence_v2 (656행, GT — 노이즈 포함) + OCR 재추출 (거절결정 표, authoritative).
    # 키 (target특허, cited_doc, ground) 로 병합하고 청구항 집합을 합친다.
    judg: dict[tuple, set[int]] = {}
    ev = edges[edges["source_type"] == "evidence_v2"].drop_duplicates(["target_patent_id", "cited_id", "legal_basis"])
    for _, e in ev.iterrows():
        ground = GROUND.get(str(e["legal_basis"]))
        if ground is None:
            stat["judgment_no_ground"] += 1
            continue
        key = (str(e["target_patent_id"]), str(e["cited_doc_id"]), ground)  # ground = RejectionType 개체명
        cl = {int(x) for x in str(e["target_claims"] or "").split("|") if x.strip().isdigit()}
        judg.setdefault(key, set()).update(cl)
    # OCR 재추출 (data/interim/reextracted_judgments.jsonl). ground("§29②")를 evidence_v2 와
    # 같은 RejectionType 개체명으로 매핑해야 키가 병합되고 onGround IRI 가 유효해진다.
    rxf = ROOT / "data" / "interim" / "reextracted_judgments.jsonl"
    if rxf.exists():
        for line in rxf.open():
            r = json.loads(line)
            gr = GROUND.get(r["ground"])
            if gr is None:
                continue
            key = (f"patent:kr_{r['target_patent']}", str(r["cited_doc"]), gr)
            judg.setdefault(key, set()).update(int(x) for x in r["target_claims"])
            stat["reextract_rows"] += 1

    for (tgt_id, cited_doc, ground), claims in judg.items():
        canon = cited_map.get(cited_doc)
        if not canon:
            stat["judgment_cited_unresolved"] += 1
            continue
        tgt = _u(tgt_id.replace("patent:", "patent/"))
        cited = _u(canon.replace("patent:", "patent/"))
        j = _u(f"judgment/{_slug(tgt_id + '__' + cited_doc + '__' + ground)}")
        g.add((j, RDF.type, R("PriorArtJudgment")))
        g.add((j, R("onGround"), R(ground)))
        g.add((j, R("overPriorArt"), cited))
        g.add((tgt, R("hasJudgment"), j))
        stat["judgments"] += 1
        appno = tgt_id.replace("patent:kr_", "")
        for cn in sorted(claims):
            cl = _u(f"claim/{_slug('rej:'+appno)}_c{cn}")
            if str(cl) in seen_claim:
                g.add((j, R("aboutClaim"), cl))
                stat["about_claim"] += 1

    # CR-004R: RejectionReason 실체화 — reextract_claim_judgments.py --reasons-only 산출을 읽는다.
    # 입도 = 출원 × groundClause(조-항-호 전체) × 회차. 인용문헌 불필요(§29 한정 아님) — 그 조항이
    # 그 회차에 제기됐다는 사실만 기록한다. 기존 judg 루프(PriorArtJudgment·§29 한정)와 독립.
    reasons_f = ROOT / "data" / "interim" / "rejection_reasons.jsonl"
    if reasons_f.exists():
        for line in reasons_f.open():
            r = json.loads(line)
            if "_skipped_clauses" in r:
                continue
            app = r["application"]
            patent = _u(f"patent/kr_{app}")
            rr = _u(f"rejection/kr_{app}__{r['clause']}__r{r['notice_round']}")
            g.add((rr, RDF.type, R("RejectionReason")))
            g.add((rr, R("reasonGround"), R(r["reason_ground"])))
            g.add((rr, R("groundClause"), Literal(r["clause"], datatype=XSD.string)))
            g.add((rr, R("noticeRound"), Literal(int(r["notice_round"]), datatype=XSD.integer)))
            g.add((rr, R("noticeType"), Literal(r["notice_type"], datatype=XSD.string)))
            if r.get("notice_date"):
                g.add((rr, R("noticeDate"), Literal(r["notice_date"], datatype=XSD.date)))
            g.add((patent, R("rejectionEvidence"), rr))
            stat["rejection_reasons"] += 1

    _b_loss_report(b_pop, b_claims)

    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(str(OUT_TTL), format="turtle")
    projection = _emit_projection(proj, _sha256(OUT_TTL))
    report = {
        "_README": "CR-019 — `counts.*` 와 `feature_concept_by_type` 은 **그래프 고유 기준**이고 "
                   "(rdflib 가 같은 트리플을 합치므로 방출 횟수는 그래프를 기술하지 않는다), "
                   "`*_duplicate_emissions`·`concept_hits_raw` 는 버리지 않고 계상한 재방출이다. "
                   "**두 계열을 더하지 말 것.** `input_claims` 는 원천 행 수라 고유 청구항 수와 "
                   "`input_duplicate_keys` 만큼 다르다.",
        "triples": len(g), "input_claims": len(rows),
        "counts": {**dict(stat),
                   "input_duplicate_keys": dupstat["input_duplicate_keys"],
                   "input_duplicate_rows": dupstat["input_duplicate_rows"]},
        "feature_concept_by_type": dict(concept_hits.most_common()),
        "duplicate_keys_by_side": dupstat["duplicate_keys_by_side"],
        "projection_cr017": projection,
        "note": "feature 정규화 = build_abox_patents 와 동일 브리지. 판단 = evidence_v2 실체화. "
                "RejectionReason = rejection_reasons.jsonl 실체화(CR-004R).",
    }
    # 계수와 투영이 어긋나면 **쓰지 않는다** — 틀린 숫자를 발행하느니 산출물이 없는 편이 낫다.
    _assert_count_integrity(report)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"✓ ({len(g):,} 트리플) → {OUT_TTL.name}")
    print(f"  claims={stat['claims']} features={stat['features']} depends={stat['depends']}")
    print(f"  judgments={stat['judgments']} about_claim={stat['about_claim']}")
    print(f"  rejection_reasons={stat['rejection_reasons']}")
    print(f"  featureConcept by type: {dict(concept_hits.most_common(6))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
