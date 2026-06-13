// About page — three flow variants for the user to choose from.
// Each variant is a complete (slim) About page using the Herbarium system.

const A_DISPLAY = '"EB Garamond", "Cardo", Georgia, serif';
const A_MONO    = '"IBM Plex Mono", ui-monospace, monospace';
const A_TOKENS = {
  parchment:     "#f3e9cd",
  parchmentDeep: "#ead9b0",
  parchmentLight:"#fdf8e9",
  ink:           "#1a1f17",
  forest:        "#243025",
  forestDeep:    "#19211b",
  accent:        "#3d5b3e",
  umber:         "#7a5a3a",
  rule:          "#8a7a4a",
};

// ─── shared bits ───
const ALabel = ({ children, color = A_TOKENS.umber, style = {} }) => (
  <div style={{
    fontFamily: A_MONO,
    fontSize: 11, letterSpacing: "0.22em",
    textTransform: "uppercase",
    color, opacity: 0.7,
    ...style,
  }}>{children}</div>
);

const ADivider = ({ color = A_TOKENS.rule, glyph = "❦" }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 14, color, margin: "32px auto", maxWidth: 480 }}>
    <span style={{ flex: 1, height: 1, background: color, opacity: 0.5 }}></span>
    <span style={{ flex: 1, height: 3, borderTop: `1px solid ${color}`, borderBottom: `1px solid ${color}`, opacity: 0.5 }}></span>
    <span style={{ fontFamily: A_DISPLAY, fontSize: 22, opacity: 0.7, lineHeight: 1 }}>{glyph}</span>
    <span style={{ flex: 1, height: 3, borderTop: `1px solid ${color}`, borderBottom: `1px solid ${color}`, opacity: 0.5 }}></span>
    <span style={{ flex: 1, height: 1, background: color, opacity: 0.5 }}></span>
  </div>
);

