"""KIPRIS Plus API로 반도체 거절특허 데이터셋을 단계적으로 확장.

호출 한도 운영 원칙
====================
- 프로필 기본값: ``--profile free`` 는 ``--interval 0.6`` / ``--max-api-calls 150``,
    ``--profile paid`` 는 ``--interval 0.4`` / ``--max-api-calls 600``.
- 수동 오버라이드: ``--interval``, ``--max-api-calls`` 를 직접 주면 프로필 기본값보다 우선.
- 호출 1건당 정보 최대 추출: ``getBibliographyDetailInfoSearch`` 1회로 IPC + claim1 +
  abstract + 인용문헌(`priorArtDocumentsInfoArray`)을 모두 추출. 별도
  ``getClaimInfoSearch`` 호출 없음.
- 거절결정서 REST(`IntermediateDocumentREService`)는 confirmed 후보에 한해 ``--collect-admin-docs``
  플래그가 켜진 경우에만 호출.

전략 (collection plan, 단계적 확장)
===================================
기본 계획은 ``etch_poc`` 이지만, 상용 도메인 데이터셋용으로는
``semiconductor_commercial`` 플랜을 사용한다.

- stage 1: 식각(Etch) 검증 전략 우선
- stage 2: 인접 공정(증착/포토) 확장
- stage 3: 전공정 전반(세정/CMP, 산화/확산, 이온주입, 금속배선) 확장
- stage 4: 후공정 + 소재/부품/장비(MPE) 확장

각 stage는 앞 단계에서 목표 건수를 채우지 못했을 때만 실행한다.

후보 필터링 (사전)
==================
검색 결과 단계에서 다음을 통과한 후보에만 biblio detail 호출(=API 호출 절약).

1. ``application_number`` 가 기존 JSONL의 seen set에 없을 것.
2. ``registerStatus`` 가 거절/rejected 패턴을 포함할 것.
3. ``openDate`` 또는 ``applicationDate`` 가 ``--year-min``/``--year-max`` 범위.
4. stage별 keyword gate가 title/abstract에 1개 이상.

후보 필터링 (사후, biblio 결과 기반)
====================================
- ``priorArtDocumentsInfoArray`` 에서 ``examinerQuotationFlag = 'Y'`` 인 항목 ≥1.
- ``claim1`` 추출 성공 (claimInfoArray).

스키마 정합성
=============
기존 JSONL 구조를 유지하되, 도메인/공정/가치사슬 메타를 추가 기록한다.

- ``meta.source = "kipris_plus_api"`` (기존 ``"kipris_web_advanced_search"`` 와 분리)
- ``ground_truth_evidence = []`` (API에서는 OCR 인용 문구 미제공; ``meta.notes`` 로 명시)
- ``meta.evidence_document_url`` 와 ``meta.admin_documents`` 는 거절결정서 REST 결과로
  채우거나 빈 값.

레코드는 atomic append: 한 건 확정될 때마다 즉시 JSONL 끝에 한 줄 기록한다.
중간에 quota/오류로 끊겨도 이미 확정된 레코드는 보존된다.

사용 예
=======

    .venv/bin/python scripts/expand_dataset_via_api.py --dry-run --max-api-calls 5
    .venv/bin/python scripts/expand_dataset_via_api.py --collection-plan etch_poc --target 100
    .venv/bin/python scripts/expand_dataset_via_api.py --collection-plan semiconductor_commercial --target 300 --profile paid --max-api-calls 400

확장 후 후속 산출물 동기화:

    .venv/bin/python scripts/build_manifest.py
    .venv/bin/python scripts/build_etching_corpus.py --include-unresolved --fresh
    .venv/bin/python scripts/eval_recall_baseline.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from kipris_dataset.kipris import (  # noqa: E402
    KiprisClient,
    KiprisQuotaExceeded,
    KiprisServiceKeyError,
)
from kipris_dataset.rejection_decision import (  # noqa: E402
    BASE_URL as REJ_BASE_URL,
    RejectionDecisionClient,
)

DEFAULT_DATASET = REPO_ROOT / "data/processed/etching_reject_web_poc_dataset.jsonl"
SEMICONDUCTOR_DATASET = REPO_ROOT / "data/processed/semiconductor_industry_rejected_patents.jsonl"
DEFAULT_TARGET = 100
PROFILE_PRESETS: Dict[str, Dict[str, float | int]] = {
    "free": {"interval": 0.6, "max_api_calls": 150},
    "paid": {"interval": 0.4, "max_api_calls": 600},
}
DEFAULT_PROFILE = "free"
DEFAULT_MAX_API_CALLS = int(PROFILE_PRESETS[DEFAULT_PROFILE]["max_api_calls"])
DEFAULT_INTERVAL = float(PROFILE_PRESETS[DEFAULT_PROFILE]["interval"])
DEFAULT_ROWS = 30
DEFAULT_MAX_PAGES = 30
DEFAULT_MAX_CANDIDATES_PER_PAGE = 15
DEFAULT_YEAR_MIN = 2015
DEFAULT_YEAR_MAX = 2024
DEFAULT_MAX_NEW_STRATEGY_SHARE = 0.55
DEFAULT_GUARDRAIL_WARMUP = 20
DEFAULT_PROGRESS_FILE = REPO_ROOT / "data/processed/expand_dataset_progress.json"
DEFAULT_MAX_NO_ADD_PAGES_PER_STRATEGY = 8
DEFAULT_MIN_BIBLIO_ATTEMPTS_BEFORE_DISABLE = 6
DEFAULT_MIN_STRATEGY_YIELD = 0.2
DEFAULT_MIN_SEARCH_CANDIDATES_BEFORE_DISABLE = 60

REJECTED_PATTERNS = ("거절", "rejected", "reject")
# pre-filter에서 명백히 비거절인 케이스만 차단 (검색 응답의 registerStatus가 비어 있는
# 경우가 많아 거절 여부는 biblio detail에서 권위적으로 확정한다).
NON_REJECTED_EXPLICIT = (
    "공개",
    "공고",
    "출원",
    "심사중",
    "등록",
    "소멸",
    "무효",
    "취하",
    "포기",
)

STRATEGY_LIBRARY: Dict[str, Dict[str, Any]] = {
    "plasma_H01J37": {
        "name": "plasma_H01J37",
        "keyword": "플라즈마 식각",
        "ipcNumber": "H01J37",
        "validated_web_query": '(플라즈마 식각+"plasma etch"+RIE)*(반도체+웨이퍼)',
        "keyword_gate": (
            "식각",
            "에칭",
            "plasma",
            "etch",
            "rie",
            "웨이퍼",
            "반도체",
            "원자층 식각",
            "챔버",
            "샤워헤드",
        ),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "사전 세정"),
        "process_family": "etch",
        "value_chain": ["process", "equipment"],
        "validation_status": "validated",
    },
    "wet_solution_kw": {
        "name": "wet_solution_kw",
        "keyword": "식각 용액",
        "ipcNumber": None,
        "validated_web_query": '(습식 식각+식각 용액+에칭 용액)*(반도체+질화막+산화막)',
        "keyword_gate": ("식각", "에칭", "질화막", "산화막", "용액", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화"),
        "process_family": "etch",
        "value_chain": ["process", "material"],
        "validation_status": "validated",
    },
    "profile_H01L21": {
        "name": "profile_H01L21",
        "keyword": "반도체 트렌치 식각",
        "ipcNumber": "H01L21",
        "validated_web_query": '(반도체+식각+트렌치)*(측벽+선택비+프로파일+패턴)',
        "keyword_gate": (
            "식각",
            "트렌치",
            "측벽",
            "프로파일",
            "선택비",
            "반도체",
            "채널",
            "패턴",
            "정지막",
        ),
        "negative_gate": (
            "패키지",
            "몰딩",
            "본딩",
            "캡슐화",
            "팬-아웃",
            "관통 전극",
            "디스플레이",
            "드라이버",
        ),
        "process_family": "etch",
        "value_chain": ["process", "device"],
        "validation_status": "live-tuned-20260505",
    },
    "depo_plasma_C23C": {
        "name": "depo_plasma_C23C",
        "keyword": "플라즈마 증착 PECVD",
        "ipcNumber": "C23C",
        "validated_web_query": '(플라즈마 증착+PECVD+"plasma enhanced CVD")*(반도체+웨이퍼+박막)',
        "keyword_gate": (
            "증착",
            "pecvd",
            "박막",
            "플라즈마",
            "반도체",
            "웨이퍼",
            "샤워헤드",
            "절연막",
            "기판",
        ),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "연료전지", "촉매", "디스플레이"),
        "process_family": "deposition",
        "value_chain": ["process", "equipment", "material"],
        "validation_status": "parked-no-yield-20260505",
    },
    "depo_ald_precursor": {
        "name": "depo_ald_precursor",
        "keyword": "게이트 유전막 형성",
        "ipcNumber": "H01L21",
        "validated_web_query": '(게이트+유전막+절연막)*(성막+증착+CVD)*(반도체+메모리)',
        "keyword_gate": ("유전막", "절연막", "성막", "증착", "퇴적", "cvd", "게이트"),
        "negative_gate": (
            "패키지",
            "몰딩",
            "본딩",
            "캡슐화",
            "디스플레이",
            "유기 발광",
            "표시 장치",
            "태양전지",
            "밀봉막",
        ),
        "process_family": "deposition",
        "value_chain": ["process", "device", "material"],
        "validation_status": "live-validated-20260505",
    },
    "photo_resist_G03F7": {
        "name": "photo_resist_G03F7",
        "keyword": "반도체 포토레지스트",
        "ipcNumber": "G03F7",
        "validated_web_query": '(포토레지스트+감광막+"photo resist")*(반도체+패턴+노광+현상)',
        "keyword_gate": ("포토", "레지스트", "감광", "노광", "리소그래피", "패턴", "반도체"),
        "negative_gate": (
            "패키지",
            "몰딩",
            "본딩",
            "캡슐화",
            "디스플레이",
            "인쇄",
            "배선 기판",
            "솔더",
            "경화막",
        ),
        "process_family": "photo",
        "value_chain": ["process", "material"],
        "validation_status": "parked-no-yield-20260505",
    },
    "photo_euv_patterning": {
        "name": "photo_euv_patterning",
        "keyword": "반도체 리소그래피 공정",
        "ipcNumber": "H01L21",
        "validated_web_query": '(리소그래피+노광+패터닝)*(반도체+웨이퍼+공정)',
        "keyword_gate": ("리소그래피", "노광", "레지스트", "감광", "현상"),
        "negative_gate": (
            "패키지",
            "몰딩",
            "본딩",
            "캡슐화",
            "팬-아웃",
            "다이 스택",
            "디스플레이",
            "인쇄",
            "배선 기판",
            "포토다이오드",
            "본드 패드",
        ),
        "process_family": "photo",
        "value_chain": ["process", "equipment"],
        "validation_status": "parked-low-precision-20260505",
    },
    "photo_resist_pattern_H01L21": {
        "name": "photo_resist_pattern_H01L21",
        "keyword": "반도체 포토레지스트 패터닝",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("포토", "레지스트", "패터닝", "노광", "현상", "반도체", "웨이퍼"),
        "negative_gate": (
            "패키지",
            "몰딩",
            "본딩",
            "캡슐화",
            "디스플레이",
            "인쇄",
            "배선 기판",
            "솔더",
            "컬러 필터",
        ),
        "process_family": "photo",
        "value_chain": ["process", "material"],
        "validation_status": "tuned-20260506",
    },
    "photo_mask_align_H01L21": {
        "name": "photo_mask_align_H01L21",
        "keyword": "반도체 노광 정렬 마스크",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("노광", "정렬", "마스크", "포토", "리소그래피", "반도체"),
        "negative_gate": (
            "패키지",
            "몰딩",
            "본딩",
            "캡슐화",
            "디스플레이",
            "인쇄",
            "배선 기판",
            "컬러 필터",
        ),
        "process_family": "photo",
        "value_chain": ["process", "equipment"],
        "validation_status": "tuned-20260506",
    },
    "clean_cmp_surface": {
        "name": "clean_cmp_surface",
        "keyword": "반도체 CMP 세정 슬러리 평탄화",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("cmp", "연마", "세정", "평탄화", "슬러리", "반도체", "웨이퍼"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "clean_cmp",
        "value_chain": ["process", "material", "equipment"],
        "validation_status": "tuned-20260506",
    },
    "cmp_postclean_H01L21": {
        "name": "cmp_postclean_H01L21",
        "keyword": "반도체 CMP 후세정",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("cmp", "후세정", "세정", "슬러리", "평탄화", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "clean_cmp",
        "value_chain": ["process", "material", "equipment"],
        "validation_status": "tuned-20260506",
    },
    "oxidation_diffusion_H01L21": {
        "name": "oxidation_diffusion_H01L21",
        "keyword": "산화 확산 열처리 반도체",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("산화", "확산", "열처리", "게이트 산화막", "반도체"),
        "negative_gate": ("패키지", "몰딩", "캡슐화", "열 확산기", "heat spreader", "본딩"),
        "process_family": "oxidation_diffusion",
        "value_chain": ["process", "equipment"],
        "validation_status": "draft",
    },
    "implant_H01L21": {
        "name": "implant_H01L21",
        "keyword": "이온 주입 도핑 반도체",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("이온 주입", "도핑", "implant", "반도체", "웨이퍼"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화"),
        "process_family": "implant",
        "value_chain": ["process", "equipment"],
        "validation_status": "draft",
    },
    "metallization_C23C": {
        "name": "metallization_C23C",
        "keyword": "반도체 금속 배선 증착",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("금속", "배선", "증착", "박막", "도전막", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "metallization",
        "value_chain": ["process", "material"],
        "validation_status": "tuned-20260506",
    },
    "package_bond_B23K": {
        "name": "package_bond_B23K",
        "keyword": "반도체 패키지 본딩 기판",
        "ipcNumber": "B23K",
        "validated_web_query": '',
        "keyword_gate": ("패키지", "본딩", "패키징", "기판", "반도체"),
        "process_family": "packaging",
        "value_chain": ["process", "component", "equipment"],
        "validation_status": "draft",
    },
    "backend_rdl_interposer_H01L23": {
        "name": "backend_rdl_interposer_H01L23",
        "keyword": "반도체 인터포저 재배선",
        "ipcNumber": "H01L23",
        "validated_web_query": '',
        "keyword_gate": ("인터포저", "재배선", "범프", "반도체", "패키지"),
        "negative_gate": ("디스플레이", "인쇄회로", "pcb", "커넥터", "몰딩"),
        "process_family": "backend_packaging",
        "value_chain": ["process", "component", "material"],
        "validation_status": "tuned-20260506",
    },
    "material_wafer_H01L21": {
        "name": "material_wafer_H01L21",
        "keyword": "반도체 웨이퍼 기판 에피택시",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("웨이퍼", "에피", "에피택셜", "기판", "실리콘", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "materials",
        "value_chain": ["material"],
        "validation_status": "tuned-20260506",
    },
    "material_compound_epi_H01L21": {
        "name": "material_compound_epi_H01L21",
        "keyword": "반도체 SiC GaN 에피 웨이퍼",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("sic", "gan", "에피", "웨이퍼", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "materials",
        "value_chain": ["material", "process"],
        "validation_status": "tuned-20260506",
    },
    "component_chamber_H01J37": {
        "name": "component_chamber_H01J37",
        "keyword": "반도체 정전척 샤워헤드 포커스링",
        "ipcNumber": "H01J37",
        "validated_web_query": '',
        "keyword_gate": ("챔버", "정전척", "포커스", "식각", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "components",
        "value_chain": ["component"],
        "validation_status": "tuned-20260506",
    },
    "component_esc_susceptor_H01J37": {
        "name": "component_esc_susceptor_H01J37",
        "keyword": "반도체 정전척 서셉터",
        "ipcNumber": "H01J37",
        "validated_web_query": '',
        "keyword_gate": ("정전척", "서셉터", "척", "반도체", "웨이퍼"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "components",
        "value_chain": ["component", "equipment"],
        "validation_status": "tuned-20260506",
    },
    "equipment_cluster_H01J37": {
        "name": "equipment_cluster_H01J37",
        "keyword": "반도체 웨이퍼 처리 장비 로드락",
        "ipcNumber": "H01J37",
        "validated_web_query": '',
        "keyword_gate": ("장비", "로드락", "플라즈마", "반도체", "웨이퍼"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "equipment",
        "value_chain": ["equipment"],
        "validation_status": "tuned-20260506",
    },
    "equipment_vacuum_transfer_H01J37": {
        "name": "equipment_vacuum_transfer_H01J37",
        "keyword": "반도체 진공 이송 로드락 장비",
        "ipcNumber": "H01J37",
        "validated_web_query": '',
        "keyword_gate": ("진공", "이송", "로드락", "장비", "반도체", "웨이퍼"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "equipment",
        "value_chain": ["equipment", "process"],
        "validation_status": "tuned-20260506",
    },
    # ── 온톨로지 확장 전략 (2026-05-08 추가) ────────────────────────────────
    # 3D 통합 / 인터커넥트
    "tsv_wafer_bonding_H01L21": {
        "name": "tsv_wafer_bonding_H01L21",
        "keyword": "반도체 TSV 관통전극 웨이퍼 본딩",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("tsv", "관통전극", "관통 비아", "웨이퍼 본딩", "직접 본딩", "하이브리드 본딩", "3d", "반도체", "웨이퍼", "실리콘", "접합"),
        "negative_gate": ("디스플레이", "인쇄회로", "pcb", "커넥터", "납땜"),
        "process_family": "3d_integration",
        "value_chain": ["process", "equipment", "material"],
        "validation_status": "draft-20260508",
    },
    "interconnect_cu_lowk_H01L21": {
        "name": "interconnect_cu_lowk_H01L21",
        "keyword": "반도체 금속 배선 배리어 다마신",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("구리", "배선", "배리어", "다마신", "인터커넥트", "금속 배선", "배선층", "반도체", "도전막"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이", "pcb"),
        "process_family": "interconnect",
        "value_chain": ["process", "material"],
        "validation_status": "draft-20260508",
    },
    # 메모리 소자
    "memory_dram_cell_H01L27": {
        "name": "memory_dram_cell_H01L27",
        "keyword": "DRAM 셀 커패시터 반도체 메모리",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": ("dram", "디램", "커패시터", "메모리 셀", "비트라인", "워드라인", "스토리지 노드"),
        "negative_gate": ("디스플레이", "인쇄회로", "pcb", "패키지 기판", "낸드"),
        "process_family": "memory_dram",
        "value_chain": ["device", "process"],
        "validation_status": "draft-20260508",
    },
    "memory_nand_flash_H01L29": {
        "name": "memory_nand_flash_H01L29",
        "keyword": "반도체 플래시 메모리 셀 트랜지스터",
        "ipcNumber": "H01L29",
        "validated_web_query": '',
        "keyword_gate": ("nand", "낸드", "플래시 메모리", "플로팅 게이트", "전하포획", "3d nand", "v-nand", "ctl", "메모리", "반도체", "트랜지스터", "셀"),
        "negative_gate": ("디스플레이", "인쇄회로", "pcb", "패키지 기판", "디램"),
        "process_family": "memory_nand",
        "value_chain": ["device", "process"],
        "validation_status": "draft-20260508",
    },
    # 첨단 로직 소자
    "logic_finfet_gaa_H01L29": {
        "name": "logic_finfet_gaa_H01L29",
        "keyword": "반도체 트랜지스터 게이트 채널",
        "ipcNumber": "H01L29",
        "validated_web_query": '',
        "keyword_gate": ("finfet", "핀펫", "gaa", "게이트 올 어라운드", "나노시트", "나노와이어", "게이트 스택", "high-k", "트랜지스터", "게이트", "반도체", "채널"),
        "negative_gate": ("디스플레이", "인쇄회로", "pcb", "패키지", "몰딩", "디램", "낸드"),
        "process_family": "logic_device",
        "value_chain": ["device", "process"],
        "validation_status": "draft-20260508",
    },
    "contact_silicide_H01L21": {
        "name": "contact_silicide_H01L21",
        "keyword": "반도체 컨택 금속 접합 오믹",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("컨택", "실리사이드", "오믹", "자기정합", "살리사이드", "접합 저항", "반도체", "금속", "접합", "도전", "저항"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "logic_device",
        "value_chain": ["process", "material"],
        "validation_status": "draft-20260508",
    },
    # 전력 반도체
    "power_device_igbt_H01L29": {
        "name": "power_device_igbt_H01L29",
        "keyword": "반도체 전력 소자 트랜지스터",
        "ipcNumber": "H01L29",
        "validated_web_query": '',
        "keyword_gate": ("전력", "igbt", "mosfet", "sic", "갈륨 나이트라이드", "드리프트층", "항복전압", "반도체", "트랜지스터", "소자", "다이오드"),
        "negative_gate": ("디스플레이", "인쇄회로", "pcb", "패키지 기판"),
        "process_family": "power_device",
        "value_chain": ["device", "process", "material"],
        "validation_status": "draft-20260508",
    },
    # MEMS / 센서
    "mems_sensor_B81B": {
        "name": "mems_sensor_B81B",
        "keyword": "MEMS 마이크로구조 압력센서 가속도계",
        "ipcNumber": "B81B",
        "validated_web_query": '',
        "keyword_gate": ("mems", "마이크로 구조", "압력 센서", "가속도계", "자이로", "멤스", "마이크로머시닝", "마이크로", "센서", "실리콘", "기판", "구조물", "소자"),
        "negative_gate": ("패키지", "디스플레이", "인쇄회로"),
        "process_family": "mems",
        "value_chain": ["device", "process"],
        "validation_status": "draft-20260508",
    },
    # 검사 / 계측
    "inspection_metrology_G01N": {
        "name": "inspection_metrology_G01N",
        "keyword": "반도체 검사 결함 측정",
        "ipcNumber": "G01N",
        "validated_web_query": '',
        "keyword_gate": ("결함 검사", "계측", "cd-sem", "ocd", "오버레이", "임계치수", "결함", "반도체", "검사", "측정", "웨이퍼"),
        "negative_gate": ("디스플레이", "인쇄회로", "pcb", "생물학", "의료"),
        "process_family": "inspection_metrology",
        "value_chain": ["equipment", "process"],
        "validation_status": "draft-20260508",
    },
    # 열처리 / 어닐링
    "thermal_anneal_H01L21": {
        "name": "thermal_anneal_H01L21",
        "keyword": "반도체 어닐링 열처리 RTP 급속열처리",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("어닐링", "열처리", "rtp", "급속열처리", "활성화 열처리", "스파이크"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "thermal",
        "value_chain": ["process", "equipment"],
        "validation_status": "draft-20260508",
    },
    # 에피택시
    "epitaxy_sige_H01L21": {
        "name": "epitaxy_sige_H01L21",
        "keyword": "반도체 SiGe 에피택시 선택성장",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("에피택시", "에피택셜 성장", "sige", "선택성장", "게르마늄", "변형 실리콘"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "epitaxy",
        "value_chain": ["process", "material"],
        "validation_status": "draft-20260508",
    },
    # 첨단 패키징
    "advanced_package_3d_H01L25": {
        "name": "advanced_package_3d_H01L25",
        "keyword": "반도체 패키지 적층 칩",
        "ipcNumber": "H01L25",
        "validated_web_query": '',
        "keyword_gate": ("3d 패키징", "hbm", "칩렛", "cowos", "foplp", "팬아웃", "2.5d", "어드밴스드 패키징", "패키지", "반도체", "적층", "칩", "다이"),
        "negative_gate": ("디스플레이", "인쇄회로", "pcb", "커넥터"),
        "process_family": "advanced_packaging",
        "value_chain": ["process", "component", "material"],
        "validation_status": "draft-20260508",
    },
    "flip_chip_bump_H01L24": {
        "name": "flip_chip_bump_H01L24",
        "keyword": "반도체 패키지 본딩 연결",
        "ipcNumber": "H01L24",
        "validated_web_query": '',
        "keyword_gate": ("플립칩", "범프", "언더필", "솔더 볼", "c4", "마이크로범프", "반도체", "패키지", "본딩", "연결", "솔더"),
        "negative_gate": ("디스플레이", "인쇄회로", "pcb"),
        "process_family": "advanced_packaging",
        "value_chain": ["process", "material"],
        "validation_status": "draft-20260508",
    },
    # 화합물 반도체
    "compound_semi_gaas_H01L21": {
        "name": "compound_semi_gaas_H01L21",
        "keyword": "화합물 반도체 GaAs InP III-V 에피",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("gaas", "갈륨비소", "inp", "iii-v", "화합물 반도체", "헤테로접합"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "compound_semiconductor",
        "value_chain": ["material", "device", "process"],
        "validation_status": "draft-20260508",
    },
    # EDA / 설계-공정 연계
    "design_drc_opc_G06F": {
        "name": "design_drc_opc_G06F",
        "keyword": "반도체 OPC DRC 설계 공정 보정",
        "ipcNumber": "G06F",
        "validated_web_query": '',
        "keyword_gate": ("opc", "drc", "설계 규칙", "공정 보정", "레이아웃 검증", "리소그래피 시뮬레이션"),
        "negative_gate": ("디스플레이", "인쇄회로", "소프트웨어 일반", "운영체제"),
        "process_family": "eda_design",
        "value_chain": ["design", "process"],
        "validation_status": "draft-20260508",
    },
    # 소재 / 전구체 / 슬러리
    "material_precursor_chem_C07F": {
        "name": "material_precursor_chem_C07F",
        "keyword": "반도체 ALD CVD 전구체 유기금속",
        "ipcNumber": "C07F",
        "validated_web_query": '',
        "keyword_gate": ("전구체", "유기금속", "ald", "cvd", "반도체 소재", "하프늄", "지르코늄"),
        "negative_gate": ("디스플레이", "촉매 일반", "의약", "농약"),
        "process_family": "materials",
        "value_chain": ["material"],
        "validation_status": "draft-20260508",
    },
    "material_slurry_cmp_C09G": {
        "name": "material_slurry_cmp_C09G",
        "keyword": "반도체 CMP 슬러리 연마재 첨가제",
        "ipcNumber": "C09G",
        "validated_web_query": '',
        "keyword_gate": ("슬러리", "연마재", "cmp", "연마 입자", "첨가제", "반도체"),
        "negative_gate": ("디스플레이", "페인트", "도료", "의약"),
        "process_family": "materials",
        "value_chain": ["material"],
        "validation_status": "draft-20260508",
    },
    # 이미지 센서 / RF
    "image_sensor_cmos_H01L27": {
        "name": "image_sensor_cmos_H01L27",
        "keyword": "CMOS 이미지 센서 픽셀 포토다이오드",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": ("이미지 센서", "cmos 이미지", "픽셀", "포토다이오드", "bsi", "dtis"),
        "negative_gate": ("디스플레이", "인쇄회로", "pcb"),
        "process_family": "image_sensor",
        "value_chain": ["device", "process"],
        "validation_status": "draft-20260508",
    },
    "rf_device_H01L29": {
        "name": "rf_device_H01L29",
        "keyword": "RF 반도체 HEMT 고주파 트랜지스터",
        "ipcNumber": "H01L29",
        "validated_web_query": '',
        "keyword_gate": ("rf", "hemt", "고주파", "마이크로파", "ldmos", "전력증폭기", "gan rf"),
        "negative_gate": ("패키지", "몰딩", "캡슐화", "디스플레이", "인쇄회로"),
        "process_family": "rf_device",
        "value_chain": ["device", "process"],
        "validation_status": "draft-20260508",
    },
    # ── 신규 고수익 전략 (2026-05-09 추가) ─────────────────────────────────
    # H01L21 기반 한국어 키워드 전략 — KIPRIS 히트율 검증된 패턴 활용
    "gate_dielectric_H01L21": {
        "name": "gate_dielectric_H01L21",
        "keyword": "반도체 게이트 절연막 산화막 형성",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("게이트 절연막", "게이트 산화막", "고유전율", "게이트 유전막", "게이트 스택", "반도체", "절연막", "산화막"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이", "유기 발광", "표시 장치", "태양전지"),
        "process_family": "gate_dielectric",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260509",
    },
    "sti_isolation_H01L21": {
        "name": "sti_isolation_H01L21",
        "keyword": "반도체 소자분리 트렌치 STI 필드산화막",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("소자 분리", "트렌치", "sti", "필드 산화막", "소자분리", "분리 공정", "반도체", "웨이퍼", "실리콘"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "isolation",
        "value_chain": ["process"],
        "validation_status": "new-20260509",
    },
    "spacer_junction_H01L21": {
        "name": "spacer_junction_H01L21",
        "keyword": "반도체 스페이서 소스 드레인 접합 형성",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("스페이서", "소스", "드레인", "접합 형성", "불순물 도핑", "ldd", "halo", "반도체", "웨이퍼"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "junction",
        "value_chain": ["process"],
        "validation_status": "new-20260509",
    },
    "memory_cell_capacitor_H01L21": {
        "name": "memory_cell_capacitor_H01L21",
        "keyword": "반도체 메모리 셀 커패시터 비트라인 워드라인",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("메모리 셀", "커패시터", "비트라인", "워드라인", "스토리지 노드", "셀 어레이", "반도체", "메모리"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "memory_cell",
        "value_chain": ["process", "device"],
        "validation_status": "new-20260509",
    },
    "trench_capacitor_H01L21": {
        "name": "trench_capacitor_H01L21",
        "keyword": "반도체 트렌치 커패시터 깊은 트렌치 메모리",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("트렌치 커패시터", "깊은 트렌치", "deep trench", "커패시터 구조", "유전체", "반도체", "트렌치"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "memory_cell",
        "value_chain": ["process", "device"],
        "validation_status": "new-20260509",
    },
    # ── 신규 exhausted 우회 전략 (2026-05-09 추가) ─────────────────────────
    # 기존 전략이 KIPRIS 30페이지 소진 후, 동일 IPC + 다른 검색어로 새 레코드 발굴
    "thin_film_depo_H01L21": {
        "name": "thin_film_depo_H01L21",
        "keyword": "박막 형성 반도체 웨이퍼",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("박막", "형성", "웨이퍼", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이", "태양전지", "유기 발광"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260509",
    },
    "hardmask_etch_H01L21": {
        "name": "hardmask_etch_H01L21",
        "keyword": "하드마스크 패터닝 식각 반도체",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("하드마스크", "패터닝", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "etch",
        "value_chain": ["process"],
        "validation_status": "new-20260509",
    },
    "polysilicon_gate_H01L21": {
        "name": "polysilicon_gate_H01L21",
        "keyword": "폴리실리콘 게이트 반도체 형성",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("폴리실리콘", "게이트", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "gate_dielectric",
        "value_chain": ["process"],
        "validation_status": "new-20260509",
    },
    "via_contact_hole_H01L21": {
        "name": "via_contact_hole_H01L21",
        "keyword": "비아 컨택 홀 반도체 금속",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("비아", "컨택", "홀", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이", "인쇄회로"),
        "process_family": "interconnect",
        "value_chain": ["process"],
        "validation_status": "new-20260509",
    },
    "diffusion_barrier_H01L21": {
        "name": "diffusion_barrier_H01L21",
        "keyword": "확산 방지막 배리어 반도체",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("확산 방지", "배리어", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "interconnect",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260509",
    },
    "passivation_H01L21": {
        "name": "passivation_H01L21",
        "keyword": "보호막 패시베이션 반도체 질화막",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("보호막", "패시베이션", "반도체"),
        "negative_gate": ("패키지", "몰딩", "캡슐화", "디스플레이", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260509",
    },
    "semiconductor_method_H01L21": {
        "name": "semiconductor_method_H01L21",
        "keyword": "반도체 소자 제조 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "소자", "제조"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260509",
    },
    "trench_etch_fill_H01L21": {
        "name": "trench_etch_fill_H01L21",
        "keyword": "트렌치 식각 매립 반도체",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("트렌치", "매립", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "etch",
        "value_chain": ["process"],
        "validation_status": "new-20260509",
    },
    "metal_cvd_H01L21": {
        "name": "metal_cvd_H01L21",
        "keyword": "금속막 CVD 스퍼터 반도체 배선",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("금속막", "스퍼터", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이", "태양전지"),
        "process_family": "metallization",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260509",
    },
    "nitride_oxide_H01L21": {
        "name": "nitride_oxide_H01L21",
        "keyword": "질화막 산화막 반도체 절연층",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("질화막", "절연층", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이", "태양전지", "유기 발광"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260509",
    },
    "tungsten_plug_H01L21": {
        "name": "tungsten_plug_H01L21",
        "keyword": "텅스텐 플러그 반도체 매립 콘택",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("텅스텐", "반도체"),
        "negative_gate": ("패키지", "몰딩", "본딩", "캡슐화", "디스플레이"),
        "process_family": "interconnect",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260509",
    },
    "chamber_plasma_C23C": {
        "name": "chamber_plasma_C23C",
        "keyword": "반응 가스 챔버 스퍼터링 박막",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("챔버", "박막", "반도체"),
        "negative_gate": ("디스플레이", "솔라", "연료전지", "촉매", "몰딩"),
        "process_family": "deposition",
        "value_chain": ["process", "equipment", "material"],
        "validation_status": "new-20260509",
    },
    "cvd_film_C23C": {
        "name": "cvd_film_C23C",
        "keyword": "CVD 박막 증착 반도체 기판",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("cvd", "증착", "반도체"),
        "negative_gate": ("디스플레이", "솔라", "연료전지", "몰딩", "코팅"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260509",
    },
    # ── 신규 광범위 H01L21 전략 (2026-05-09 2차 추가) ───────────────────────
    # semiconductor_method_H01L21 패턴을 따라 폭넓은 검색어로 새 결과셋 발굴
    "semiconductor_fabrication_H01L21": {
        "name": "semiconductor_fabrication_H01L21",
        "keyword": "반도체 제조 공정 웨이퍼",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "공정"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260509b",
    },
    "semiconductor_layer_H01L21": {
        "name": "semiconductor_layer_H01L21",
        "keyword": "반도체 층 형성 기판 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "기판"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260509b",
    },
    "semiconductor_pattern_H01L21": {
        "name": "semiconductor_pattern_H01L21",
        "keyword": "반도체 패턴 형성 식각 마스크",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "패턴"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "etch",
        "value_chain": ["process"],
        "validation_status": "new-20260509b",
    },
    "semiconductor_circuit_H01L21": {
        "name": "semiconductor_circuit_H01L21",
        "keyword": "집적회로 반도체 제조 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("집적회로", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260509b",
    },
    "semiconductor_film_H01L21": {
        "name": "semiconductor_film_H01L21",
        "keyword": "반도체 막 증착 형성 절연",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "절연"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260509b",
    },
    "semiconductor_oxide_layer_H01L21": {
        "name": "semiconductor_oxide_layer_H01L21",
        "keyword": "반도체 산화막 층 기판 제조",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "산화"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "oxidation",
        "value_chain": ["process"],
        "validation_status": "new-20260510a",
    },
    "semiconductor_nitride_layer_H01L21": {
        "name": "semiconductor_nitride_layer_H01L21",
        "keyword": "반도체 질화막 기판 층 제조",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "질화"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510a",
    },
    "semiconductor_metal_wire_H01L21": {
        "name": "semiconductor_metal_wire_H01L21",
        "keyword": "반도체 금속 배선 형성 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "금속"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "metallization",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510a",
    },
    "semiconductor_ion_doping_H01L21": {
        "name": "semiconductor_ion_doping_H01L21",
        "keyword": "반도체 이온 주입 도핑 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "이온"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "implant",
        "value_chain": ["process"],
        "validation_status": "new-20260510a",
    },
    "semiconductor_etch_layer_H01L21": {
        "name": "semiconductor_etch_layer_H01L21",
        "keyword": "반도체 식각 층 기판 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "식각"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "etch",
        "value_chain": ["process"],
        "validation_status": "new-20260510a",
    },
    "semiconductor_depo_layer_H01L21": {
        "name": "semiconductor_depo_layer_H01L21",
        "keyword": "반도체 증착 층 기판 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "증착"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510a",
    },
    "semiconductor_surface_H01L21": {
        "name": "semiconductor_surface_H01L21",
        "keyword": "반도체 표면 처리 기판 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "표면"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "clean",
        "value_chain": ["process"],
        "validation_status": "new-20260510a",
    },
    "semiconductor_structure_H01L21": {
        "name": "semiconductor_structure_H01L21",
        "keyword": "반도체 구조 형성 기판 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("반도체", "구조"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260510a",
    },
    "sputtering_C23C": {
        "name": "sputtering_C23C",
        "keyword": "스퍼터링 반도체 박막 증착 금속",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510b",
    },
    "ald_depo_C23C": {
        "name": "ald_depo_C23C",
        "keyword": "원자층 증착 ALD 반도체 박막",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("원자층", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510b",
    },
    "pvd_film_C23C": {
        "name": "pvd_film_C23C",
        "keyword": "물리 기상 증착 PVD 반도체 박막",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("기상", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510b",
    },
    "semiconductor_gate_H01L21": {
        "name": "semiconductor_gate_H01L21",
        "keyword": "게이트 반도체 기판 형성 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("게이트", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "gate",
        "value_chain": ["process"],
        "validation_status": "new-20260510b",
    },
    "semiconductor_electrode_H01L21": {
        "name": "semiconductor_electrode_H01L21",
        "keyword": "전극 반도체 기판 형성 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("전극", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "metallization",
        "value_chain": ["process"],
        "validation_status": "new-20260510b",
    },
    "semiconductor_wiring_H01L21": {
        "name": "semiconductor_wiring_H01L21",
        "keyword": "배선 반도체 기판 형성 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("배선", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "metallization",
        "value_chain": ["process"],
        "validation_status": "new-20260510b",
    },
    "semiconductor_memory_fab_H01L21": {
        "name": "semiconductor_memory_fab_H01L21",
        "keyword": "메모리 반도체 셀 형성 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("메모리", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510b",
    },
    "semiconductor_trench_H01L21": {
        "name": "semiconductor_trench_H01L21",
        "keyword": "트렌치 반도체 기판 형성 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("트렌치", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "etch",
        "value_chain": ["process"],
        "validation_status": "new-20260510b",
    },
    "semiconductor_photo_H01L21": {
        "name": "semiconductor_photo_H01L21",
        "keyword": "감광막 반도체 패턴 형성 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": ("감광막", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "lithography",
        "value_chain": ["process"],
        "validation_status": "new-20260510b",
    },
    "nogate_h01l21_a": {
        "name": "nogate_h01l21_a",
        "keyword": "반도체 소자 형성 방법 기판",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드", "LED", "OLED", "액정"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260510c",
    },
    "nogate_h01l21_b": {
        "name": "nogate_h01l21_b",
        "keyword": "반도체 제조 공정 웨이퍼 층",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드", "LED", "OLED", "액정"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260510c",
    },
    "nogate_h01l21_c": {
        "name": "nogate_h01l21_c",
        "keyword": "집적회로 반도체 소자 기판 제조",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드", "LED", "OLED", "액정"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260510c",
    },
    "nogate_h01l21_d": {
        "name": "nogate_h01l21_d",
        "keyword": "반도체 박막 절연 형성 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드", "LED", "OLED", "액정"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510c",
    },
    "nogate_h01l21_e": {
        "name": "nogate_h01l21_e",
        "keyword": "반도체 소자 패턴 식각 마스크",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드", "LED", "OLED", "액정"),
        "process_family": "etch",
        "value_chain": ["process"],
        "validation_status": "new-20260510c",
    },
    "nogate_h01l21_f": {
        "name": "nogate_h01l21_f",
        "keyword": "반도체 금속 배선 콘택 형성",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드", "LED", "OLED", "액정"),
        "process_family": "metallization",
        "value_chain": ["process"],
        "validation_status": "new-20260510c",
    },
    "nogate_h01l27_a": {
        "name": "nogate_h01l27_a",
        "keyword": "반도체 메모리 셀 집적회로 소자",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510c",
    },
    "nogate_c23c_a": {
        "name": "nogate_c23c_a",
        "keyword": "박막 증착 반도체 기판 형성",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510c",
    },
    "nogate_c23c_b": {
        "name": "nogate_c23c_b",
        "keyword": "반도체 금속 박막 증착 스퍼터",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510c",
    },
    "nogate_h01l27_b": {
        "name": "nogate_h01l27_b",
        "keyword": "반도체 집적회로 메모리 셀 소자",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510d",
    },
    "nogate_h01l27_c": {
        "name": "nogate_h01l27_c",
        "keyword": "반도체 회로 소자 기판 제조 방법",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260510d",
    },
    "nogate_h01l27_d": {
        "name": "nogate_h01l27_d",
        "keyword": "플래시 메모리 반도체 셀 구조",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510d",
    },
    "nogate_h01l27_e": {
        "name": "nogate_h01l27_e",
        "keyword": "DRAM 메모리 셀 반도체 소자",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510d",
    },
    "nogate_h01l27_f": {
        "name": "nogate_h01l27_f",
        "keyword": "반도체 소자 집적 회로 형성",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260510d",
    },
    "nogate_h01l29_a": {
        "name": "nogate_h01l29_a",
        "keyword": "반도체 트랜지스터 소자 형성 방법",
        "ipcNumber": "H01L29",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "device",
        "value_chain": ["process"],
        "validation_status": "new-20260510d",
    },
    "nogate_h01l29_b": {
        "name": "nogate_h01l29_b",
        "keyword": "MOS 트랜지스터 반도체 기판 형성",
        "ipcNumber": "H01L29",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "device",
        "value_chain": ["process"],
        "validation_status": "new-20260510d",
    },
    "nogate_h01l21_g": {
        "name": "nogate_h01l21_g",
        "keyword": "반도체 소자 형성 기판 공정",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260510d",
    },
    "nogate_h01l21_h": {
        "name": "nogate_h01l21_h",
        "keyword": "반도체 절연막 층 기판 형성",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510d",
    },
    "nogate_h01l27_g": {
        "name": "nogate_h01l27_g",
        "keyword": "반도체 트랜지스터 게이트 소자 형성",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "device",
        "value_chain": ["process"],
        "validation_status": "new-20260510e",
    },
    "nogate_h01l27_h": {
        "name": "nogate_h01l27_h",
        "keyword": "비휘발성 메모리 반도체 소자 형성",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510e",
    },
    "nogate_h01l27_i": {
        "name": "nogate_h01l27_i",
        "keyword": "반도체 캐패시터 셀 소자 형성",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510e",
    },
    "nogate_h01l27_j": {
        "name": "nogate_h01l27_j",
        "keyword": "반도체 셀 어레이 메모리 소자",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510e",
    },
    "nogate_h01l27_k": {
        "name": "nogate_h01l27_k",
        "keyword": "반도체 집적 회로 소자 제조",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "general",
        "value_chain": ["process"],
        "validation_status": "new-20260510e",
    },
    "nogate_h01l27_l": {
        "name": "nogate_h01l27_l",
        "keyword": "반도체 비트라인 워드라인 메모리 소자",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510e",
    },
    "nogate_h01l21_i": {
        "name": "nogate_h01l21_i",
        "keyword": "반도체 소자 게이트 산화막 형성",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드"),
        "process_family": "gate",
        "value_chain": ["process"],
        "validation_status": "new-20260510e",
    },
    "nogate_h01l21_j": {
        "name": "nogate_h01l21_j",
        "keyword": "반도체 비아 홀 금속 배선 형성",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드"),
        "process_family": "metallization",
        "value_chain": ["process"],
        "validation_status": "new-20260510e",
    },
    # --- Run 13: H01L27 DRAM/capacitor focus + C23C sputtering variants + H10B/G11C new IPC ---
    "nogate_h01l27_m": {
        "name": "nogate_h01l27_m",
        "keyword": "반도체 DRAM 셀 커패시터 형성",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510f",
    },
    "nogate_h01l27_n": {
        "name": "nogate_h01l27_n",
        "keyword": "반도체 스토리지 노드 커패시터 소자",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510f",
    },
    "nogate_h01l27_o": {
        "name": "nogate_h01l27_o",
        "keyword": "반도체 커패시터 유전막 소자 형성",
        "ipcNumber": "H01L27",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510f",
    },
    "nogate_h10b_a": {
        "name": "nogate_h10b_a",
        "keyword": "반도체 메모리 셀 소자 형성",
        "ipcNumber": "H10B",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510f",
    },
    "nogate_h10b_b": {
        "name": "nogate_h10b_b",
        "keyword": "반도체 커패시터 셀 소자 제조",
        "ipcNumber": "H10B",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510f",
    },
    "nogate_h10b_c": {
        "name": "nogate_h10b_c",
        "keyword": "반도체 DRAM 커패시터 셀 소자",
        "ipcNumber": "H10B",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510f",
    },
    "sputtering_b_C23C": {
        "name": "sputtering_b_C23C",
        "keyword": "스퍼터링 타겟 금속 박막 반도체",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510f",
    },
    "sputtering_c_C23C": {
        "name": "sputtering_c_C23C",
        "keyword": "마그네트론 스퍼터 반도체 금속 박막",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260510f",
    },
    "nogate_g11c_a": {
        "name": "nogate_g11c_a",
        "keyword": "반도체 메모리 셀 소자 제조",
        "ipcNumber": "G11C",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판"),
        "process_family": "memory",
        "value_chain": ["process"],
        "validation_status": "new-20260510f",
    },
    # --- Run 14: C23C sputtering variants + H01L21 nogate (pages 9-30 pattern) ---
    "sputtering_d_C23C": {
        "name": "sputtering_d_C23C",
        "keyword": "스퍼터 반도체 장벽 금속막 형성",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511a",
    },
    "sputtering_e_C23C": {
        "name": "sputtering_e_C23C",
        "keyword": "스퍼터 알루미늄 반도체 금속 배선",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511a",
    },
    "sputtering_f_C23C": {
        "name": "sputtering_f_C23C",
        "keyword": "스퍼터 타이타늄 질화막 반도체 소자",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511a",
    },
    "nogate_h01l21_k": {
        "name": "nogate_h01l21_k",
        "keyword": "반도체 소자 게이트 절연막 형성",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드"),
        "process_family": "gate",
        "value_chain": ["process"],
        "validation_status": "new-20260511a",
    },
    "nogate_h01l21_l": {
        "name": "nogate_h01l21_l",
        "keyword": "반도체 산화막 질화막 절연막 형성",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드"),
        "process_family": "deposition",
        "value_chain": ["process"],
        "validation_status": "new-20260511a",
    },
    "nogate_h01l21_m": {
        "name": "nogate_h01l21_m",
        "keyword": "반도체 소자 금속 배선 형성 방법",
        "ipcNumber": "H01L21",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로", "패키지 기판", "발광 다이오드"),
        "process_family": "metallization",
        "value_chain": ["process"],
        "validation_status": "new-20260511a",
    },
    # --- Run 15: More C23C sputtering variants (황금 패턴 계속) ---
    "sputtering_g_C23C": {
        "name": "sputtering_g_C23C",
        "keyword": "스퍼터 구리 배선 반도체 증착",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511b",
    },
    "sputtering_h_C23C": {
        "name": "sputtering_h_C23C",
        "keyword": "스퍼터 배리어 금속 반도체 박막",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511b",
    },
    "sputtering_i_C23C": {
        "name": "sputtering_i_C23C",
        "keyword": "스퍼터 산화물 도전막 반도체 형성",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511b",
    },
    "sputtering_j_C23C": {
        "name": "sputtering_j_C23C",
        "keyword": "스퍼터 텅스텐 금속 반도체 배선",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511b",
    },
    # --- Run 16: More C23C variants ---
    "nogate_c23c_c": {
        "name": "nogate_c23c_c",
        "keyword": "반도체 소자 금속 배선 스퍼터링",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511c",
    },
    "nogate_c23c_d": {
        "name": "nogate_c23c_d",
        "keyword": "반도체 집적회로 금속막 배선 형성",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": (),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511c",
    },
    "sputtering_k_C23C": {
        "name": "sputtering_k_C23C",
        "keyword": "스퍼터 반도체 전극 도전막 형성",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511c",
    },
    "sputtering_l_C23C": {
        "name": "sputtering_l_C23C",
        "keyword": "스퍼터 반도체 도전층 금속 배선",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511c",
    },
    "sputtering_m_C23C": {
        "name": "sputtering_m_C23C",
        "keyword": "스퍼터 반도체 확산방지막 금속층",
        "ipcNumber": "C23C",
        "validated_web_query": '',
        "keyword_gate": ("스퍼터", "반도체"),
        "negative_gate": ("디스플레이", "표시 장치", "유기 발광", "태양전지", "인쇄회로"),
        "process_family": "deposition",
        "value_chain": ["process", "material"],
        "validation_status": "new-20260511c",
    },
}

COLLECTION_PLANS: Dict[str, Dict[str, Any]] = {
    "etch_poc": {
        "scope": "semiconductor_etching_rejected_patents",
        "default_dataset": DEFAULT_DATASET,
        "year_min": 2015,
        "year_max": 2024,
        "stages": [
            {
                "name": "etch_core",
                "label": "Etch Core",
                "budget_share": 1.0,
                "strategies": ["plasma_H01J37", "wet_solution_kw", "profile_H01L21"],
            }
        ],
    },
    "semiconductor_commercial": {
        "scope": "semiconductor_fullstack_rejected_patents",
        "default_dataset": SEMICONDUCTOR_DATASET,
        "year_min": 2012,
        "year_max": 2025,
        "stages": [
            {
                "name": "etch_core",
                "label": "Etch Core",
                "budget_share": 0.25,
                # wet_solution_kw 추가 (기존 플랜에서 누락됐던 습식 식각 전략)
                "strategies": ["plasma_H01J37", "profile_H01L21", "wet_solution_kw"],
            },
            {
                "name": "adjacent_frontend",
                "label": "Adjacent Frontend",
                "budget_share": 0.25,
                "strategies": ["depo_ald_precursor", "photo_resist_pattern_H01L21", "photo_mask_align_H01L21"],
            },
            {
                "name": "frontend_broadening",
                "label": "Frontend Broadening",
                "budget_share": 0.25,
                "strategies": [
                    "clean_cmp_surface",
                    "cmp_postclean_H01L21",
                    "oxidation_diffusion_H01L21",
                    "implant_H01L21",
                    "metallization_C23C",
                ],
            },
            {
                "name": "backend_and_assets",
                "label": "Backend And Assets",
                "budget_share": 0.25,
                "strategies": [
                    "backend_rdl_interposer_H01L23",
                    "material_wafer_H01L21",
                    "material_compound_epi_H01L21",
                    "component_chamber_H01J37",
                    "component_esc_susceptor_H01J37",
                    "equipment_cluster_H01J37",
                    "equipment_vacuum_transfer_H01J37",
                ],
            },
        ],
    },
    # ── 반도체 온톨로지 구축용 전공정 확장 플랜 (2026-05-08 신설) ──────────────
    # 반도체 공정 전체(FEOL/MOL/BEOL/패키징/소재/부품/장비/설계) +
    # 메모리·로직·전력·MEMS·RF·이미지센서 등 소자 계열을 망라한다.
    # 연도 범위를 2008~2025로 넓혀 성숙 기술의 레거시 거절특허도 포함.
    # 각 stage의 budget_share 합계 = 1.0.
    "semiconductor_ontology": {
        "scope": "semiconductor_ontology_rejected_patents",
        "default_dataset": SEMICONDUCTOR_DATASET,
        "year_min": 2008,
        "year_max": 2025,
        "stages": [
            # ── FEOL 공정 ────────────────────────────────────────────────────
            {
                "name": "feol_etch",
                "label": "FEOL — Etch",
                "budget_share": 0.12,
                "strategies": ["plasma_H01J37", "profile_H01L21", "wet_solution_kw"],
            },
            {
                "name": "feol_depo",
                "label": "FEOL — Deposition & Epitaxy",
                "budget_share": 0.09,
                "strategies": [
                    "depo_ald_precursor",
                    "depo_plasma_C23C",
                    "epitaxy_sige_H01L21",
                    "material_compound_epi_H01L21",
                ],
            },
            {
                "name": "feol_photo",
                "label": "FEOL — Lithography",
                "budget_share": 0.10,
                "strategies": [
                    "photo_resist_pattern_H01L21",
                    "photo_mask_align_H01L21",
                    "photo_resist_G03F7",
                    "photo_euv_patterning",
                ],
            },
            {
                "name": "feol_thermal_implant",
                "label": "FEOL — Thermal & Implant",
                "budget_share": 0.08,
                "strategies": [
                    "oxidation_diffusion_H01L21",
                    "implant_H01L21",
                    "thermal_anneal_H01L21",
                ],
            },
            {
                "name": "feol_cmp_clean",
                "label": "FEOL — CMP & Clean",
                "budget_share": 0.06,
                "strategies": ["clean_cmp_surface", "cmp_postclean_H01L21"],
            },
            # ── 신규 FEOL 공정 (게이트/소자분리/접합) ────────────────────────
            {
                "name": "feol_gate_isolation",
                "label": "FEOL — Gate, Isolation & Junction",
                "budget_share": 0.08,
                "strategies": [
                    "gate_dielectric_H01L21",
                    "sti_isolation_H01L21",
                    "spacer_junction_H01L21",
                ],
            },
            # ── MOL / BEOL 배선 ──────────────────────────────────────────────
            {
                "name": "mol_beol_interconnect",
                "label": "MOL/BEOL — Interconnect",
                "budget_share": 0.08,
                "strategies": [
                    "metallization_C23C",
                    "interconnect_cu_lowk_H01L21",
                    "contact_silicide_H01L21",
                ],
            },
            # ── 소자 구조 ────────────────────────────────────────────────────
            {
                "name": "device_logic",
                "label": "Device — Logic (FinFET/GAA)",
                "budget_share": 0.08,
                "strategies": ["logic_finfet_gaa_H01L29"],
            },
            {
                "name": "device_memory",
                "label": "Device — Memory (DRAM/NAND)",
                "budget_share": 0.07,
                "strategies": ["memory_dram_cell_H01L27", "memory_nand_flash_H01L29", "memory_cell_capacitor_H01L21", "trench_capacitor_H01L21"],
            },
            {
                "name": "device_special",
                "label": "Device — Power / RF / Imager / MEMS",
                "budget_share": 0.08,
                "strategies": [
                    "power_device_igbt_H01L29",
                    "rf_device_H01L29",
                    "image_sensor_cmos_H01L27",
                    "mems_sensor_B81B",
                    "compound_semi_gaas_H01L21",
                ],
            },
            # ── 3D 통합 / 첨단 패키징 ────────────────────────────────────────
            {
                "name": "packaging_3d",
                "label": "3D Integration & Advanced Packaging",
                "budget_share": 0.08,
                "strategies": [
                    "tsv_wafer_bonding_H01L21",
                    "advanced_package_3d_H01L25",
                    "flip_chip_bump_H01L24",
                    "backend_rdl_interposer_H01L23",
                    "package_bond_B23K",
                ],
            },
            # ── 소재 / 부품 / 장비 / 검사 ────────────────────────────────────
            {
                "name": "materials_assets",
                "label": "Materials, Components & Equipment",
                "budget_share": 0.08,
                "strategies": [
                    "material_wafer_H01L21",
                    "material_precursor_chem_C07F",
                    "material_slurry_cmp_C09G",
                    "component_chamber_H01J37",
                    "component_esc_susceptor_H01J37",
                    "equipment_cluster_H01J37",
                    "equipment_vacuum_transfer_H01J37",
                ],
            },
            # ── 검사 / 계측 / EDA ────────────────────────────────────────────
            {
                "name": "metrology_eda",
                "label": "Inspection, Metrology & EDA",
                "budget_share": 0.06,
                "strategies": [
                    "inspection_metrology_G01N",
                    "design_drc_opc_G06F",
                ],
            },
            # ── 소진 우회: 새 H01L21 키워드 변형 ────────────────────────────
            {
                "name": "feol_new_keywords_a",
                "label": "FEOL — New Keyword Variants A",
                "budget_share": 0.12,
                "strategies": [
                    "thin_film_depo_H01L21",
                    "hardmask_etch_H01L21",
                    "polysilicon_gate_H01L21",
                    "via_contact_hole_H01L21",
                    "diffusion_barrier_H01L21",
                    "passivation_H01L21",
                ],
            },
            {
                "name": "feol_new_keywords_b",
                "label": "FEOL — New Keyword Variants B",
                "budget_share": 0.10,
                "strategies": [
                    "semiconductor_method_H01L21",
                    "trench_etch_fill_H01L21",
                    "metal_cvd_H01L21",
                    "nitride_oxide_H01L21",
                    "tungsten_plug_H01L21",
                    "chamber_plasma_C23C",
                    "cvd_film_C23C",
                ],
            },
            {
                "name": "feol_new_keywords_c",
                "label": "FEOL — New Keyword Variants C",
                "budget_share": 0.15,
                "strategies": [
                    "semiconductor_fabrication_H01L21",
                    "semiconductor_layer_H01L21",
                    "semiconductor_pattern_H01L21",
                    "semiconductor_circuit_H01L21",
                    "semiconductor_film_H01L21",
                ],
            },
            {
                "name": "feol_new_keywords_d",
                "label": "FEOL — New Keyword Variants D",
                "budget_share": 0.20,
                "strategies": [
                    "semiconductor_oxide_layer_H01L21",
                    "semiconductor_nitride_layer_H01L21",
                    "semiconductor_metal_wire_H01L21",
                    "semiconductor_ion_doping_H01L21",
                    "semiconductor_etch_layer_H01L21",
                    "semiconductor_depo_layer_H01L21",
                    "semiconductor_surface_H01L21",
                    "semiconductor_structure_H01L21",
                ],
            },
            {
                "name": "feol_new_keywords_e",
                "label": "FEOL — New Keyword Variants E",
                "budget_share": 0.20,
                "strategies": [
                    "sputtering_C23C",
                    "ald_depo_C23C",
                    "pvd_film_C23C",
                    "semiconductor_gate_H01L21",
                    "semiconductor_electrode_H01L21",
                    "semiconductor_wiring_H01L21",
                    "semiconductor_memory_fab_H01L21",
                    "semiconductor_trench_H01L21",
                    "semiconductor_photo_H01L21",
                ],
            },
            {
                "name": "feol_nogate_f",
                "label": "No-Gate — IPC-Only Strategies",
                "budget_share": 0.50,
                "strategies": [
                    "nogate_h01l21_a",
                    "nogate_h01l21_b",
                    "nogate_h01l21_c",
                    "nogate_h01l21_d",
                    "nogate_h01l21_e",
                    "nogate_h01l21_f",
                    "nogate_h01l27_a",
                    "nogate_c23c_a",
                    "nogate_c23c_b",
                ],
            },
            {
                "name": "feol_nogate_g",
                "label": "No-Gate — H01L27/H01L29 Variants",
                "budget_share": 0.50,
                "strategies": [
                    "nogate_h01l27_b",
                    "nogate_h01l27_c",
                    "nogate_h01l27_d",
                    "nogate_h01l27_e",
                    "nogate_h01l27_f",
                    "nogate_h01l29_a",
                    "nogate_h01l29_b",
                    "nogate_h01l21_g",
                    "nogate_h01l21_h",
                ],
            },
            {
                "name": "feol_nogate_h",
                "label": "No-Gate — H01L27 Extended + H01L21 New",
                "budget_share": 0.50,
                "strategies": [
                    "nogate_h01l27_g",
                    "nogate_h01l27_h",
                    "nogate_h01l27_i",
                    "nogate_h01l27_j",
                    "nogate_h01l27_k",
                    "nogate_h01l27_l",
                    "nogate_h01l21_i",
                    "nogate_h01l21_j",
                ],
            },
            {
                "name": "feol_nogate_i",
                "label": "No-Gate — H01L27 DRAM + H10B/G11C + C23C Sputtering",
                "budget_share": 0.50,
                "strategies": [
                    "nogate_h01l27_m",
                    "nogate_h01l27_n",
                    "nogate_h01l27_o",
                    "nogate_h10b_a",
                    "nogate_h10b_b",
                    "nogate_h10b_c",
                    "sputtering_b_C23C",
                    "sputtering_c_C23C",
                    "nogate_g11c_a",
                ],
            },
            {
                "name": "feol_nogate_j",
                "label": "No-Gate — C23C Sputtering Variants + H01L21 New",
                "budget_share": 0.50,
                "strategies": [
                    "sputtering_d_C23C",
                    "sputtering_e_C23C",
                    "sputtering_f_C23C",
                    "nogate_h01l21_k",
                    "nogate_h01l21_l",
                    "nogate_h01l21_m",
                ],
            },
            {
                "name": "feol_nogate_k",
                "label": "No-Gate — C23C Sputtering Final Push",
                "budget_share": 0.60,
                "strategies": [
                    "sputtering_g_C23C",
                    "sputtering_h_C23C",
                    "sputtering_i_C23C",
                    "sputtering_j_C23C",
                ],
            },
            {
                "name": "feol_nogate_l",
                "label": "No-Gate — C23C New Variants Run 16",
                "budget_share": 0.70,
                "strategies": [
                    "nogate_c23c_c",
                    "nogate_c23c_d",
                    "sputtering_k_C23C",
                    "sputtering_l_C23C",
                    "sputtering_m_C23C",
                ],
            },
        ],
    },
}


# ── 유틸 ────────────────────────────────────────────────────────────────────


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _str(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _to_list(v: Any) -> List[Dict[str, Any]]:
    if v is None:
        return []
    if isinstance(v, dict):
        return [v]
    if isinstance(v, list):
        return [i for i in v if isinstance(i, dict)]
    return []


def _extract_year(value: Any) -> Optional[int]:
    s = _str(value)
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) < 4:
        return None
    y = int(digits[:4])
    return y if 1900 <= y <= 2100 else None


def _has_strategy_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    s = (text or "").lower()
    return any(k.lower() in s for k in keywords)


def _hits_negative_gate(text: str, keywords: tuple[str, ...]) -> bool:
    s = (text or "").lower()
    return any(k.lower() in s for k in keywords)


def _collection_plan(name: str) -> Dict[str, Any]:
    plan = COLLECTION_PLANS.get(name)
    if not isinstance(plan, dict):
        raise KeyError(name)
    return plan


def _plan_stages(name: str) -> List[Dict[str, Any]]:
    plan = _collection_plan(name)
    stages = plan.get("stages") or []
    compiled: List[Dict[str, Any]] = []
    for stage in stages:
        stage_name = _str(stage.get("name"))
        if not stage_name:
            continue
        strategy_names = stage.get("strategies") or []
        strategies = [STRATEGY_LIBRARY[s] for s in strategy_names if s in STRATEGY_LIBRARY]
        if not strategies:
            continue
        compiled.append({
            "name": stage_name,
            "label": _str(stage.get("label")) or stage_name,
            "budget_share": float(stage.get("budget_share", 1.0)),
            "strategies": strategies,
        })
    return compiled


def _required_target_fields_ok(target: Dict[str, Any]) -> bool:
    required = [
        _str(target.get("application_number")),
        _str(target.get("title")),
        _str(target.get("abstract")),
        _str(target.get("claim1")),
        _str(target.get("ipc")),
        _str(target.get("date")),
    ]
    return all(bool(v) for v in required)


def _empty_strategy_stats() -> Dict[str, Any]:
    return {
        "pages": 0,
        "search_candidates": 0,
        "prefilter_passed": 0,
        "biblio_attempts": 0,
        "added": 0,
        "disabled": False,
        "disable_reason": "",
    }


def _strategy_yield(stats: Dict[str, Any]) -> float:
    attempts = int(stats.get("biblio_attempts", 0))
    if attempts <= 0:
        return 0.0
    return int(stats.get("added", 0)) / attempts


def _should_disable_strategy(
    stats: Dict[str, Any],
    *,
    min_biblio_attempts: int,
    min_strategy_yield: float,
) -> bool:
    if stats.get("disabled"):
        return False
    attempts = int(stats.get("biblio_attempts", 0))
    if attempts < max(1, min_biblio_attempts):
        return False
    return _strategy_yield(stats) < min_strategy_yield


def _should_disable_zero_prefilter_strategy(
    stats: Dict[str, Any],
    *,
    min_search_candidates: int,
) -> bool:
    if stats.get("disabled"):
        return False
    if int(stats.get("prefilter_passed", 0)) > 0:
        return False
    return int(stats.get("search_candidates", 0)) >= max(1, min_search_candidates)


def _stage_budget_limit(total_limit: int, budget_share: float) -> int:
    share = min(max(float(budget_share), 0.0), 1.0)
    if share <= 0.0:
        return 0
    return max(1, int(total_limit * share + 0.9999))


def _looks_rejected(status: str) -> bool:
    s = (status or "").lower()
    return any(k in s for k in REJECTED_PATTERNS)


def _is_non_rejected_explicit(status: str) -> bool:
    """검색 응답에서 거절이 아님이 명백한지 (등록/소멸/무효/취하/포기, 단 거절 키워드는 제외)."""
    s = (status or "")
    if not s.strip():
        return False
    s_low = s.lower()
    if any(k in s_low for k in REJECTED_PATTERNS):
        return False
    return any(k in s for k in NON_REJECTED_EXPLICIT)


def _load_seen(path: Path) -> Tuple[List[Dict[str, Any]], set]:
    rows: List[Dict[str, Any]] = []
    seen: set = set()
    if not path.exists():
        return rows, seen
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            rows.append(rec)
            app_no = (rec.get("target_patent") or {}).get("application_number")
            if app_no:
                seen.add(_str(app_no))
        except json.JSONDecodeError:
            continue
    return rows, seen


def _append_record(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 파일이 newline 없이 끝났을 수 있으므로 append 직전 정상화한다.
    if path.exists() and path.stat().st_size > 0:
        with path.open("rb") as fh:
            fh.seek(-1, 2)
            last = fh.read(1)
        if last != b"\n":
            with path.open("a", encoding="utf-8") as fh:
                fh.write("\n")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_progress(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "expand_progress/v1",
            "updated_at": _utc_now(),
            "strategies": {},
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "schema_version": "expand_progress/v1",
            "updated_at": _utc_now(),
            "strategies": {},
        }
    if not isinstance(data, dict):
        return {
            "schema_version": "expand_progress/v1",
            "updated_at": _utc_now(),
            "strategies": {},
        }
    data.setdefault("schema_version", "expand_progress/v1")
    data.setdefault("updated_at", _utc_now())
    data.setdefault("strategies", {})
    if not isinstance(data.get("strategies"), dict):
        data["strategies"] = {}
    return data


def _save_progress(path: Path, progress: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    progress["updated_at"] = _utc_now()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _strategy_state(progress: Dict[str, Any], strategy_name: str) -> Dict[str, int]:
    strategies = progress.setdefault("strategies", {})
    state = strategies.get(strategy_name)
    if not isinstance(state, dict):
        state = {}
    next_page = int(state.get("next_page", 1)) if str(state.get("next_page", "")).strip() else 1
    no_add_pages = (
        int(state.get("no_add_pages", 0)) if str(state.get("no_add_pages", "")).strip() else 0
    )
    norm = {
        "next_page": max(1, next_page),
        "no_add_pages": max(0, no_add_pages),
    }
    strategies[strategy_name] = norm
    return norm


def _guardrail_blocks_strategy(
    *,
    strategy_name: str,
    strategy_added: Counter,
    current_new_total: int,
    max_new_strategy_share: float,
    warmup_min_records: int,
) -> bool:
    """신규 추가분에서 단일 전략 점유율 상한을 초과하면 차단한다."""
    if max_new_strategy_share <= 0.0 or max_new_strategy_share >= 1.0:
        return False
    projected_total = current_new_total + 1
    if projected_total < max(1, warmup_min_records):
        return False
    projected_share = (strategy_added[strategy_name] + 1) / projected_total
    return projected_share > max_new_strategy_share


# ── API 호출 예산 트래커 ─────────────────────────────────────────────────────


class CallBudget:
    def __init__(self, limit: int) -> None:
        self.limit = max(0, int(limit))
        self.used = 0

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def consume(self, n: int = 1) -> None:
        self.used += n

    def can_call(self, n: int = 1) -> bool:
        return self.used + n <= self.limit


# ── 스키마 빌더 ─────────────────────────────────────────────────────────────


def _ipc_pipe_string(bib_item: Dict[str, Any]) -> str:
    arr = (bib_item.get("ipcInfoArray") or {})
    items = _to_list(arr.get("ipcInfo"))
    codes = [_str(i.get("ipcNumber")) for i in items if i.get("ipcNumber")]
    return "|".join(codes)


def _abstract_from_biblio(bib_item: Dict[str, Any]) -> str:
    arr = (bib_item.get("abstractInfoArray") or {})
    info = arr.get("abstractInfo")
    if isinstance(info, list):
        info = info[0] if info else {}
    if isinstance(info, dict):
        return _str(info.get("astrtCont"))
    return ""


def _claim1_from_biblio(bib_item: Dict[str, Any]) -> str:
    arr = (bib_item.get("claimInfoArray") or {})
    claims = _to_list(arr.get("claimInfo"))
    for c in claims:
        text = _str(c.get("claim") or c.get("claimText") or "")
        if text.startswith("1.") or text.startswith("1 "):
            return text[:2000]
    if claims:
        return _str(claims[0].get("claim") or claims[0].get("claimText") or "")[:2000]
    return ""


def _summary(bib_item: Dict[str, Any]) -> Dict[str, Any]:
    arr = (bib_item.get("biblioSummaryInfoArray") or {})
    info = arr.get("biblioSummaryInfo")
    if isinstance(info, list):
        info = info[0] if info else {}
    return info if isinstance(info, dict) else {}


def _examination_status(summary: Dict[str, Any]) -> str:
    """`거절결정(일반)` 같은 KIPO 행정상태 문자열을 최대한 추출."""
    for key in ("finalDisposal", "examinationStatus", "examinationDocStatus"):
        v = _str(summary.get(key))
        if v:
            return v
    rs = _str(summary.get("registerStatus"))
    return f"{rs}(API)" if rs else ""


def _prior_arts(bib_item: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    p_array = (
        bib_item.get("priorArtDocumentsInfoArray")
        or bib_item.get("priorArtDocumentInfoArray")
        or bib_item.get("priorArtDocumentsArray")
        or bib_item.get("priorArtDocumentArray")
        or {}
    )
    docs = _to_list(
        p_array.get("priorArtDocumentsInfo")
        or p_array.get("priorArtDocumentInfo")
        or p_array.get("priorArtDocuments")
        or p_array.get("priorArtDocument")
    )
    examiner: List[str] = []
    all_ids: List[str] = []
    for c in docs:
        cited = _str(
            c.get("documentsNumber")
            or c.get("documentNumber")
            or c.get("docNumber")
            or ""
        )
        if not cited:
            continue
        all_ids.append(cited)
        flag = _str(
            c.get("examinerQuotationFlag")
            or c.get("examinerQuotationYn")
            or c.get("examinerQuotationYN")
        ).upper()
        if flag == "Y":
            examiner.append(cited)
    return examiner, all_ids


def _build_record(
    *,
    search_item: Dict[str, Any],
    bib_item: Dict[str, Any],
    strategy: Dict[str, Any],
    collection_plan: str,
    collection_stage: str,
    cohort_scope: str,
    admin_documents: List[Dict[str, Any]],
    evidence_url: str,
    evidence_type: str,
) -> Optional[Dict[str, Any]]:
    app_no = _str(search_item.get("applicationNumber"))
    if not app_no:
        return None

    summary = _summary(bib_item)
    title = _str(search_item.get("inventionTitle") or summary.get("inventionTitle"))
    abstract = _str(search_item.get("astrtCont")) or _abstract_from_biblio(bib_item)
    ipc = _ipc_pipe_string(bib_item) or _str(search_item.get("ipcNumber"))
    claim1 = _claim1_from_biblio(bib_item)
    open_date = _str(search_item.get("openDate") or summary.get("openDate"))
    open_no = _str(search_item.get("openNumber") or summary.get("openNumber"))

    examiner, all_ids = _prior_arts(bib_item)
    if not examiner:
        return None

    register_status = _str(summary.get("registerStatus") or search_item.get("registerStatus"))
    if not _looks_rejected(register_status):
        return None
    examination_status = _examination_status(summary) or "거절결정(API)"

    target_patent = {
        "application_number": app_no,
        "title": title,
        "abstract": abstract,
        "ipc": ipc,
        "date": open_date,
        "claim1": claim1,
        "registration": {
            "register_status": "거절",
            "register_number": _str(summary.get("registerNumber")),
            "register_date": _str(summary.get("registerDate")),
        },
        "biblio": {
            "examination_status": examination_status,
            "unex_pub_number": open_no,
            "unex_pub_date": open_date,
            "source": "kipris_plus_api",
        },
    }
    if not _required_target_fields_ok(target_patent):
        return None

    return {
        "target_patent": target_patent,
        "ground_truth_examiner": examiner,
        "ground_truth_all": all_ids or examiner,
        "ground_truth_evidence": [],
        "meta": {
            "source": "kipris_plus_api",
            "collection_plan": collection_plan,
            "collection_stage": collection_stage,
            "search_strategy": strategy["name"],
            "search_query": strategy["keyword"],
            "validated_web_query": strategy.get("validated_web_query", ""),
            "cohort_scope": cohort_scope,
            "process_family": strategy.get("process_family", ""),
            "value_chain": strategy.get("value_chain", []),
            "strategy_validation_status": strategy.get("validation_status", ""),
            "collection_ts": _utc_now(),
            "evidence_document_type": evidence_type,
            "evidence_document_url": evidence_url,
            "admin_documents": admin_documents,
            "notes": "ground_truth_evidence is empty: KIPRIS Plus API does not expose OCR'd citation phrases.",
        },
    }


# ── 메인 수집 루프 ───────────────────────────────────────────────────────────


def search_page(
    client: KiprisClient,
    budget: CallBudget,
    *,
    keyword: Optional[str],
    ipc: Optional[str],
    page: int,
    rows: int,
) -> Tuple[int, List[Dict[str, Any]]]:
    if not budget.can_call():
        return 0, []
    params: Dict[str, Any] = {
        "pageNo": page,
        "numOfRows": rows,
        "sortSpec": "AD",
        "descSort": "true",
    }
    if keyword:
        # `word` 통합 검색: title + abstract + claim 모두 매칭. astrtCont보다 후보 풀이 훨씬 큼.
        params["word"] = keyword
    if ipc:
        params["ipcNumber"] = ipc
    try:
        budget.consume()
        resp = client.get("getAdvancedSearch", params)
    except KiprisQuotaExceeded:
        raise
    except Exception:
        return 0, []
    body = (resp.get("response", {}).get("body") or {})
    items = _to_list((body.get("items") or {}).get("item"))
    return len(items), items


def search_rejection_decision_page(
    client: Optional[RejectionDecisionClient],
    budget: CallBudget,
    *,
    keyword: Optional[str],
    page: int,
    rows: int,
) -> Tuple[int, List[Dict[str, Any]]]:
    if client is None or not keyword or not budget.can_call():
        return 0, []
    docs_start = ((max(1, page) - 1) * max(1, rows)) + 1
    try:
        budget.consume()
        items = client.search(
            word=keyword,
            patent=True,
            utility=False,
            docs_start=docs_start,
            docs_count=rows,
        )
    except KiprisQuotaExceeded:
        raise
    except Exception:
        return 0, []

    candidates: List[Dict[str, Any]] = []
    for item in items:
        candidates.append(
            {
                "applicationNumber": _str(item.get("applicationNumber")),
                "inventionTitle": _str(item.get("title") or item.get("inventionTitle")),
                "astrtCont": "",
                # REST seed의 sendDate는 거절 문서 발송일이라 연도 필터에 직접 쓰지 않는다.
                "openDate": "",
                "decisionSendDate": _str(item.get("sendDate")),
                "registerStatus": "거절",
                "evidenceDocumentType": "거절결정서",
                "evidenceDocumentUrl": _str(item.get("filePath")),
                "seedSource": "rejection_decision_rest",
            }
        )
    return len(candidates), candidates


def get_biblio(
    client: KiprisClient,
    budget: CallBudget,
    app_no: str,
) -> Optional[Dict[str, Any]]:
    if not budget.can_call():
        return None
    try:
        budget.consume()
        resp = client.get(
            "getBibliographyDetailInfoSearch",
            {"applicationNumber": app_no},
        )
    except KiprisQuotaExceeded:
        raise
    except Exception:
        return None
    body = (resp.get("response", {}).get("body") or {})
    item = body.get("item")
    if isinstance(item, list):
        return item[0] if item else None
    return item if isinstance(item, dict) else None


def _item_seed_admin_documents(item: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str, str]:
    evidence_url = _str(item.get("evidenceDocumentUrl"))
    evidence_type = _str(item.get("evidenceDocumentType")) or "거절결정서"
    if not evidence_url:
        return [], "", ""
    return [{"type": evidence_type, "url": evidence_url}], evidence_url, evidence_type


def _merge_admin_documents(*groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for group in groups:
        for item in group:
            doc_type = _str(item.get("type"))
            url = _str(item.get("url"))
            key = (doc_type, url)
            if not doc_type or not url or key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append({"type": doc_type, "url": url})
    return merged


def _item_year_with_biblio(search_item: Dict[str, Any], bib_item: Dict[str, Any]) -> Optional[int]:
    summary = _summary(bib_item)
    return _extract_year(
        search_item.get("openDate")
        or search_item.get("applicationDate")
        or summary.get("openDate")
        or summary.get("applicationDate")
        or summary.get("registerDate")
    )


def collect_admin_documents(
    rej_client: Optional[RejectionDecisionClient],
    budget: CallBudget,
    app_no: str,
) -> Tuple[List[Dict[str, Any]], str, str]:
    """confirmed 후보의 거절결정서 PDF URL 추출. 옵션."""
    if rej_client is None or not budget.can_call():
        return [], "", ""
    try:
        budget.consume()
        items = rej_client.search(application_number=app_no, docs_count=10)
    except KiprisQuotaExceeded:
        raise
    except Exception:
        return [], "", ""
    if not items:
        return [], "", ""
    docs: List[Dict[str, Any]] = []
    primary_url = ""
    for it in items:
        url = _str(it.get("filePath") or it.get("path") or "")
        if not url:
            continue
        docs.append({"type": "거절결정서", "url": url})
        if not primary_url:
            primary_url = url
    return docs, primary_url, ("거절결정서" if docs else "")


def main() -> None:
    ap = argparse.ArgumentParser(description="KIPRIS Plus API로 메인 데이터셋을 N건까지 확장")
    ap.add_argument("--collection-plan", choices=sorted(COLLECTION_PLANS.keys()), default="etch_poc",
                    help="단계적 수집 플랜. etch_poc=식각 PoC, semiconductor_commercial=반도체 전공정/MPE 확장")
    ap.add_argument(
        "--seed-source",
        choices=["search", "rejection-decision"],
        default="search",
        help="후보 생성 소스. search=공개공보 검색, rejection-decision=거절결정서 REST keyword seed",
    )
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--target", type=int, default=DEFAULT_TARGET,
                    help=f"최종 데이터셋 크기 (기본 {DEFAULT_TARGET})")
    ap.add_argument(
        "--profile",
        choices=sorted(PROFILE_PRESETS.keys()),
        default=DEFAULT_PROFILE,
        help=(
            "호출 예산 프로필. free=보수적(150 calls, 0.6s), "
            "paid=확장형(600 calls, 0.4s)"
        ),
    )
    ap.add_argument(
        "--max-api-calls",
        type=int,
        default=None,
        help=(
            "이번 실행에서 허용할 API 호출 상한. 미지정 시 --profile 기본값 사용 "
            f"(free={PROFILE_PRESETS['free']['max_api_calls']}, "
            f"paid={PROFILE_PRESETS['paid']['max_api_calls']})"
        ),
    )
    ap.add_argument(
        "--interval",
        type=float,
        default=None,
        help=(
            "호출 간격(초). 미지정 시 --profile 기본값 사용 "
            f"(free={PROFILE_PRESETS['free']['interval']}, "
            f"paid={PROFILE_PRESETS['paid']['interval']})"
        ),
    )
    ap.add_argument("--rows-per-page", type=int, default=DEFAULT_ROWS)
    ap.add_argument("--max-pages-per-strategy", type=int, default=DEFAULT_MAX_PAGES)
    ap.add_argument("--max-candidates-per-page", type=int, default=DEFAULT_MAX_CANDIDATES_PER_PAGE,
                    help=f"페이지당 biblio detail 호출 상한 (기본 {DEFAULT_MAX_CANDIDATES_PER_PAGE})")
    ap.add_argument("--year-min", type=int, default=None)
    ap.add_argument("--year-max", type=int, default=None)
    ap.add_argument(
        "--progress-file",
        type=Path,
        default=DEFAULT_PROGRESS_FILE,
        help="전략별 마지막 페이지/무수확 streak 체크포인트 파일",
    )
    ap.add_argument(
        "--reset-progress",
        action="store_true",
        help="--progress-file 내용을 지우고 1페이지부터 재탐색",
    )
    ap.add_argument(
        "--max-no-add-pages-per-strategy",
        type=int,
        default=DEFAULT_MAX_NO_ADD_PAGES_PER_STRATEGY,
        help=(
            "전략별 연속 무수확 페이지 허용치. 초과 시 해당 전략을 조기 종료 "
            f"(기본 {DEFAULT_MAX_NO_ADD_PAGES_PER_STRATEGY})"
        ),
    )
    ap.add_argument(
        "--max-new-strategy-share",
        type=float,
        default=DEFAULT_MAX_NEW_STRATEGY_SHARE,
        help=(
            "신규 추가분(new_records)에서 단일 전략이 차지할 최대 비중. "
            "0<share<1 일 때만 활성화 (기본 0.55)."
        ),
    )
    ap.add_argument(
        "--guardrail-warmup",
        type=int,
        default=DEFAULT_GUARDRAIL_WARMUP,
        help="가드레일을 적용하기 시작할 신규 레코드 수 (기본 20)",
    )
    ap.add_argument(
        "--min-biblio-attempts-before-disable",
        type=int,
        default=DEFAULT_MIN_BIBLIO_ATTEMPTS_BEFORE_DISABLE,
        help="전략 자동 비활성화를 판단하기 전 최소 biblio 시도 수",
    )
    ap.add_argument(
        "--min-strategy-yield",
        type=float,
        default=DEFAULT_MIN_STRATEGY_YIELD,
        help="added / biblio_attempts 수율이 이 값 미만이면 전략을 비활성화",
    )
    ap.add_argument(
        "--min-search-candidates-before-disable",
        type=int,
        default=DEFAULT_MIN_SEARCH_CANDIDATES_BEFORE_DISABLE,
        help="prefilter 통과 0건 전략을 비활성화하기 전 최소 검색 후보 수",
    )
    ap.add_argument(
        "--keep-low-yield-strategies",
        action="store_true",
        help="수율이 낮아도 전략 자동 비활성화를 하지 않음",
    )
    ap.add_argument("--collect-admin-docs", action="store_true",
                    help="confirmed 후보에 거절결정서 REST 1회 호출 (각 후보 당 +1 call)")
    ap.add_argument("--dry-run", action="store_true",
                    help="JSONL append 없이 후보 흐름만 시뮬레이션")
    args = ap.parse_args()

    preset = PROFILE_PRESETS[args.profile]
    plan = _collection_plan(args.collection_plan)
    if args.max_api_calls is None:
        args.max_api_calls = int(preset["max_api_calls"])
    if args.interval is None:
        args.interval = float(preset["interval"])
    if args.dataset == DEFAULT_DATASET and args.collection_plan != "etch_poc":
        args.dataset = Path(plan["default_dataset"])
    if args.year_min is None:
        args.year_min = int(plan.get("year_min", DEFAULT_YEAR_MIN))
    if args.year_max is None:
        args.year_max = int(plan.get("year_max", DEFAULT_YEAR_MAX))

    if not (0.0 < args.max_new_strategy_share <= 1.0):
        raise SystemExit("--max-new-strategy-share must satisfy 0 < share <= 1")
    if args.guardrail_warmup < 1:
        raise SystemExit("--guardrail-warmup must be >= 1")
    if args.min_biblio_attempts_before_disable < 1:
        raise SystemExit("--min-biblio-attempts-before-disable must be >= 1")
    if args.min_search_candidates_before_disable < 1:
        raise SystemExit("--min-search-candidates-before-disable must be >= 1")
    if not (0.0 <= args.min_strategy_yield <= 1.0):
        raise SystemExit("--min-strategy-yield must satisfy 0 <= yield <= 1")
    if args.max_no_add_pages_per_strategy < 1:
        raise SystemExit("--max-no-add-pages-per-strategy must be >= 1")
    if args.interval <= 0:
        raise SystemExit("--interval must be > 0")
    if args.max_api_calls < 1:
        raise SystemExit("--max-api-calls must be >= 1")

    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(REPO_ROOT / "env")
    api_key = os.getenv("KIPRIS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("KIPRIS_API_KEY not set in environment")

    client = KiprisClient(api_key, min_request_interval=args.interval)
    rej_client: Optional[RejectionDecisionClient] = None
    if args.collect_admin_docs or args.seed_source == "rejection-decision":
        rej_key = os.getenv("KIPRIS_REJECTION_DECISION_API_KEY", "").strip() or api_key
        rej_base = os.getenv("KIPRIS_REJECTION_DECISION_BASE_URL", REJ_BASE_URL).strip() or REJ_BASE_URL
        rej_client = RejectionDecisionClient(
            rej_key, base_url=rej_base, min_request_interval=args.interval
        )

    existing, seen = _load_seen(args.dataset)
    needed = max(0, args.target - len(existing))
    print(
        f"[config] plan={args.collection_plan} seed={args.seed_source} profile={args.profile} "
        f"interval={args.interval}s max_api_calls={args.max_api_calls} years={args.year_min}-{args.year_max}"
    )
    print(f"[init] existing={len(existing)} target={args.target} needed={needed}")
    if needed == 0:
        print("[done] target already met")
        return

    progress: Dict[str, Any] = {
        "schema_version": "expand_progress/v1",
        "updated_at": _utc_now(),
        "strategies": {},
    }
    if not args.dry_run:
        if args.reset_progress and args.progress_file.exists():
            args.progress_file.unlink()
            print(f"[progress] reset: {args.progress_file}")
        progress = _load_progress(args.progress_file)
        print(f"[progress] using: {args.progress_file}")

    budget = CallBudget(args.max_api_calls)
    new_records: List[Dict[str, Any]] = []
    strategy_added = Counter()
    guardrail_skips = 0
    early_stops = 0
    stages = _plan_stages(args.collection_plan)
    strategy_stats: Dict[str, Dict[str, Any]] = {
        name: _empty_strategy_stats() for name in STRATEGY_LIBRARY
    }
    stage_report: Dict[str, Dict[str, Any]] = {}
    disabled_strategies = 0

    quota_hit = False
    try:
        for stage in stages:
            if len(new_records) >= needed or budget.remaining == 0:
                break
            stage_budget_limit = min(budget.remaining, _stage_budget_limit(args.max_api_calls, stage["budget_share"]))
            stage_budget_start = budget.used
            stage_report[stage["name"]] = {
                "label": stage["label"],
                "budget_limit": stage_budget_limit,
                "budget_used": 0,
                "added": 0,
            }
            print(f"\n[stage] {stage['label']} ({stage['name']}) budget_cap={stage_budget_limit}")
            for strat in stage["strategies"]:
                if len(new_records) >= needed or budget.remaining == 0:
                    break
                stage_budget_used = budget.used - stage_budget_start
                if stage_budget_used >= stage_budget_limit:
                    print(
                        f"  [stage-cap] {stage['name']}: used={stage_budget_used}/{stage_budget_limit}, moving on"
                    )
                    break
                strat_name = strat["name"]
                stats = strategy_stats.setdefault(strat_name, _empty_strategy_stats())
                state = _strategy_state(progress, strat_name)
                start_page = state["next_page"]
                if start_page > args.max_pages_per_strategy:
                    start_page = 1
                    state["next_page"] = 1
                no_add_streak = state["no_add_pages"]
                print(
                    f"\n[strategy] {strat_name} (remaining budget={budget.remaining}, "
                    f"start_page={start_page}, no_add_streak={no_add_streak})"
                )

                for page in range(start_page, args.max_pages_per_strategy + 1):
                    if len(new_records) >= needed or budget.remaining == 0:
                        break
                    stage_budget_used = budget.used - stage_budget_start
                    if stage_budget_used >= stage_budget_limit:
                        print(
                            f"  [stage-cap] {stage['name']}: used={stage_budget_used}/{stage_budget_limit}, stop current stage"
                        )
                        break
                    if not budget.can_call():
                        break

                    if args.seed_source == "rejection-decision":
                        n_items, items = search_rejection_decision_page(
                            rej_client,
                            budget,
                            keyword=strat["keyword"],
                            page=page,
                            rows=args.rows_per_page,
                        )
                    else:
                        n_items, items = search_page(
                            client, budget,
                            keyword=strat["keyword"], ipc=strat["ipcNumber"],
                            page=page, rows=args.rows_per_page,
                        )
                    stats["pages"] += 1
                    stats["search_candidates"] += n_items
                    print(f"  page={page} candidates={n_items} budget_left={budget.remaining}")
                    page_added = 0
                    if n_items == 0:
                        state["next_page"] = 1
                        state["no_add_pages"] = min(no_add_streak + 1, args.max_no_add_pages_per_strategy)
                        if not args.dry_run:
                            _save_progress(args.progress_file, progress)
                        break

                    pre_passed: List[Dict[str, Any]] = []
                    page_seen: set[str] = set()
                    for it in items:
                        app_no = _str(it.get("applicationNumber"))
                        if not app_no or app_no in seen or app_no in page_seen:
                            continue
                        rs = _str(it.get("registerStatus"))
                        if _is_non_rejected_explicit(rs):
                            continue
                        y = _extract_year(it.get("openDate") or it.get("applicationDate"))
                        if y is not None and not (args.year_min <= y <= args.year_max):
                            continue
                        text_gate = tuple(strat.get("keyword_gate") or ())
                        negative_gate = tuple(strat.get("negative_gate") or ())
                        text_blob = " ".join([
                            _str(it.get("inventionTitle")),
                            _str(it.get("astrtCont")),
                        ])
                        if (
                            args.seed_source != "rejection-decision"
                            and text_gate
                            and text_blob
                            and not _has_strategy_keyword(text_blob, text_gate)
                        ):
                            continue
                        if negative_gate and text_blob and _hits_negative_gate(text_blob, negative_gate):
                            continue
                        pre_passed.append(it)
                        page_seen.add(app_no)
                        if len(pre_passed) >= args.max_candidates_per_page:
                            break
                    stats["prefilter_passed"] += len(pre_passed)

                    if not pre_passed:
                        no_add_streak += 1
                        state["next_page"] = page + 1 if page < args.max_pages_per_strategy else 1
                        state["no_add_pages"] = no_add_streak
                        if not args.dry_run:
                            _save_progress(args.progress_file, progress)
                        if not args.keep_low_yield_strategies and _should_disable_zero_prefilter_strategy(
                            stats,
                            min_search_candidates=args.min_search_candidates_before_disable,
                        ):
                            stats["disabled"] = True
                            stats["disable_reason"] = (
                                f"prefilter=0 after search_candidates={stats['search_candidates']}"
                            )
                            disabled_strategies += 1
                            print(f"  [disable] {strat_name}: {stats['disable_reason']}")
                            break
                        if no_add_streak >= args.max_no_add_pages_per_strategy:
                            early_stops += 1
                            print(
                                f"  [early-stop] {strat_name}: no-add streak {no_add_streak} "
                                f">= {args.max_no_add_pages_per_strategy}"
                            )
                            break
                        if n_items < args.rows_per_page:
                            state["next_page"] = 1
                            if not args.dry_run:
                                _save_progress(args.progress_file, progress)
                            break
                        continue

                    for it in pre_passed:
                        if len(new_records) >= needed or not budget.can_call():
                            break
                        stage_budget_used = budget.used - stage_budget_start
                        if stage_budget_used >= stage_budget_limit:
                            break
                        app_no = _str(it.get("applicationNumber"))
                        stats["biblio_attempts"] += 1
                        bib = get_biblio(client, budget, app_no)
                        if bib is None:
                            continue
                        record_year = _item_year_with_biblio(it, bib)
                        if record_year is not None and not (args.year_min <= record_year <= args.year_max):
                            continue
                        seed_admin_docs, seed_primary_url, seed_primary_type = _item_seed_admin_documents(it)
                        extra_admin_docs: List[Dict[str, Any]] = []
                        primary_url = seed_primary_url
                        primary_type = seed_primary_type
                        if args.collect_admin_docs and budget.remaining > 0:
                            extra_admin_docs, extra_primary_url, extra_primary_type = collect_admin_documents(
                                rej_client, budget, app_no
                            )
                            if not primary_url:
                                primary_url = extra_primary_url
                                primary_type = extra_primary_type
                        admin_docs = _merge_admin_documents(seed_admin_docs, extra_admin_docs)
                        rec = _build_record(
                            search_item=it,
                            bib_item=bib,
                            strategy=strat,
                            collection_plan=args.collection_plan,
                            collection_stage=stage["name"],
                            cohort_scope=_str(plan["scope"]),
                            admin_documents=admin_docs,
                            evidence_url=primary_url,
                            evidence_type=primary_type,
                        )
                        if rec is None:
                            continue
                        if _guardrail_blocks_strategy(
                            strategy_name=strat["name"],
                            strategy_added=strategy_added,
                            current_new_total=len(new_records),
                            max_new_strategy_share=args.max_new_strategy_share,
                            warmup_min_records=args.guardrail_warmup,
                        ):
                            guardrail_skips += 1
                            continue
                        seen.add(app_no)
                        new_records.append(rec)
                        strategy_added[strat["name"]] += 1
                        stats["added"] += 1
                        page_added += 1
                        stage_report[stage["name"]]["added"] += 1
                        if not args.dry_run:
                            _append_record(args.dataset, rec)
                        print(
                            f"    + {app_no}  GT={len(rec['ground_truth_examiner'])}  "
                            f"({len(new_records)}/{needed})  budget_left={budget.remaining}"
                        )

                    if page_added > 0:
                        no_add_streak = 0
                    else:
                        no_add_streak += 1
                    state["no_add_pages"] = no_add_streak
                    state["next_page"] = page + 1 if page < args.max_pages_per_strategy else 1
                    if not args.dry_run:
                        _save_progress(args.progress_file, progress)

                    if no_add_streak >= args.max_no_add_pages_per_strategy:
                        early_stops += 1
                        print(
                            f"  [early-stop] {strat_name}: no-add streak {no_add_streak} "
                            f">= {args.max_no_add_pages_per_strategy}"
                        )
                        break

                    if not args.keep_low_yield_strategies and _should_disable_strategy(
                        stats,
                        min_biblio_attempts=args.min_biblio_attempts_before_disable,
                        min_strategy_yield=args.min_strategy_yield,
                    ):
                        stats["disabled"] = True
                        stats["disable_reason"] = (
                            f"yield={_strategy_yield(stats):.3f} < {args.min_strategy_yield:.3f}"
                        )
                        disabled_strategies += 1
                        print(
                            f"  [disable] {strat_name}: {stats['disable_reason']} "
                            f"after biblio_attempts={stats['biblio_attempts']}"
                        )
                        break

                    if n_items < args.rows_per_page:
                        state["next_page"] = 1
                        if not args.dry_run:
                            _save_progress(args.progress_file, progress)
                        break
                stage_report[stage["name"]]["budget_used"] = budget.used - stage_budget_start
    except KiprisQuotaExceeded as exc:
        quota_hit = True
        print(f"\n[중단] KIPRIS quota: {exc}")
    except KiprisServiceKeyError as exc:
        print(f"\n[중단] KIPRIS auth: {exc}")
        raise SystemExit(2)

    print("\n" + "=" * 56)
    print(f"  added new records: {len(new_records)}")
    print(f"  total api calls used: {budget.used}/{budget.limit}")
    print(f"  per-strategy added: {dict(strategy_added)}")
    print(
        "  strategy guardrail: "
        f"max_new_share={args.max_new_strategy_share}, warmup={args.guardrail_warmup}, "
        f"blocked={guardrail_skips}"
    )
    print(
        "  strategy early-stop: "
        f"max_no_add_pages={args.max_no_add_pages_per_strategy}, triggered={early_stops}"
    )
    print(
        "  low-yield disable: "
        f"min_biblio_attempts={args.min_biblio_attempts_before_disable}, "
        f"min_yield={args.min_strategy_yield:.3f}, disabled={disabled_strategies}, "
        f"enabled={not args.keep_low_yield_strategies}"
    )
    print("  stage report:")
    for stage_name, info in stage_report.items():
        print(
            f"    - {stage_name}: added={info['added']} "
            f"budget_used={info['budget_used']}/{info['budget_limit']}"
        )
    print("  strategy report:")
    for stage in stages:
        for strat in stage["strategies"]:
            name = strat["name"]
            info = strategy_stats[name]
            print(
                f"    - {name}: pages={info['pages']} candidates={info['search_candidates']} "
                f"prefilter={info['prefilter_passed']} biblio={info['biblio_attempts']} "
                f"added={info['added']} yield={_strategy_yield(info):.3f} "
                f"disabled={info['disabled']}"
            )
    print(f"  dataset size: {len(existing) + len(new_records)} / target {args.target}")
    if quota_hit:
        print("  note: stopped early due to quota")
    if args.dry_run:
        print("  note: dry-run, no JSONL append")
    print("=" * 56)


if __name__ == "__main__":
    main()
