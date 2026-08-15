# Definition of Done — Quality Gates

*Apply this checklist to every ticket in `07_Backlog_Epics_Tickets.md` before
considering it complete, in addition to that ticket's own acceptance criteria.
This document is generic and stable — it should rarely need to change.*

---

## 1. Neutrality check (applies to any ticket touching user-facing output)

- [ ] No evaluative wording present: "best", "good", "excellent", "top",
      "recommended", "better than", or French equivalents ("bon", "meilleur",
      "recommandé", "excellent").
- [ ] No implicit ranking signal in UI (color, size, badge, ordering) tied to
      a result indicator.
- [ ] Any explanatory text is static/versioned content, not freely generated
      by the LLM at request time.
- [ ] If in doubt, run the query/scenario past the adversarial test set from
      ticket AGENT-3, even for non-agent tickets — a frontend or API bug can
      reintroduce implicit ranking just as easily as a prompt issue.

## 2. Data integrity

- [ ] No indicator value is estimated, backfilled, or guessed when the source
      marks it as non-diffused (below threshold).
- [ ] Every displayed figure traces to a `SourceReference` — no orphan numbers.
- [ ] Historical data is never overwritten; new ingestion runs add rows, they
      don't mutate past years.

## 3. Testing

- [ ] Unit tests for domain/application logic exist and pass, independent of
      database or HTTP framework.
- [ ] Integration tests exist for any new endpoint, covering at least one
      normal case and one edge case (missing data, below threshold, empty
      result set).
- [ ] Tests run inside `docker compose` or an equivalent reproducible
      environment, not only "on my machine."

## 4. Documentation sync

- [ ] `docs/04_Journal_Decisions.md` updated if this ticket involved a
      structuring choice not already recorded.
- [ ] `08_API_Contract.md` updated if this ticket changed an endpoint's real
      shape.
- [ ] `docs/05_Resultats_Spike_Technique.md` referenced (not contradicted) for
      any ticket touching the directory/indicators join or historical data.

## 5. Architecture conformance

- [ ] No new service, queue, or database engine introduced without a
      documented reason added to `docs/02_Architecture_Decisions.md`
      ("Alternatives explicitement écartées" section should be revisited, not
      silently ignored).
- [ ] `domain/` code has zero framework imports (FastAPI, SQLAlchemy, etc.).
- [ ] Configuration values are read from environment/settings, never
      hardcoded.

## 6. Language and conventions

- [ ] Code, comments, commit messages, identifiers in English.
- [ ] Commit is small and scoped to this ticket (or a clearly explained
      reason for a larger commit).

---

## When a ticket fails this checklist

Do not silently patch around it. Flag the gap, note it in
`docs/04_Journal_Decisions.md` if it reveals a real design question, and only
then proceed. A ticket that "works" but fails the neutrality or data-integrity
sections is not done — this product's credibility depends on both more than
on shipping speed.