const ANav = () => {
  const links = ["Home", "Download", "About", "Contact"];
  return (
    <div style={{
      borderTop: `3px double ${A_TOKENS.rule}`,
      borderBottom: `1px solid ${A_TOKENS.rule}66`,
      background: A_TOKENS.parchment,
      padding: "20px 48px",
      display: "flex", alignItems: "center", justifyContent: "space-between",
    }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
        <div style={{ fontFamily: A_DISPLAY, fontSize: 36, fontWeight: 500, lineHeight: 1, color: A_TOKENS.ink }}>
          POPP<span style={{ fontStyle: "italic" }}>y</span>
        </div>
        <div style={{ fontFamily: A_MONO, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", opacity: 0.6, color: A_TOKENS.ink }}>
          Pharmacopoeia<br/>Ontologica
        </div>
      </div>
      <div style={{ display: "flex", gap: 28 }}>
        {links.map(l => (
          <div key={l} style={{
            fontFamily: A_DISPLAY,
            fontVariantCaps: "all-small-caps",
            letterSpacing: "0.14em",
            fontSize: 16,
            color: l === "About" ? A_TOKENS.accent : A_TOKENS.ink,
            borderBottom: l === "About" ? `2px solid ${A_TOKENS.accent}` : "2px solid transparent",
            paddingBottom: 2,
          }}>{l}</div>
        ))}
      </div>
    </div>
  );
};

const AFooter = () => (
  <div style={{
    background: A_TOKENS.forestDeep,
    color: A_TOKENS.parchment,
    padding: "32px 48px",
    fontFamily: A_MONO, fontSize: 10, letterSpacing: "0.16em",
    textTransform: "uppercase", opacity: 0.7,
    display: "flex", justifyContent: "space-between",
  }}>
    <span>© MMXXVI · Oresta S.I. Hewryk</span>
    <span>Editio Prima · v 0.1</span>
  </div>
);

const AHero = ({ compact = false }) => (
  <section style={{ padding: compact ? "48px 48px 24px" : "72px 48px 32px", textAlign: "center" }}>
    <div style={{ maxWidth: 880, margin: "0 auto" }}>
      <ALabel>About</ALabel>
      <h1 style={{
        fontFamily: A_DISPLAY,
        fontWeight: 500,
        fontSize: compact ? 52 : 60,
        lineHeight: 1.05, letterSpacing: "-0.015em",
        margin: "16px 0 20px",
        color: A_TOKENS.forest,
      }}>
        Reuniting the <span style={{ fontStyle: "italic" }}>materia medica</span> with the molecule.
      </h1>
      <p style={{
        fontFamily: A_DISPLAY, fontStyle: "italic",
        fontSize: 20, color: A_TOKENS.umber,
        margin: 0, maxWidth: 720, marginLeft: "auto", marginRight: "auto",
        lineHeight: 1.4,
      }}>
        For most of human history, medicine was made from plants. POPPy is a quiet attempt to render that knowledge legible to machines.
      </p>
      <ADivider />
      <p style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 18, color: A_TOKENS.ink, opacity: 0.85, margin: "0 auto", maxWidth: 640 }}>
        A project of the <a style={{ color: A_TOKENS.accent, fontStyle: "normal", borderBottom: `1px dotted ${A_TOKENS.accent}` }}>Romano Lab</a> at the <span style={{ fontVariantCaps: "all-small-caps", letterSpacing: "0.12em", color: A_TOKENS.umber, fontStyle: "normal" }}>University of Pennsylvania</span>.
      </p>
    </div>
  </section>
);

const AMaintainerCard = ({ compact = false }) => (
  <div style={{
    background: A_TOKENS.parchmentLight,
    border: `1px solid ${A_TOKENS.rule}66`,
    padding: compact ? "32px 36px" : "44px 48px",
    display: "grid",
    gridTemplateColumns: compact ? "100px 1fr auto" : "140px 1fr auto",
    gap: compact ? 28 : 36,
    alignItems: "center",
  }}>
    <div style={{
      width: compact ? 100 : 140, height: compact ? 100 : 140, borderRadius: "50%",
      background: A_TOKENS.parchmentDeep,
      border: `1px solid ${A_TOKENS.rule}`,
      fontFamily: A_DISPLAY, fontStyle: "italic",
      fontSize: compact ? 40 : 56, color: A_TOKENS.umber,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>OH</div>
    <div>
      <ALabel>Maintainer</ALabel>
      <div style={{ fontFamily: A_DISPLAY, fontSize: compact ? 26 : 30, color: A_TOKENS.forest, fontWeight: 600, lineHeight: 1, marginTop: 6 }}>
        Oresta S.I. Hewryk
      </div>
      <div style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 16, color: A_TOKENS.umber, marginTop: 4 }}>
        Founder · Lead curator
      </div>
      <div style={{ marginTop: 12, fontFamily: A_DISPLAY, fontSize: 16, color: A_TOKENS.accent, borderBottom: `1px dotted ${A_TOKENS.accent}`, display: "inline-block" }}>
        Romano Lab · <span style={{ fontVariantCaps: "all-small-caps", letterSpacing: "0.12em", color: A_TOKENS.umber }}>University of Pennsylvania</span>
      </div>
    </div>
    <button style={{
      fontFamily: A_DISPLAY,
      fontVariantCaps: "all-small-caps",
      letterSpacing: "0.18em",
      fontSize: 14, padding: "12px 24px",
      background: A_TOKENS.forest, color: A_TOKENS.parchment,
      border: `1px solid ${A_TOKENS.forest}`,
      whiteSpace: "nowrap", cursor: "pointer",
    }}>Visit the lab →</button>
  </div>
);

const METHODS = [
  { n: "01", t: "Curate",   b: "Plant taxa are reconciled against canonical sources (Kew, GBIF). Each entry carries its original ethnobotanical reference." },
  { n: "02", t: "Resolve",  b: "Compounds are mapped to InChI / SMILES via PubChem and ChEBI. Duplicates are merged through structural fingerprints." },
  { n: "03", t: "Annotate", b: "Targets and therapeutic effects are linked through peer-reviewed literature, with every claim retaining its primary citation." },
];

const REFS = [
  { n: "i.",   t: "The Open Biological and Biomedical Ontologies (OBO) Foundry",          a: "Smith, B., et al.",          m: "Nature Biotechnology · 2007" },
  { n: "ii.",  t: "ChEBI in 2024: chemical entities of biological interest",              a: "Hastings, J., et al.",       m: "Nucleic Acids Research · 2024" },
  { n: "iii.", t: "PubChem in 2023: improved data integration and substructure search",   a: "Kim, S., et al.",            m: "Nucleic Acids Research · 2023" },
  { n: "iv.",  t: "Kew Medicinal Plant Names Services",                                    a: "Royal Botanic Gardens, Kew", m: "Reference database · 2024" },
  { n: "v.",   t: "Global Biodiversity Information Facility (GBIF)",                       a: "GBIF Secretariat",           m: "Biodiversity records · 2024" },
];

// ════════════════════════════════════════════════════════════════════
//  OPTION A — Narrative chapters
//   hero → maintainer (early) → mission (dark) → method → cite+refs
// ════════════════════════════════════════════════════════════════════
const AboutA = () => (
  <div style={{ width: 1280, background: A_TOKENS.parchment, fontFamily: A_DISPLAY, color: A_TOKENS.ink, lineHeight: 1.55 }}>
    <ANav />
    <AHero />

    {/* Maintainer up front */}
    <section style={{ padding: "20px 48px 60px" }}>
      <div style={{ maxWidth: 920, margin: "0 auto" }}>
        <AMaintainerCard />
      </div>
    </section>

    {/* MISSION — full-bleed forest chapter break */}
    <section style={{ background: A_TOKENS.forest, color: A_TOKENS.parchment, padding: "80px 48px" }}>
      <div style={{ maxWidth: 920, margin: "0 auto" }}>
        <ALabel color={A_TOKENS.parchmentDeep}>The mission</ALabel>
        <h2 style={{ fontFamily: A_DISPLAY, fontWeight: 500, fontSize: 44, lineHeight: 1.15, margin: "12px 0 28px", fontStyle: "italic", color: A_TOKENS.parchment }}>
          The first structured phytochemicals ontology, built for AI-based drug discovery.
        </h2>
        <p style={{ fontFamily: A_DISPLAY, fontSize: 21, lineHeight: 1.65, opacity: 0.92, marginBottom: 22, color: A_TOKENS.parchment }}>
          POPPy catalogues medicinal plants, the compounds they contain, the human targets those compounds engage, and the therapeutic effects they produce — each relationship traceable to the peer-reviewed literature that established it.
        </p>
        <p style={{ fontFamily: A_DISPLAY, fontSize: 21, lineHeight: 1.65, opacity: 0.85, color: A_TOKENS.parchment }}>
          The goal is simple: make four millennia of accumulated botanical pharmacology queryable by a graph, a SPARQL endpoint, or a language model — without losing the citation trail.
        </p>
      </div>
    </section>

    {/* METHOD */}
    <section style={{ padding: "70px 48px" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <ALabel>Method</ALabel>
          <h2 style={{ fontFamily: A_DISPLAY, fontSize: 36, fontWeight: 500, color: A_TOKENS.forest, margin: "8px 0 0" }}>How POPPy is built</h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 24 }}>
          {METHODS.map(m => (
            <div key={m.n} style={{ background: A_TOKENS.parchmentLight, border: `1px solid ${A_TOKENS.rule}66`, padding: "30px 32px 36px" }}>
              <div style={{ fontFamily: A_MONO, fontSize: 12, letterSpacing: "0.22em", color: A_TOKENS.umber }}>{m.n}</div>
              <h3 style={{ fontFamily: A_DISPLAY, fontSize: 28, color: A_TOKENS.forest, margin: "14px 0 12px", fontStyle: "italic" }}>{m.t}</h3>
              <p style={{ fontFamily: A_DISPLAY, fontSize: 16, lineHeight: 1.55, opacity: 0.85, margin: 0 }}>{m.b}</p>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* CITE + REFS merged */}
    <section style={{ background: A_TOKENS.parchmentDeep + "88", padding: "70px 48px", borderTop: `1px solid ${A_TOKENS.rule}66`, borderBottom: `1px solid ${A_TOKENS.rule}66` }}>
      <div style={{ maxWidth: 920, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <ALabel>Cite & sources</ALabel>
          <h2 style={{ fontFamily: A_DISPLAY, fontSize: 36, fontWeight: 500, color: A_TOKENS.forest, margin: "8px 0 0" }}>Using POPPy in your work</h2>
        </div>
        <div style={{ background: A_TOKENS.parchmentLight, border: `1px solid ${A_TOKENS.rule}66`, padding: "28px 36px", marginBottom: 28 }}>
          <ALabel>Recommended citation</ALabel>
          <p style={{ fontFamily: A_DISPLAY, fontSize: 18, lineHeight: 1.6, color: A_TOKENS.ink, paddingLeft: 16, borderLeft: `2px solid ${A_TOKENS.rule}`, margin: "12px 0 0" }}>
            Hewryk, O. S. I., & Romano Lab (2026). POPPy: A Phyto-Ontology Platform for Pharmacology. <em>University of Pennsylvania</em>.
          </p>
        </div>
        <details style={{ background: A_TOKENS.parchmentLight, border: `1px solid ${A_TOKENS.rule}66`, padding: "20px 32px" }}>
          <summary style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 18, color: A_TOKENS.forest, cursor: "pointer" }}>
            Sources we build on ({REFS.length} references)
          </summary>
          <div style={{ marginTop: 18 }}>
            {REFS.map(r => (
              <div key={r.n} style={{ padding: "14px 0", borderBottom: `1px dotted ${A_TOKENS.rule}55`, display: "grid", gridTemplateColumns: "40px 1fr", gap: 16 }}>
                <span style={{ fontFamily: A_DISPLAY, fontStyle: "italic", color: A_TOKENS.umber }}>{r.n}</span>
                <div>
                  <div style={{ fontFamily: A_DISPLAY, fontSize: 16, color: A_TOKENS.forest }}>{r.t}</div>
                  <div style={{ fontFamily: A_MONO, fontSize: 11, letterSpacing: "0.14em", color: A_TOKENS.umber, marginTop: 4 }}>{r.a} · {r.m}</div>
                </div>
              </div>
            ))}
          </div>
        </details>
      </div>
    </section>

    <AFooter />
  </div>
);

// ════════════════════════════════════════════════════════════════════
//  OPTION B — Editorial / pull-quote
//   long-form magazine layout, drop cap, pull quote, footnote-style cite
// ════════════════════════════════════════════════════════════════════
const AboutB = () => (
  <div style={{ width: 1280, background: A_TOKENS.parchment, fontFamily: A_DISPLAY, color: A_TOKENS.ink, lineHeight: 1.55 }}>
    <ANav />
    <AHero compact />

    {/* WHO WE ARE — drop cap + pull quote */}
    <section style={{ padding: "32px 48px 60px" }}>
      <div style={{ maxWidth: 760, margin: "0 auto" }}>
        <p style={{ fontFamily: A_DISPLAY, fontSize: 22, lineHeight: 1.65, margin: "0 0 24px" }}>
          <span style={{ fontFamily: A_DISPLAY, fontSize: 90, lineHeight: 0.85, float: "left", marginRight: 14, marginTop: 6, color: A_TOKENS.forest, fontWeight: 500 }}>P</span>
          OPPy — the <em>Phyto-Ontology Platform for Pharmacology</em> — is the first structured ontology of phytochemicals built for AI-based drug discovery. It is developed and maintained by the <a style={{ color: A_TOKENS.accent, borderBottom: `1px dotted ${A_TOKENS.accent}` }}>Romano Lab</a> at the University of Pennsylvania, with input from collaborators across ethnobotany, cheminformatics, and knowledge-graph engineering.
        </p>

        <p style={{ fontFamily: A_DISPLAY, fontSize: 21, lineHeight: 1.65, margin: "0 0 36px" }}>
          We catalogue medicinal plants, the compounds they contain, the human targets those compounds engage, and the therapeutic effects they produce — each relationship traceable to the peer-reviewed literature that established it.
        </p>

        {/* PULL QUOTE */}
        <div style={{ textAlign: "center", margin: "48px 0 56px", padding: "0 40px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, color: A_TOKENS.rule, marginBottom: 24 }}>
            <span style={{ flex: 1, height: 1, background: "currentColor", opacity: 0.4 }}></span>
            <span style={{ fontFamily: A_DISPLAY, fontSize: 16 }}>❦</span>
            <span style={{ flex: 1, height: 1, background: "currentColor", opacity: 0.4 }}></span>
          </div>
          <p style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 36, lineHeight: 1.25, color: A_TOKENS.forest, margin: 0 }}>
            "Four millennia of botanical pharmacology, queryable by a graph — without losing the citation trail."
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 16, color: A_TOKENS.rule, marginTop: 24 }}>
            <span style={{ flex: 1, height: 1, background: "currentColor", opacity: 0.4 }}></span>
            <span style={{ fontFamily: A_DISPLAY, fontSize: 16 }}>❦</span>
            <span style={{ flex: 1, height: 1, background: "currentColor", opacity: 0.4 }}></span>
          </div>
        </div>

        {/* METHOD inline — alphabetic, not numeric, runs with text */}
        <h2 style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 28, color: A_TOKENS.forest, margin: "0 0 16px" }}>How it's built</h2>
        {METHODS.map((m, i) => (
          <div key={m.n} style={{ display: "grid", gridTemplateColumns: "100px 1fr", gap: 24, padding: "16px 0", borderBottom: i < METHODS.length - 1 ? `1px dotted ${A_TOKENS.rule}55` : "none" }}>
            <div style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 22, color: A_TOKENS.umber }}>{m.t}.</div>
            <div style={{ fontFamily: A_DISPLAY, fontSize: 17, lineHeight: 1.6, color: A_TOKENS.ink }}>{m.b}</div>
          </div>
        ))}

        {/* FOOTNOTE-STYLE CITE */}
        <div style={{ marginTop: 56, padding: "20px 28px", background: A_TOKENS.parchmentLight, border: `1px solid ${A_TOKENS.rule}55`, borderLeft: `3px solid ${A_TOKENS.accent}` }}>
          <ALabel>How to cite</ALabel>
          <p style={{ fontFamily: A_DISPLAY, fontSize: 16, lineHeight: 1.6, color: A_TOKENS.ink, margin: "8px 0 0" }}>
            Hewryk, O. S. I., & Romano Lab (2026). <em>POPPy: A Phyto-Ontology Platform for Pharmacology</em>. University of Pennsylvania. <span style={{ color: A_TOKENS.accent, borderBottom: `1px dotted ${A_TOKENS.accent}`, marginLeft: 8 }}>Copy BibTeX</span>
          </p>
        </div>

        {/* REFS — tight list */}
        <div style={{ marginTop: 40 }}>
          <ALabel>References</ALabel>
          <ol style={{ listStyle: "none", padding: 0, margin: "16px 0 0", borderTop: `1px solid ${A_TOKENS.rule}66` }}>
            {REFS.map(r => (
              <li key={r.n} style={{ padding: "12px 0", borderBottom: `1px dotted ${A_TOKENS.rule}55`, display: "grid", gridTemplateColumns: "32px 1fr", gap: 16 }}>
                <span style={{ fontFamily: A_DISPLAY, fontStyle: "italic", color: A_TOKENS.umber, fontSize: 14 }}>{r.n}</span>
                <div style={{ fontFamily: A_DISPLAY, fontSize: 15, lineHeight: 1.45 }}>
                  <span style={{ color: A_TOKENS.forest }}>{r.t}.</span>
                  <span style={{ color: A_TOKENS.umber, fontStyle: "italic" }}> {r.a}. {r.m}.</span>
                </div>
              </li>
            ))}
          </ol>
        </div>

        {/* MAINTAINER — small, end of essay */}
        <div style={{ marginTop: 56, paddingTop: 32, borderTop: `1px solid ${A_TOKENS.rule}66` }}>
          <ALabel>Maintainer</ALabel>
          <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 20 }}>
            <div style={{ width: 56, height: 56, borderRadius: "50%", background: A_TOKENS.parchmentDeep, border: `1px solid ${A_TOKENS.rule}`, fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 22, color: A_TOKENS.umber, display: "flex", alignItems: "center", justifyContent: "center" }}>OH</div>
            <div>
              <div style={{ fontFamily: A_DISPLAY, fontSize: 19, color: A_TOKENS.forest, fontWeight: 600 }}>Oresta S.I. Hewryk</div>
              <div style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 14, color: A_TOKENS.umber }}>Founder · Romano Lab, University of Pennsylvania</div>
            </div>
          </div>
        </div>

      </div>
    </section>

    <AFooter />
  </div>
);

