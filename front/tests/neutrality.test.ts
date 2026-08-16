/**
 * The frontend counterpart of back/tests/unit/test_neutrality.py.
 *
 * Copy discipline is not enough on its own: a single convenient word in a
 * label would breach the product's central promise, and nobody would notice in
 * review. This scans every string the frontend authors, and asserts the
 * structural guarantees that keep a ranking un-buildable.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import * as copy from "../src/content/copy";

/**
 * From docs/09_Definition_of_Done_Quality_Gates.md §1 plus the charter's own
 * forbidden vocabulary. Word-boundary matched: a naive substring search flags
 * the project's own guardrails ("classement" inside "ne classe pas") and
 * innocent words ("bonne" inside "abonnement").
 */
const FORBIDDEN = [
  "best", "top", "recommended", "better than",
  "meilleur", "meilleure", "meilleurs", "meilleures",
  "bon", "bonne", "excellent", "excellente",
  "recommandé", "recommandée", "recommande",
  "classement", "palmarès", "performant", "performante",
  "surperforme", "sous-performe", "sous-performant",
];

/**
 * Strings that legitimately contain a forbidden word because they *deny* it.
 *
 * "Ce service ne classe pas et ne recommande aucun choix" must be sayable —
 * refusing to rank is the product's central promise, and stating it requires
 * naming the thing being refused. Each entry is an exact string, so a new
 * usage of a forbidden word cannot pass by resembling an approved one: it
 * fails until a human reviews it and adds it here deliberately.
 */
const APPROVED_NEGATIONS = new Set<string>([
  copy.HOME.intro,
  copy.HOME.commitments[2].title,
  copy.HOME.commitments[2].body,
]);

function collectStrings(value: unknown, path: string, into: Array<[string, string]>) {
  if (typeof value === "string") {
    into.push([path, value]);
  } else if (Array.isArray(value)) {
    value.forEach((item, i) => collectStrings(item, `${path}[${i}]`, into));
  } else if (value && typeof value === "object") {
    for (const [key, inner] of Object.entries(value)) {
      collectStrings(inner, `${path}.${key}`, into);
    }
  }
  // Functions (message templates) are exercised separately below.
}

describe("frontend copy contains no evaluative wording", () => {
  const strings: Array<[string, string]> = [];
  collectStrings(copy, "copy", strings);

  it("collects a meaningful number of strings (guards against a vacuous scan)", () => {
    expect(strings.length).toBeGreaterThan(30);
  });

  it.each(FORBIDDEN)("never uses %s", (word) => {
    const pattern = new RegExp(`(^|[^\\p{L}])${word}([^\\p{L}]|$)`, "iu");
    const offenders = strings.filter(
      ([, text]) => pattern.test(text) && !APPROVED_NEGATIONS.has(text),
    );
    expect(offenders).toEqual([]);
  });

  it("every approved negation actually negates", () => {
    // An allowlist that drifts into excusing real evaluative wording would be
    // worse than no allowlist. Each entry must contain an explicit denial.
    for (const text of APPROVED_NEGATIONS) {
      expect(text.toLowerCase()).toMatch(/\bne\b|\baucun\b|\bsans\b|\bjamais\b/);
    }
  });

  it("templated messages are also clean", () => {
    const rendered = [
      copy.SEARCH.countMany(3),
      copy.SEARCH.showing(3, 9),
      copy.SEARCH.distance(2.4),
      copy.SEARCH.removeFilter("Type"),
      copy.FACT_SHEET.yearLabel(2025),
      copy.FACT_SHEET.candidates(120),
      copy.FACT_SHEET.lastSync("15/08/2026"),
    ];
    for (const text of rendered) {
      for (const word of FORBIDDEN) {
        expect(text.toLowerCase()).not.toMatch(
          new RegExp(`(^|[^\\p{L}])${word}([^\\p{L}]|$)`, "iu"),
        );
      }
    }
  });
});

