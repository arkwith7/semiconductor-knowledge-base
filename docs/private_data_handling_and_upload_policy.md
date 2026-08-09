# Private 운영 및 업로드 금지 정책

이 문서는 `paper_data` 저장소를 **법적/라이선스 리스크가 커지지 않도록** 운영하기 위한 최소 정책을 정리합니다.

이 문서는 법률 자문이 아니라, 현재 저장소 구조와 산출물을 기준으로 한 **실무 운영 가이드**입니다.

## 1. 한 줄 결론

- 저장소는 **Private** 로 운영하는 것이 맞습니다.
- 하지만 **Private 만으로 충분하지는 않습니다**.
- 서버나 원격 저장소에는 **구조화 데이터만 올리고**, 원문 PDF/OCR/fulltext/비밀정보는 올리지 않는 것이 기본 원칙입니다.

## 2. 왜 Private 만으로 끝나지 않는가

Private 저장소는 공개 재배포 위험을 줄여 주지만, 아래 문제를 자동으로 해결해 주지는 않습니다.

- KIPRIS 또는 연계 소스의 이용약관/재배포 제한
- 원문 PDF, OCR 텍스트, near-fulltext 본문의 보관 범위 문제
- 내부 서버에 올린 뒤 다른 시스템으로 재복제되는 운영 리스크
- git history 에 원문성 파일이나 비밀정보가 남는 문제

따라서 실무 기준은 아래와 같습니다.

- `Private` 는 필요 조건
- `원문/비밀정보 분리` 는 필수 추가 조치

## 3. 서버에 올리지 말아야 하는 것

아래 항목은 **GitHub 원격 저장소, 배포 서버, 외부 공유 스토리지**에 올리지 않는 것을 기본 원칙으로 합니다.

### 3-1. 원문성 자산

- `data/processed/rejection_decisions/pdf/`
- `data/processed/rejection_decisions/txt/`
- `data/processed/fulltext/prior_arts/`
- `data/processed/fulltext/etching_prior_arts/`
- KIPRIS 또는 외부 소스에서 직접 내려받은 PDF, TXT, HTML, OCR 결과물 일체

이 경로들은 원문 PDF, OCR 텍스트, near-fulltext 본문을 담고 있으므로 가장 보수적으로 다뤄야 합니다.

### 3-2. 원문을 거의 복원할 수 있는 파생 산출물

- 대량 원문 span 이 들어 있는 JSON
- OCR 결과를 문단 단위로 길게 보관한 JSON
- 원문을 다시 조합할 수 있는 캐시/중간 산출물

### 3-3. 비밀정보

- `.env`
- `env`
- API key, session cookie, access token, 인증 헤더가 들어 있는 모든 파일
- 토큰이 섞인 로그 파일

## 4. 서버에 올려도 비교적 안전한 것

아래는 일반적으로 원문 재배포보다 리스크가 낮은 계층입니다. 다만 외부 공개 전에는 최종 재검토가 필요합니다.

- 출원번호, 공개번호, 등록번호 같은 식별자
- IPC/CPC, 법적상태, 이벤트 날짜, 패밀리 메타데이터
- `meta.evidence_document_url` 같은 참조 URL
- `ground_truth_evidence_v2` 같은 구조화 근거 매핑
- 짧은 설명형 라벨, 정규화된 코드, 요약형 통계
- 재수집 스크립트, 스키마 문서, 품질 리포트 생성 코드
- 외부 공개 라이선스 자산 (예: Wikidata SPARQL = CC0 인 `data/external/device_vocab/`)

현재 저장소에서 이 계층에 가까운 대표 자산은 아래와 같습니다.

- `docs/`
- `scripts/`
- `src/`
- `data/external/device_vocab/` (Wikidata 유래, CC0)

> **주의 — canonical JSONL 은 이 계층이 아니다.**
> `data/processed/semiconductor_industry_rejected_patents.jsonl` 은 `abstract`,
> `claim1`, `claims_full[].text` 같은 **KIPRIS 원문 텍스트**를 포함하므로
> 식별자/메타데이터 계층이 아니라 **원문성 자산(§3)** 으로 분류한다.
> 따라서 공개 저장소에 올리지 않으며 `.gitignore` 가 `data/processed/*` 로 제외한다.
> 품질 리포트(`dataset_quality_*`) 등 경량 산출물도 본문 span 이 섞이면 동일하게 제외한다.

