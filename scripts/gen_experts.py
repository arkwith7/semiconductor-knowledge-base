#!/usr/bin/env python3
"""Build deliverable ② — 100 synthetic semiconductor domain expert profiles.

The plan commits to a *de-identified, domain-expert-reviewed synthetic* cohort,
not real PII. Profiles are deterministic given SEED and reproducible from the
SIRP + baseline data already on disk:

  - Skill domains are drawn from SDKB Process / SubProcess / EquipmentClass nodes
    (data/semiconductor_v0_3.json).
  - Process-family weights track the SIRP empirical distribution
    (data/patents/rejected_patents_meta.parquet) so that the synthetic cohort's
    expertise mass aligns with the technical problems it will be matched to.
  - Years of experience, retiree status, region, jurisdiction, and certifications
    are sampled from calibrated distributions documented inline.

Output:
  data/expert_profiles.parquet  — 100 rows
  data/experts_report.json       — distribution checks + caveats

The expert validation log (docs/expert_validation_log.md) is the human-side
audit trail; this generator produces the substrate that experts review.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN_BASELINE = ROOT / "data" / "semiconductor_v0_3.json"
IN_PATENTS = ROOT / "data" / "patents" / "rejected_patents_meta.parquet"
OUT_PARQUET = ROOT / "data" / "expert_profiles.parquet"
OUT_REPORT = ROOT / "data" / "experts_report.json"

N_EXPERTS = 100
SEED = 20260512

# ── Sampling distributions (calibrated, documented) ────────────────

# Korean semiconductor industry context: 소부장 SME tilt + chaebol R&D centers.
# Region distribution roughly mirrors Korean semiconductor employer geography.
REGION_WEIGHTS = {
    "경기 화성/평택":      0.22,  # Samsung/SK fab clusters
    "경기 이천/청주":      0.10,  # SK hynix M-series
    "수도권 (서울/판교)": 0.18,  # design/EDA/IP houses
    "충청남도 (천안/아산)": 0.10,  # equipment & materials SMEs
    "경상남도 (구미/창원)": 0.08,
    "대전":               0.08,  # ETRI/KAIST surroundings
    "해외 (한국계 기업)":  0.10,
    "그 외 지방":         0.14,
}

# Firm-type distribution: emphasizes 소부장 SME per the plan's customer focus.
FIRM_TYPE_WEIGHTS = {
    "소부장 SME":           0.42,
    "Foundry/IDM 사내":     0.18,
    "장비 OEM":             0.10,
    "재료 공급사":          0.08,
    "팹리스 / 디자인하우스": 0.08,
    "OSAT":                0.04,
    "연구소 (출연/대학)":   0.06,
    "변리사·IP 컨설팅":     0.04,
}

# Education tier mix avoids the anti-pattern in expert_validation_log.md.
EDU_TIER_WEIGHTS = {
    "PhD":      0.20,
    "MSc":      0.35,
    "BSc":      0.32,
    "전문대/고졸+장기경력": 0.13,
}

# Korean export-control jurisdiction tags (governance-kr hooks)
# Subjects per-jurisdiction; "KR-only" is the modal experts can publicly engage.
JURISDICTION_PROFILES = [
    ("KR-only",     0.40),
    ("KR×JP",       0.20),
    ("KR×US",       0.20),
    ("KR×JP×US",    0.12),
    ("KR×CN",       0.08),
]

# Skill family canonical labels mapped to process_family tags in SIRP.
SKILL_FAMILIES = [
    "etch", "deposition", "metallization", "photo", "implant",
    "oxidation_diffusion", "memory", "materials", "packaging",
    "metrology", "general",
]


def _pick(weights: dict[str, float], rng: random.Random) -> str:
    keys = list(weights.keys())
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def _years_of_experience(rng: random.Random, retiree: bool) -> int:
    """Mixture-of-Gaussians–like sampler, then truncate to integer years."""
    if retiree:
        return rng.randint(28, 42)
    # Bimodal: junior (3–9) and senior (10–22) with a long tail.
    bucket = rng.choices(["junior", "senior", "veteran"],
                         weights=[0.45, 0.42, 0.13], k=1)[0]
    if bucket == "junior":
        return max(1, int(rng.gauss(6, 2)))
    if bucket == "senior":
        return max(8, int(rng.gauss(14, 3)))
    return max(18, int(rng.gauss(24, 4)))


def _load_process_family_weights() -> dict[str, float]:
    """Track SIRP family distribution so expert mass aligns with problem mass."""
    fallback = {fam: 1.0 for fam in SKILL_FAMILIES}
    if not IN_PATENTS.exists():
        return fallback
    df = pd.read_parquet(IN_PATENTS)
    counts = df["process_family"].value_counts().to_dict()
    weights = {fam: float(counts.get(fam, 0) + 1) for fam in SKILL_FAMILIES}
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def _load_subprocess_pool() -> list[tuple[str, str]]:
    """Load (id, canonical_name) of SubProcess and EquipmentClass nodes."""
    if not IN_BASELINE.exists():
        return []
    with open(IN_BASELINE, encoding="utf-8") as f:
        g = json.load(f)
    pool = [
        (n["id"], n.get("canonical_name") or n["id"])
        for n in g.get("nodes", [])
        if n.get("type") in {"SubProcess", "EquipmentClass", "Material", "Metrology"}
    ]
    return pool


def _sample_skill_set(rng: random.Random, pool: list[tuple[str, str]],
                      primary_family: str, n_min: int = 3, n_max: int = 8) -> list[str]:
    """Pick 3–8 SDKB node IDs as the expert's deepest skills.

    Bias the pick toward the expert's primary process_family by string match in label.
    """
    if not pool:
        return []
    n = rng.randint(n_min, n_max)
    # Soft-prefer items whose label hints at the family
    fam_kw = primary_family.replace("_", " ")
    biased = [p for p in pool if fam_kw.split()[0] in p[1].lower()]
    others = [p for p in pool if p not in biased]
    rng.shuffle(biased)
    rng.shuffle(others)
    picks = (biased[: n // 2] + others)[:n]
    return [p[0] for p in picks]


def build_one(idx: int, rng: random.Random,
              fam_weights: dict[str, float],
              skill_pool: list[tuple[str, str]]) -> dict:
    expert_id = f"expert:syn_{idx:03d}"
    primary_family = rng.choices(list(fam_weights.keys()),
                                 weights=list(fam_weights.values()), k=1)[0]
    # 12% retirees per qualitative plan requirement (지식 재활용 생태계)
    retiree = rng.random() < 0.12
    yoe = _years_of_experience(rng, retiree)
    edu = _pick(EDU_TIER_WEIGHTS, rng)
    firm = _pick(FIRM_TYPE_WEIGHTS, rng)
    region = _pick(REGION_WEIGHTS, rng)
    jur_keys = [k for k, _ in JURISDICTION_PROFILES]
    jur_wts = [w for _, w in JURISDICTION_PROFILES]
    jur = rng.choices(jur_keys, weights=jur_wts, k=1)[0]

    skills = _sample_skill_set(rng, skill_pool, primary_family)
    # Skill claim sanity: cap distinct skills at YOE / 3 to avoid the anti-pattern.
    skill_cap = max(3, yoe // 3)
    if len(skills) > skill_cap:
        skills = skills[:skill_cap]

    # Certifications: stratified by yoe
    certs: list[str] = []
    if yoe >= 5 and rng.random() < 0.45:
        certs.append("사내 공정 자격 (Tier-1)")
    if yoe >= 10 and rng.random() < 0.30:
        certs.append("국가기술자격 (반도체장비)")
    if firm == "변리사·IP 컨설팅":
        certs.append("변리사")
    if yoe >= 15 and rng.random() < 0.15:
        certs.append("PMP")

    # Availability — 소부장 SME 컨설팅 수요 모델
    avail = rng.choices(["full-time", "part-time", "advisory"], weights=[0.55, 0.30, 0.15], k=1)[0]
    if retiree:
        avail = rng.choices(["advisory", "part-time"], weights=[0.70, 0.30], k=1)[0]

    # Hourly rate (KRW) — heuristic by yoe and firm
    base = 60_000 + yoe * 9_000
    if firm == "변리사·IP 컨설팅":
        base += 40_000
    if firm in {"Foundry/IDM 사내", "장비 OEM"}:
        base += 15_000
    rate = int(base * rng.uniform(0.85, 1.20))

    # Sensitive-attribute proxies for the AFCP compliance gate
    has_nct_exposure = primary_family in {"memory", "etch", "deposition", "metallization"} and yoe >= 12
    return {
        "expert_id": expert_id,
        "primary_process_family": primary_family,
        "years_of_experience": yoe,
        "retiree": retiree,
        "education_tier": edu,
        "firm_type": firm,
        "region": region,
        "jurisdiction_profile": jur,
        "skill_node_ids": "|".join(skills),
        "n_skills": len(skills),
        "certifications": "|".join(certs),
        "availability": avail,
        "hourly_rate_krw": rate,
        "nct_exposure_flag": has_nct_exposure,
        "interpretation_type": "author-defined",
        "validation_required": True,  # all profiles need expert review before unlock
        "source": "scripts/gen_experts.py",
        "seed": SEED,
    }


def main() -> None:
    rng = random.Random(SEED)
    fam_weights = _load_process_family_weights()
    skill_pool = _load_subprocess_pool()
    rows = [build_one(i, rng, fam_weights, skill_pool) for i in range(N_EXPERTS)]
    df = pd.DataFrame(rows)
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)

    # Distribution report
    report = {
        "seed": SEED,
        "n_experts": int(len(df)),
        "primary_family_distribution": dict(Counter(df["primary_process_family"])),
        "firm_type_distribution": dict(Counter(df["firm_type"])),
        "education_tier_distribution": dict(Counter(df["education_tier"])),
        "region_distribution": dict(Counter(df["region"])),
        "jurisdiction_distribution": dict(Counter(df["jurisdiction_profile"])),
        "retiree_count": int(df["retiree"].sum()),
        "yoe_stats": {
            "min": int(df["years_of_experience"].min()),
            "mean": round(float(df["years_of_experience"].mean()), 2),
            "max": int(df["years_of_experience"].max()),
        },
        "n_skills_stats": {
            "min": int(df["n_skills"].min()),
            "mean": round(float(df["n_skills"].mean()), 2),
            "max": int(df["n_skills"].max()),
        },
        "hourly_rate_stats": {
            "min": int(df["hourly_rate_krw"].min()),
            "median": int(df["hourly_rate_krw"].median()),
            "max": int(df["hourly_rate_krw"].max()),
        },
        "anti_pattern_checks": {
            "all_same_education": int(df["education_tier"].nunique() == 1),
            "all_metro_region": int(
                df["region"].isin({"수도권 (서울/판교)", "경기 화성/평택", "경기 이천/청주"}).all()
            ),
            "no_retirees": int(df["retiree"].sum() == 0),
        },
        "output": str(OUT_PARQUET.relative_to(ROOT)),
        "caveat": "Synthetic, de-identified profiles for benchmarking only. Expert review log "
                  "(docs/expert_validation_log.md) is the authoritative audit trail before any "
                  "downstream use.",
    }
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"✓ Expert profiles ({len(df)} rows) → {OUT_PARQUET.relative_to(ROOT)}")
    print(f"  retirees: {report['retiree_count']}, regions: {df['region'].nunique()}, "
          f"education tiers: {df['education_tier'].nunique()}")
    print(f"  yoe: min={report['yoe_stats']['min']}, "
          f"mean={report['yoe_stats']['mean']}, max={report['yoe_stats']['max']}")
    # Surface any anti-pattern hits
    for k, v in report["anti_pattern_checks"].items():
        if v:
            print(f"⚠ anti-pattern triggered: {k} — investigate before review session")


if __name__ == "__main__":
    main()
