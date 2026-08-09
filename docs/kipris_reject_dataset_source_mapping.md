# KIPRIS 데이터 소스 매핑 메모

## 목적

이 문서는 KIPRIS Plus 서비스 설명 페이지 중 현재 데이터셋 목적과 직접 연결되는 두 소스를 정리합니다.

1. `특허·실용 공개·등록공보`
2. `거절결정서`

확인한 서비스 페이지:

- `특허·실용 공개·등록공보`: `https://plus.kipris.or.kr/portal/popup/service/DBII_000000000000001/view.do#soap_ADI_0000000000015128`
- `거절결정서`: `https://plus.kipris.or.kr/portal/popup/service/DBII_000000000000243/view.do`

기준은 다음과 같습니다.

- 현재 PoC의 핵심인 `거절특허 + 심사관 인용문헌` 구조에 직접 기여하는가
- 학습 입력 필드와 정답/설명 필드를 얼마나 안정적으로 제공하는가
- REST 기반 소량 검증과 대량 수집 경로를 어떻게 나눌 것인가

## 현재 운영 상태

2026-05-16 기준 현재 기본 수집 경로는 아래 조합입니다.

- rejected-only 후보 seed: KIPRIS 거절결정서 REST
- 타겟 특허 상세와 심사관 인용문헌 GT: KIPRIS Plus API 공개·등록공보 상세
- 타겟 보강 (전체 청구항 + family + legal status): KIPRIS Plus biblio detail 의 `claimInfoArray`/`familyInfoArray`/`legalStatusInfoArray` (Phase A)
- 인용 외부특허 본문 (corpus 편입):
  - KR pub/grant: KIPRIS Plus biblio detail (1728/1740 성공)
  - JP/US pub/grant: Google Patents 페이지 스크래핑 (752+379 성공)
  - WO/CN: EPO OPS biblio (71+19 성공)
- 거절결정서 본문: KIPRIS Plus `fileToss.jsp` PDF 다운로드 + pdfplumber/PyMuPDF 텍스트 추출 + tesseract OCR 폴백 (430 success)
- patent family 폴백: EPO OPS INPADOC (KIPRIS family 비어 있을 때만)
- 외부 device 어휘: Wikidata SPARQL (31 device classes)
- legacy 근거 문장과 raw archive: KIPRIS 웹 상세보기 + 의견제출통지서 OCR 경로 (POC 11건)

즉, 이 문서는 canonical semiconductor dataset 기준 서비스 수준 매핑 문서이며, legacy web+OCR 경로는 provenance 보강용으로 해석합니다.

## 1. 특허·실용 공개·등록공보

### 서비스 설명에서 확인한 내용

- 분류: `국내 IP데이터 > 공보 > 특허·실용`
- 업데이트 주기: `일 단위`
- REST 기능:
  - 검색: 일반검색, 항목별검색
  - 서지정보: 출원번호, 등록일자, 발명의 명칭, 등록상태 등
  - 도면/전문: 공개 및 공고 전문, 대표도 다운로드 경로

### 데이터셋 목적과의 연결

이 서비스는 현재 PoC의 기본 입력 레코드를 만드는 데 바로 사용할 수 있습니다.

#### A. 후보 특허 탐색

- `getAdvancedSearch`
- 현재 수집 스크립트와 노트북에서 쓰는 시작점
- 활용 목적:
  - 식각 분야 키워드 + IPC 조합으로 후보 특허를 찾기
  - `applicationNumber`, `registerStatus`, `inventionTitle`, `ipcNumber`, `openDate`, `astrtCont`를 빠르게 확보하기

#### B. 타겟 특허 상세 확정

- `getBibliographyDetailInfoSearch`
- 서비스 페이지의 서지정보 탭에서 확인 가능
- 요청 파라미터 핵심: `applicationNumber`
- 응답에서 데이터셋에 직접 쓰는 핵심 그룹:
  - `biblioSummaryInfoArray`
  - `ipcInfoArray`
  - `abstractInfoArray`
  - `claimInfoArray`
  - `priorArtDocumentsInfoArray`

#### C. 데이터셋 필드 매핑

- `target_patent.application_number` <- `applicationNumber`
- `target_patent.title` <- `inventionTitle`
- `target_patent.abstract` <- `astrtCont` 또는 `abstractInfoArray`
- `target_patent.ipc` <- `ipcInfoArray.ipcInfo[].ipcNumber`
- `target_patent.claim1` <- `claimInfoArray.claimInfo[]`
- `target_patent.registration.register_status` <- `biblioSummaryInfo.registerStatus`
- `target_patent.registration.register_number` <- `biblioSummaryInfo.registerNumber`
- `target_patent.registration.register_date` <- `biblioSummaryInfo.registerDate`
- `ground_truth_examiner` <- `priorArtDocumentsInfo[].documentsNumber` where `examinerQuotationFlag='Y'`
- `ground_truth_all` <- `priorArtDocumentsInfo[].documentsNumber`

