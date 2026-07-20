"""변조 이력에서 저장소 밖 원천 경로를 걷어낸다.

`upgrade_log.resume_matched` 는 EXP_001~005 가 실 경력기술서 파생임을 기록하는
정당한 프로비넌스다. 다만 `pdf` 필드는 **저장소 밖 비공개 작업 경로**를 담고 있어
누구도 그것으로 재현할 수 없고, 내부 디렉터리 구조만 배포물에 남긴다.

경로는 지우고 `text_sha256` 은 남긴다 — 파생 사실을 고정하는 앵커는 해시이지
파일 위치가 아니다. 원본은 이 저장소에 반입된 적이 없다.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = (ROOT / "data" / "experts" / "curated_profiles_kr.json",
         ROOT / "data" / "experts" / "curated_profiles_en.json")

SOURCE_DESC = ("de-identified derivative of a real practitioner career record "
               "(original document not ingested into this repository)")


SOURCE_NOTE = (
    "EXP_001~005 는 실 경력기술서를 근거로 식별 불가능하도록 변조한 파생 프로필이다. "
    "이름은 가명이고 수치(patent_count 등)는 생성값이며 실인물에 대한 주장이 아니다. "
    "원본 문서는 저장소·스냅샷·배포물 어디에도 반입되지 않았다. "
    "절차는 docs/deidentification_protocol.md."
)


def main() -> None:
    for path in PATHS:
        if not path.exists():
            continue
        doc = json.loads(path.read_text())
        log = doc.get("metadata", {}).get("upgrade_log", {})
        entries = log.get("resume_matched", [])

        removed = 0
        for entry in entries:
            if entry.pop("pdf", None) is not None:
                removed += 1
            entry["source"] = SOURCE_DESC
        if entries:
            log["source_note"] = SOURCE_NOTE

        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        print(f"{path.name}: 경로 제거 {removed}건 / resume_matched {len(entries)}건")


if __name__ == "__main__":
    main()