// ════════════════════════════════════════════════════════════════════
//  OPTION C — Anchored chapter nav
//   sticky-left rail with section indices · Roman numeral chapters
// ════════════════════════════════════════════════════════════════════
const AboutC = () => {
  const chapters = [
    { roman: "I",  name: "Mission" },
    { roman: "II", name: "Method" },
    { roman: "III",name: "Citation" },
    { roman: "IV", name: "References" },
    { roman: "V",  name: "Maintainer" },
  ];

  const ChapterHead = ({ roman, label, title }) => (
    <div style={{ marginBottom: 32, textAlign: "left" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 18 }}>
        <span style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 60, color: A_TOKENS.umber, lineHeight: 1 }}>{roman}.</span>
        <div>
          <ALabel>{label}</ALabel>
          <h2 style={{ fontFamily: A_DISPLAY, fontSize: 36, fontWeight: 500, color: A_TOKENS.forest, margin: "6px 0 0" }}>{title}</h2>
        </div>
      </div>
      <div style={{ height: 1, background: A_TOKENS.rule, opacity: 0.5, marginTop: 18 }}></div>
    </div>
  );

  return (
    <div style={{ width: 1280, background: A_TOKENS.parchment, fontFamily: A_DISPLAY, color: A_TOKENS.ink, lineHeight: 1.55 }}>
      <ANav />
      <AHero compact />

      <section style={{ padding: "20px 48px 80px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", display: "grid", gridTemplateColumns: "200px 1fr", gap: 60 }}>
          {/* Sticky left rail */}
          <aside style={{ position: "sticky", top: 24, alignSelf: "start" }}>
            <ALabel>Contents</ALabel>
            <div style={{ marginTop: 20 }}>
              {chapters.map((c, i) => (
                <div key={c.roman} style={{
                  padding: "10px 0",
                  borderBottom: i < chapters.length - 1 ? `1px dotted ${A_TOKENS.rule}66` : "none",
                  display: "flex", alignItems: "baseline", gap: 12,
                  color: i === 0 ? A_TOKENS.accent : A_TOKENS.ink,
                }}>
                  <span style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 15, color: A_TOKENS.umber, minWidth: 24 }}>{c.roman}.</span>
                  <span style={{ fontFamily: A_DISPLAY, fontVariantCaps: "all-small-caps", letterSpacing: "0.14em", fontSize: 16 }}>{c.name}</span>
                </div>
              ))}
            </div>
          </aside>

          {/* Right content */}
          <div>

            {/* I. MISSION */}
            <ChapterHead roman="I" label="The mission" title="What POPPy is, and why" />
            <div style={{ marginBottom: 80, fontFamily: A_DISPLAY, fontSize: 19, lineHeight: 1.65 }}>
              <p style={{ margin: "0 0 18px" }}>
                POPPy — the <em>Phyto-Ontology Platform for Pharmacology</em> — is the first structured ontology of phytochemicals built for AI-based drug discovery. It is developed and maintained by the <a style={{ color: A_TOKENS.accent, borderBottom: `1px dotted ${A_TOKENS.accent}` }}>Romano Lab</a> at the University of Pennsylvania.
              </p>
              <p style={{ margin: 0 }}>
                We catalogue medicinal plants, the compounds they contain, the human targets those compounds engage, and the therapeutic effects they produce — each relationship traceable to the peer-reviewed literature that established it.
              </p>
            </div>

            {/* II. METHOD */}
            <ChapterHead roman="II" label="Method" title="How POPPy is built" />
            <div style={{ marginBottom: 80 }}>
              {METHODS.map((m, i) => (
                <div key={m.n} style={{ display: "grid", gridTemplateColumns: "60px 1fr", gap: 24, padding: "20px 0", borderBottom: i < METHODS.length - 1 ? `1px dotted ${A_TOKENS.rule}55` : "none" }}>
                  <div style={{ fontFamily: A_MONO, fontSize: 12, letterSpacing: "0.22em", color: A_TOKENS.umber }}>{m.n}</div>
                  <div>
                    <h3 style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 24, color: A_TOKENS.forest, margin: "0 0 6px" }}>{m.t}</h3>
                    <p style={{ fontFamily: A_DISPLAY, fontSize: 17, lineHeight: 1.6, color: A_TOKENS.ink, margin: 0, opacity: 0.9 }}>{m.b}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* III. CITATION */}
            <ChapterHead roman="III" label="How to cite" title="Using POPPy in your work" />
            <div style={{ marginBottom: 80 }}>
              <div style={{ background: A_TOKENS.parchmentLight, border: `1px solid ${A_TOKENS.rule}66`, padding: "24px 30px", marginBottom: 16 }}>
                <ALabel>Recommended citation</ALabel>
                <p style={{ fontFamily: A_DISPLAY, fontSize: 17, lineHeight: 1.6, paddingLeft: 14, borderLeft: `2px solid ${A_TOKENS.rule}`, margin: "10px 0 0" }}>
                  Hewryk, O. S. I., & Romano Lab (2026). POPPy: A Phyto-Ontology Platform for Pharmacology. <em>University of Pennsylvania</em>.
                </p>
              </div>
              <div style={{ background: A_TOKENS.ink, color: "#d9e4d7", padding: "16px 22px", fontFamily: A_MONO, fontSize: 12, lineHeight: 1.6 }}>
                <span style={{ color: "#c9b88a" }}>@misc</span>{"{poppy2026, "}<br/>
                &nbsp;&nbsp;<span style={{ color: "#c9b88a" }}>author</span> = {"{Hewryk, Oresta S. I. and Romano Lab}, "}<br/>
                &nbsp;&nbsp;<span style={{ color: "#c9b88a" }}>title</span> = {"{POPPy: A Phyto-Ontology Platform for Pharmacology}, "}<br/>
                &nbsp;&nbsp;<span style={{ color: "#c9b88a" }}>year</span> = {"{2026}"}<br/>
                {"}"}
              </div>
            </div>

            {/* IV. REFERENCES */}
            <ChapterHead roman="IV" label="References" title="Sources we build on" />
            <ol style={{ listStyle: "none", padding: 0, marginBottom: 80 }}>
              {REFS.map(r => (
                <li key={r.n} style={{ display: "grid", gridTemplateColumns: "40px 1fr auto", gap: 18, padding: "18px 0", borderBottom: `1px dotted ${A_TOKENS.rule}55`, alignItems: "baseline" }}>
                  <span style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 18, color: A_TOKENS.umber }}>{r.n}</span>
                  <div>
                    <div style={{ fontFamily: A_DISPLAY, fontSize: 17, color: A_TOKENS.forest }}>{r.t}</div>
                    <div style={{ fontFamily: A_DISPLAY, fontStyle: "italic", fontSize: 14, color: A_TOKENS.umber, marginTop: 3 }}>{r.a}</div>
                    <div style={{ fontFamily: A_MONO, fontSize: 11, letterSpacing: "0.14em", color: A_TOKENS.umber, marginTop: 4 }}>{r.m}</div>
                  </div>
                  <span style={{ fontFamily: A_MONO, fontSize: 11, letterSpacing: "0.18em", color: A_TOKENS.accent, border: `1px solid ${A_TOKENS.rule}`, padding: "5px 10px" }}>DOI</span>
                </li>
              ))}
            </ol>

            {/* V. MAINTAINER */}
            <ChapterHead roman="V" label="Primary maintainer" title="Behind the project" />
            <AMaintainerCard compact />

          </div>
        </div>
      </section>

      <AFooter />
    </div>
  );
};

Object.assign(window, { AboutA, AboutB, AboutC });