### 현재 목적에서의 판단

이 서비스는 `현재 canonical dataset의 1차 핵심 소스`입니다.

이유는 다음과 같습니다.

- 거절특허 후보 탐색과 상세 검증을 모두 REST로 수행 가능
- claim 1, 서지 요약, IPC, 심사관 인용문헌을 한 흐름에서 연결 가능
- 현재 `scripts/collect_etching_dataset.py`가 이미 이 서비스의 `getAdvancedSearch`, `getBibliographyDetailInfoSearch`를 중심으로 동작함

다만 현재 실제 검증 결과는 다음과 같이 정리해야 합니다.

- API 문서상 필드 매핑은 유효하다.
- 현재 commercial collector는 이 서비스의 상세 응답을 직접 사용한다.
- legacy etch/web+OCR import는 별도 provenance로 유지한다.

### 한계

- 거절 이유 문구 자체를 충분히 설명형 텍스트로 주는 소스는 아님
- 인용문헌은 얻을 수 있지만, `왜 거절되었는가`의 서술적 근거는 제한적임

즉 이 서비스는 `타겟 특허 + 인용문헌 ground truth`를 만드는 핵심 소스이고, 거절 사유 설명 보강은 다른 소스가 필요합니다.

## 2. 거절결정서

### 서비스 설명에서 확인한 내용

- 분류: `국내 IP데이터 > 행정 > 공통`
- 업데이트 주기: `매일`
- REST 제공 내용:
  - 서지정보
  - 심사관정보
  - PDF 정보
- BULK 제공 내용:
  - 출원번호
  - 발송번호
  - 거절결정문구
  - 거절내용
  - 법적 근거
  - TXT, XML/PDF

### REST에서 확인한 핵심 포인트

- 오퍼레이션: `advancedSearchInfo`
- 요청 URL: `http://plus.kipris.or.kr/openapi/rest/IntermediateDocumentREService`
- 주요 검색 파라미터:
  - `applicationNumber`
  - `inventionTitle`
  - `rejectionContent`
  - `sendDate`
  - `sendNumber`
  - `relationpersonName`
  - `sortSpec`
- 주요 응답 필드:
  - `applicationNumber`
  - `sendNumber`
  - `sendDate`
  - `title`
  - `filePath`

### BULK에서 확인한 핵심 포인트

- 제공 기간: `2000~현재`
- 제공 방식: `TXT, XML/PDF`
- 데이터 세부사항: `출원번호, 발송번호, 거절결정문구, 거절내용, 법적 근거 등`
- 유료 상품 성격이 강함

### 데이터셋 목적과의 연결

거절결정서는 `현재 canonical collector의 핵심 보조 소스`로 보는 것이 적절합니다.

#### 바로 쓸 수 있는 가치

- rejected-only seed 후보를 먼저 형성해 공개검색 API 낭비를 줄일 수 있음
- `왜 거절되었는가`를 설명하는 텍스트 근거를 붙일 수 있음
- `신규성/진보성/법적 근거` 관련 설명형 라벨을 만들 가능성이 있음
- 심사관 인용문헌을 찾은 뒤, 그 문헌이 어떤 거절논리와 연결되는지 설명 학습에 유리함

#### 즉시 핵심 소스로 보기 어려운 이유

- REST만으로는 현재 확인한 범위에서 구조화 필드가 비교적 얕음
- 핵심 설명 필드인 `거절내용`, `법적 근거`는 BULK 설명에서 더 분명하게 제시됨
- BULK는 비용, 승인, 다운로드/파싱 절차를 추가로 요구함

### 권장 사용 방식

#### 1단계: 현재 운영 기본 경로

- 거절결정서 REST keyword 결과를 rejected-only seed로 사용
- 이후 `applicationNumber` 기준으로 공개공보 상세와 조인
- 가능한 경우 행정문서 URL도 같이 기록

#### 2단계: 설명형 확장

- 거절결정서 REST로 특정 출원번호의 발송번호, PDF 경로 존재 여부를 확인
- PDF 또는 BULK 텍스트에서 거절 사유 문구를 추출
- `rejection_reason_text`, `legal_basis`, `decision_document_path` 같은 보조 필드를 추가 검토

