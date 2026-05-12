# Expert Validation Log

> Running log of domain-expert consultations that shape the synthetic expert profiles (deliverable ②) and the 7,500 prior-art pairs (deliverable ④).

The plan signed by Prof. Shin commits to *"도메인 전문가 자문을 통해 현실성 있게 구성"* — this file is the audit trail proving that.

## Session template

```
### Session #NN — YYYY-MM-DD
- Expert (anonymized): role + years of experience + segment
- Mode: 1:1 interview | review of N profiles | review of M pairs
- Scope: which deliverable, which subset
- Materials shared: paths to artifacts (commit hash)
- Decisions:
  - keep | revise | reject — for each reviewed item
- Action items:
  - [ ] specific edit with target file and date
- Aggregate signal:
  - face-validity rating (1–5)
  - any patterns flagged (over/under-representation)
```

## Session log (newest first)

### Session #00 — 2026-05-12 (kickoff bookkeeping)
- Expert: N/A (process scaffold only)
- Mode: log file created
- Scope: defines the convention for sessions #01..
- Decisions: none
- Action items:
  - [ ] Recruit ≥ 3 domain experts (target mix: 1 process engineer, 1 IP-R&D specialist, 1 equipment vendor / MOTIE-affiliated)
  - [ ] Send Amendment v2 + this log + `dataset_rejected_patents_card.md` to Prof. Shin before the first review session

## Acceptance criteria for deliverable ② (set by advisor)

- ≥ 3 expert sessions logged before profiles are frozen.
- Each session must produce at least one keep/revise/reject decision per 10 sampled profiles.
- Aggregate face-validity ≥ 3.5/5.0 across the 100-profile sample.

## Anti-pattern checklist (revise on sight)

- All 100 profiles share the same education tier → unrealistic.
- Geographic distribution all in capital region → unrealistic for 소부장 SME context.
- No retired engineers — the plan's qualitative target explicitly names retiree-knowledge reuse; the cohort must include some.
- Skill claims that exceed years-of-experience by ≥ 2 std deviations of the empirical distribution.
