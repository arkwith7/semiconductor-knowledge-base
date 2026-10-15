"""PLAN-006 T4 v1 사후 분석 — 동결된 b·d 로그만 재생한다(LLM 재호출 없음). 새 가설 도출용 탐색 분석.
여기서 나온 가설은 이 dev 로 다시 검증하지 않는다(새 평가 집합 필요)."""
import sys, json, collections, re
sys.path.insert(0, 'scripts')
import ir_corpus, kipris_emulator as K, report_t4_query as R
from splits import load_split

split = sys.argv[1] if len(sys.argv) > 1 else 'dev'
src = {'dev': 'data/queries/t4_dev_v1/dev_{a}.jsonl', 'train': 'data/interim/t4_stage4/train_check_{a}.jsonl'}[split]
gt = R.load_gt(split, load_split())
C = ir_corpus.load(['doc_id', 'is_candidate', 'lang', 'title', 'abstract', 'claims_full', 'claims_independent', 'ipc', 'concepts'])
E = K.Emulator(C)
lang = dict(zip(C.doc_id, C.lang)); con = {d: set(v) if v is not None else set() for d, v in zip(C.doc_id, C.concepts)}
ipc = {d: {x[:4] for x in (v if v is not None else [])} for d, v in zip(C.doc_id, C.ipc)}
runs = {a: {json.loads(l)['q']: json.loads(l) for l in open(src.format(a=a), encoding='utf-8')} for a in 'bd'}

seen = {a: {} for a in 'bd'}
for a in 'bd':
    for q, r in runs[a].items():
        s = set()
        for e in r['log']:
            if e.get('tool') in ('count_results', 'submit') and e.get('query') and 'error' not in e:
                try:
                    s |= set(E.run(e['query'], ipc=e.get('ipc') or None, exclude=(q,)))
                except ValueError:
                    pass
        seen[a][q] = s

cat = collections.Counter(); bylang = collections.defaultdict(collections.Counter); feats = collections.defaultdict(collections.Counter)
for q in sorted(gt):
    if q not in runs['b'] or q not in runs['d']:
        continue
    hb, hd = set(runs['b'][q]['hit_ids']), set(runs['d'][q]['hit_ids'])
    for d in gt[q]:
        k = 'both' if d in hb and d in hd else 'd_only' if d in hd else 'b_only' if d in hb else 'both_missed'
        if k == 'both_missed':
            sb, sd = d in seen['b'][q], d in seen['d'][q]
            k = 'missed_seen_not_accepted' if (sb or sd) else 'missed_never_retrieved'
        cat[k] += 1; bylang[k][lang.get(d, '?')] += 1
        f = feats[k]
        f['shares_concept'] += bool(con.get(q, set()) & con.get(d, set()))
        f['shares_ipc_subclass'] += bool(ipc.get(q, set()) & ipc.get(d, set()))
        f['has_claims'] += bool((C.set_index('doc_id').at[d, 'claims_full'] or '') if False else True)
        f['n'] += 1
out = {'split': split, 'gt_pairs': sum(cat.values()), 'categories': dict(cat),
       'by_language': {k: dict(v) for k, v in bylang.items()},
       'features': {k: {kk: (round(vv / v['n'], 3) if kk != 'n' else vv) for kk, vv in v.items() if kk != 'has_claims'} for k, v in feats.items()}}
print(json.dumps(out, ensure_ascii=False, indent=1))
json.dump(out, open(f'data/interim/t4_dev/miss_analysis_{split}.json', 'w'), ensure_ascii=False, indent=1)