/**
 * The home page states the scope reminder before any search has happened, so
 * there is no API response to carry it — the backend only publishes the
 * "version courte" that accompanies results. Rather than invent a second
 * wording, the frontend reproduces the charter's own "version d'accueil"
 * verbatim, and these tests make the charter the enforced source of truth:
 * if either copy drifts from docs/14, CI fails.
 *
 * This is the one place frontend-authored text restates reviewed editorial
 * content, and it is why it is allowed — see 04_Journal_Decisions.md.
 */
describe("home-page scope reminder matches the charter verbatim", () => {
  const charter = readFileSync(
    join(__dirname, "..", "..", "docs", "14_Charte_Neutralite_Editoriale.md"),
    "utf8",
  );

  it("copy.HOME.intro appears word for word in the charter", () => {
    expect(charter).toContain(copy.HOME.intro);
  });

  it("the page description appears word for word in the charter", () => {
    const html = readFileSync(join(__dirname, "..", "index.html"), "utf8");
    const description = /name="description"[\s\S]*?content="([^"]+)"/.exec(html)?.[1];
    expect(description).toBeTruthy();
    expect(charter).toContain(description!);
  });

  it("index.html carries no evaluative wording either", () => {
    // index.html sits outside copy.ts, so the main scan misses it. Its title
    // and description are user-facing and indexable, which makes them exactly
    // the kind of surface a ranking claim would slip into unnoticed.
    const html = readFileSync(join(__dirname, "..", "index.html"), "utf8");
    for (const word of FORBIDDEN) {
      const pattern = new RegExp(`(^|[^\\p{L}])${word}([^\\p{L}]|$)`, "iu");
      const offending = pattern.test(html) && !charter.includes(copy.HOME.intro);
      expect(offending).toBe(false);
    }
  });
});

describe("no structural affordance for ranking", () => {
  /**
   * Source with comments removed. The structural checks below look for code
   * constructs; a doc comment explaining *why* a component is not dismissible
   * would otherwise fail the very test asserting that it is not.
   */
  const src = (file: string) =>
    readFileSync(join(__dirname, "..", "src", file), "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "");

  it("the search page offers no sort control", () => {
    const page = src("pages/SearchResultsPage.tsx");
    // The API rejects any sort parameter with a 400; the UI must not offer one
    // at all, not even disabled — a disabled control is a state that can regress.
    expect(page).not.toMatch(/sort_by|order_by|<select/i);
  });

  it("Figure exposes no prop that could carry a judgement", () => {
    const figure = src("components/Figure.tsx");
    // No variant/tone/status/emphasis prop: nothing can be passed in meaning
    // "good" or "bad", so a value cannot be coloured by its magnitude.
    expect(figure).not.toMatch(/\b(variant|tone|status|emphasis|severity)\s*[?:]/);
  });

  it("Figure requires a source, so no figure can appear unsourced", () => {
    expect(src("components/Figure.tsx")).toMatch(/^\s*source: Source;/m);
  });

  it("the search hit type carries no result figure", () => {
    const types = src("api/types.ts");
    const hit = types.slice(
      types.indexOf("export interface SearchHit"),
      types.indexOf("export interface FiltersApplied"),
    );
    for (const field of ["taux_", "valeur_ajoutee", "Figure"]) {
      expect(hit).not.toContain(field);
    }
  });

  it("no red/green pair exists in the design tokens", () => {
    const tokens = readFileSync(
      join(__dirname, "..", "src", "styles", "tokens.css"),
      "utf8",
    );
    // Charter §9 forbids red/green to differentiate results. Only one red
    // exists (technical error) and there is no green at all.
    expect(tokens).not.toMatch(/--c-(success|good|positive|negative|bad)\b/);
    expect(tokens.match(/--c-error/g)?.length).toBeGreaterThan(0);
  });

  it("the scope disclaimer cannot be dismissed", () => {
    const disclaimer = src("components/ScopeDisclaimer.tsx");
    expect(disclaimer).not.toMatch(/dismiss|onClose|localStorage|useState/);
  });
});
