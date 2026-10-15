"""미검색 213 쌍 층화 표본(언어 ko/en × 개념 공유 × IPC 공유 · 셀당 3 · 시드 20261012) 증거 시트.
공개 특허 텍스트(제목·초록·청구항 앞부분)와 b·d 가 쓴 검색 항만 담는다. 개발용 분석 — 가설 검증은 새 집합에서."""
import sys, json, re, random, collections
sys.path.insert(0, 'scripts')
import ir_corpus, kipris_emulator as K, report_t4_query as R
from splits import load_split

gt = R.load_gt('dev', load_split())
C = ir_corpus.load(['doc_id', 'is_candidate', 'lang', 'title', 'abstract', 'claims_full', 'claims_independent', 'first_claim_original', 'ipc', 'concepts'])
E = K.Emulator(C)
row = C.set_index('doc_id')
runs = {a: {json.loads(l)['q']: json.loads(l) for l in open(f'data/queries/t4_dev_v1/dev_{a}.jsonl', encoding='utf-8')} for a in 'bd'}
con = lambda d: set(row.at[d, 'concepts']) if row.at[d, 'concepts'] is not None else set()
ipc = lambda d: {x[:4] for x in (row.at[d, 'ipc'] if row.at[d, 'ipc'] is not None else [])}

seen = {}
for q in gt:
    s = set()
    for a in 'bd':
        for e in runs[a].get(q, {}).get('log', []):
            if e.get('tool') in ('count_results', 'submit') and e.get('query') and 'error' not in e:
                try:
                    s |= set(E.run(e['query'], ipc=e.get('ipc') or None, exclude=(q,)))
                except ValueError:
                    pass
    seen[q] = s
missed = [(q, d) for q in sorted(gt) for d in sorted(gt[q])
          if d not in set(runs['b'][q]['hit_ids']) | set(runs['d'][q]['hit_ids']) and d not in seen[q]]
cells = collections.defaultdict(list)
for q, d in missed:
    L = row.at[d, 'lang']
    if L in ('ko', 'en'):
        cells[(L, bool(con(q) & con(d)), bool(ipc(q) & ipc(d)))].append((q, d))
rnd = random.Random(20261012)
pick = []
for k in sorted(cells):
    v = cells[k][:]; rnd.shuffle(v); pick += [(k, x) for x in v[:3]]


def terms(q):
    t = set()
    for a in 'bd':
        for e in runs[a][q]['log']:
            if e.get('tool') in ('count_results', 'submit') and e.get('query'):
                for tok in re.findall(r'"([^"]+)"|([^\s()+*!"]+)', e['query']):
                    w = (tok[0] or tok[1]).strip()
                    if len(w) >= 2:
                        t.add(w)
    return sorted(t)


def present(d, ts):
    txt = K.norm_text(' '.join(str(row.at[d, f] or '') for f in ('title', 'abstract', 'claims_full', 'claims_independent')))
    return [w for w in ts if K.norm_text(w) in txt]


sheet = []
for (L, sc, si), (q, d) in pick:
    ts = terms(q)
    sheet.append({'cell': f'{L}|concept={int(sc)}|ipc={int(si)}', 'q': q, 'gt': d,
                  'gt_len': {f: len(str(row.at[d, f] or '')) for f in ('title', 'abstract', 'claims_full')},
                  'gt_title': str(row.at[d, 'title'])[:200], 'gt_abstract': str(row.at[d, 'abstract'] or '')[:500],
                  'q_claim1': str(row.at[q, 'first_claim_original'] or '')[:500],
                  'shared_concepts': sorted(con(q) & con(d)), 'q_ipc': sorted(ipc(q)), 'gt_ipc': sorted(ipc(d)),
                  'query_terms_n': len(ts), 'query_terms_present_in_gt': present(d, ts)[:30]})
print(json.dumps({'cells': {f'{k[0]}|c{int(k[1])}|i{int(k[2])}': len(v) for k, v in sorted(cells.items())}, 'n': len(sheet)}, ensure_ascii=False))
json.dump(sheet, open('data/interim/t4_dev/miss_sample_sheet.json', 'w'), ensure_ascii=False, indent=1)