## 5. 현재 저장소 기준으로 가장 조심할 경로

현재 구조에서 아래 경로는 **업로드 금지 우선순위가 가장 높습니다**.

- `data/processed/rejection_decisions/`
- `data/processed/fulltext/`

특히 아래 하위 경로는 원문성 자산으로 봐야 합니다.

- `data/processed/rejection_decisions/pdf/`
- `data/processed/rejection_decisions/txt/`
- `data/processed/fulltext/prior_arts/`
- `data/processed/fulltext/etching_prior_arts/`

## 6. 운영 권장안

가장 안전한 운영 방식은 저장소를 두 층으로 나누는 것입니다.

### 6-1. 코드/배포 저장소

여기에는 아래만 둡니다.

- 코드 (`scripts/`, `src/`)
- 문서 (`docs/`, `README.md`)
- 외부 공개 라이선스 자산 (`data/external/device_vocab/`, Wikidata/CC0)
- 본문 span 이 없는 경량 통계/스키마 산출물

> canonical JSONL(`semiconductor_industry_rejected_patents.jsonl`) 과
> 모든 `data/raw/`·`data/processed/` 산출물은 **이 저장소에 두지 않는다.**
> KIPRIS 원문(초록/청구항/거절결정서/인용 본문)을 포함하거나 재구성할 수 있기 때문이다.
> 공개 GitHub 저장소에는 **수집 코드와 스크립트만** 올린다.

### 6-2. 내부 비공개 원문 저장소 또는 스토리지

여기에는 아래를 둡니다.

- 원본 PDF
- OCR 텍스트
- fulltext corpus
- 대용량 캐시
- 수집 로그 원본

이 층은 접근 권한을 제한하고, 외부 공유나 배포 파이프라인에서 분리합니다.

## 7. 업로드 전 체크리스트

서버나 원격 저장소에 올리기 전에 아래만 확인해도 큰 실수를 줄일 수 있습니다.

1. `data/processed/rejection_decisions/` 가 포함되지 않았는지 확인
2. `data/processed/fulltext/` 가 포함되지 않았는지 확인
3. `data/processed/semiconductor_industry_rejected_patents.jsonl` (canonical) 이 포함되지 않았는지 확인
4. `.env`, `env`, API key 파일이 없는지 확인
5. 로그 파일에 URL token, cookie, session 값이 없는지 확인
6. 공개 대상 JSON 에 긴 원문 본문이 섞여 있지 않은지 확인
7. 원문이 필요하면 파일 자체 대신 `url`, `path`, `hash`, `doc_id` 만 남겼는지 확인
8. 노트북 출력 셀에 KIPRIS 응답 원문이나 (마스킹 안 된) API key 가 남아 있지 않은지 확인
   (`jupyter nbconvert --clear-output` 또는 커밋 전 출력 비우기)
9. `git ls-files data/` 결과가 `.gitkeep` 와 `data/external/device_vocab/` 외에 없는지 확인

## 8. 추천 판단 기준

어떤 파일을 서버에 올려도 되는지 헷갈리면 아래 기준으로 판단합니다.

- 원문을 그대로 담고 있으면 올리지 않음
- OCR 결과가 문서 재현 수준이면 올리지 않음
- 구조화 메타데이터와 짧은 근거 매핑이면 우선 허용 후보
- 비밀값이 포함되어 있으면 무조건 제외
- 애매하면 공개 저장소가 아니라 내부 보관층으로 보냄

## 9. 현재 저장소에서의 실무 결론

현재 `paper_data` 는 단순 구조화 데이터셋만 있는 상태가 아니라, 원문 PDF/OCR/fulltext 계층이 함께 있는 **내부 수집 저장소**에 가깝습니다.

따라서 안전한 운영 원칙은 아래 한 문장으로 정리됩니다.

- `paper_data` 는 **Private 로 유지**하고, 서버에는 **구조화 데이터만 올리며**, `rejection_decisions/`, `fulltext/`, `.env` 계열은 **올리지 않는다**.