#### 3단계: 설명형 평가셋

- 현재 레코드 구조 위에 아래 필드를 보강
  - `rejection_reason_text`
  - `legal_basis`
  - `decision_send_date`
  - `decision_send_number`
- 목적:
  - 인용문헌 회수뿐 아니라, 왜 이 문헌이 거절 근거인지 설명하는 평가셋 구축

## 3. 외부 폴백 소스 (2026-05-16 신설)

### 3-1. Google Patents (JP/US/CN/WO)

- 엔드포인트: `https://patents.google.com/patent/<normalized_id>/en`
- 사용 목적: KIPRIS Plus 가 커버하지 않는 외국 공보의 title/abstract/pub_date 추출
- 호출 방식: HTML 스크래핑 (`<meta name="DC.title">`, `name="description">`, `name="DC.date">`)
- 호출 간격: 1.5초 (≈ 0.67 req/sec)
- 실측 성공률: JP 91.6% (752/821), US 80.0% (379/474), CN 95.0% (19/20)
- 한계: 본문 한국어 부재, claim1 미수집 (title/abstract 만)
- 구현: [scripts/enrich_unresolved.py](../scripts/enrich_unresolved.py) `resolve_google_patents`

### 3-2. EPO OPS (WO/CN/EP biblio + INPADOC family)

- 엔드포인트:
  - biblio: `https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc/<id>/biblio`
  - family: `https://ops.epo.org/3.2/rest-services/family/publication/docdb/<id>`
- 사용 목적:
  - WO/CN/EP 인용의 biblio + abstract (B1)
  - KR 출원의 INPADOC family 폴백 (B5)
- 인증: OAuth client_credentials (`EPO_OPS_KEY`, `EPO_OPS_SECRET`)
- 실측 성공률: WO 82.6% (71/86), EP 8.3% (1/12 — 데이터 커버리지 한계)
- 구현: [scripts/enrich_unresolved.py](../scripts/enrich_unresolved.py) `resolve_epo_ops`, [scripts/enrich_targets_b3_b5.py](../scripts/enrich_targets_b3_b5.py) `_epo_family`

### 3-3. Wikidata SPARQL (device class 어휘)

- 엔드포인트: `https://query.wikidata.org/sparql`
- 사용 목적: A2(소자/제품 계층 노드)와 B4(외부 어휘 소스)를 한 호출로 동시에 충족
- 호출 방식: SPARQL `SELECT ?item ?itemLabel ?itemLabelKo ?aliasEn ?aliasKo`
- 호출 간격: 1.2초 (Wikidata 권장 etiquette)
- 실측 결과: 31 device classes, en 79 / ko 37 alias 라벨
- 구현: [scripts/build_device_vocab.py](../scripts/build_device_vocab.py)

## 최종 권고

### 지금 바로 핵심에 넣을 것

- `특허·실용 공개·등록공보`
- 이유:
  - 현재 스크립트/노트북과 직접 연결 가능
  - `거절특허 + claim1 + examiner cited prior art`를 가장 안정적으로 생성 가능

### 2026-05-16 신설로 운영에 편입한 것

- 거절결정서 PDF OCR + 구조화 (`scripts/build_rejection_decisions.py`) — `ground_truth_evidence_v2` 656 매핑 확보
- Google Patents 폴백 — 외국 인용 in-corpus 비율 +20% 기여
- EPO OPS biblio + family — WO/CN/family 보강
- Wikidata SPARQL — device 계층 어휘 일회성 인입

### 지금은 보조/후속으로 둘 것

- BULK 기반 거절사유 본문 추출 (REST OCR 로 충분 — 441 records / 65.6% 의 URL 보유 모집단 기준)
- IEEE IRDS / JEDEC 정형 용어 인입 (Wikidata 만으로는 device alias 가 평균 3.7개/class — 후속 보강 필요)

## 코드 반영 원칙

현재 코드 기준으로는 다음 원칙을 유지합니다.

1. canonical dataset 기본 스키마는 `semiconductor_industry_rejected_patents.jsonl` 기준으로 유지
2. 타겟 특허와 인용문헌 ground truth는 `공개·등록공보` 계열 API 상세로 구축
3. `거절결정서` REST는 seed source와 admin document source로 함께 사용
4. OCR 기반 설명 확장은 legacy/raw 보존 경로와 분리해 추가

즉, 현재의 우선순위는 아래와 같습니다.

- 1순위: `거절특허 + examiner cited prior art`
- 2순위: `거절결정서 기반 설명 텍스트 보강`
