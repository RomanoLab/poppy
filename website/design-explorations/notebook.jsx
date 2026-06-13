// NOTEBOOK — modern editorial / field journal
// Warm bone, deep forest, single rust accent, kraft hairlines.
// DM Serif Display + Spectral + JetBrains Mono.

const NB = {
  bone: "#ece7d8",
  boneDeep: "#dcd4be",
  paper: "#f5f0e0",
  forest: "#2a3a2a",
  forestDeep: "#1b271c",
  rust: "#a14a2a",
  rustDeep: "#7e3a21",
  kraft: "#b9a37a",
  ink: "#1a1f1a",
};

const NB_DISPLAY = '"DM Serif Display", Georgia, serif';
const NB_BODY = '"Spectral", Georgia, serif';
const NB_MONO = '"JetBrains Mono", ui-monospace, monospace';

const NBLabel = ({ children, color = NB.rust }) => (
  <div style={{
    fontFamily: NB_MONO,
    fontSize: 11,
    letterSpacing: "0.22em",
    textTransform: "uppercase",
    color,
    fontWeight: 500,
  }}>{children}</div>
);

const NBNav = ({ active = "Home" }) => {
  const links = ["Home", "Ontology", "Visualization", "Download", "About", "Contact"];
  return (
    <div style={{
      background: NB.bone,
      borderBottom: `1px solid ${NB.kraft}66`,
    }}>
      <div style={{
        maxWidth: 1180,
        margin: "0 auto",
        padding: "22px 48px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 36, height: 36, background: NB.forest, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", color: NB.bone, fontFamily: NB_DISPLAY, fontSize: 22, fontStyle: "italic" }}>P</div>
          <div>
            <div style={{ fontFamily: NB_DISPLAY, fontSize: 22, color: NB.forest, lineHeight: 1 }}>POPPy</div>
            <div style={{ fontFamily: NB_MONO, fontSize: 9, letterSpacing: "0.16em", textTransform: "uppercase", color: NB.kraft, marginTop: 4 }}>Ledger · Vol. I, 2026</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 28 }}>
          {links.map(l => (
            <div key={l} style={{
              fontFamily: NB_MONO,
              fontSize: 12,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: l === active ? NB.rust : NB.forest,
              fontWeight: 500,
              borderBottom: l === active ? `2px solid ${NB.rust}` : "2px solid transparent",
              paddingBottom: 6,
            }}>{l}</div>
          ))}
        </div>
      </div>
    </div>
  );
};

const NBFooter = () => (
  <div style={{ background: NB.forestDeep, color: NB.bone, padding: "56px 48px 28px" }}>
    <div style={{ maxWidth: 1180, margin: "0 auto" }}>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 48, paddingBottom: 36 }}>
        <div>
          <div style={{ fontFamily: NB_DISPLAY, fontSize: 38, color: NB.bone }}>POPPy</div>
          <div style={{ fontFamily: NB_MONO, fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase", opacity: 0.55, marginTop: 8 }}>
            Phyto-Ontology Platform for Pharmacology
          </div>
          <p style={{ fontFamily: NB_BODY, fontSize: 15, lineHeight: 1.6, opacity: 0.75, marginTop: 18, maxWidth: 330 }}>
            An open registry of medicinal plants, their compounds, targets, and citations.
          </p>
        </div>
        {[
          { h: "Explore", items: ["Ontology", "Visualization", "Download"] },
          { h: "About", items: ["Mission", "Team", "Method"] },
          { h: "Legal", items: ["Privacy", "Terms", "License"] },
        ].map((col, i) => (
          <div key={i}>
            <NBLabel color={NB.kraft}>{col.h}</NBLabel>
            <div style={{ marginTop: 12 }}>
              {col.items.map(it => (
                <div key={it} style={{ fontFamily: NB_BODY, fontSize: 15, padding: "5px 0", opacity: 0.85 }}>{it}</div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div style={{ borderTop: `1px solid ${NB.bone}22`, paddingTop: 18, display: "flex", justifyContent: "space-between", fontFamily: NB_MONO, fontSize: 10, letterSpacing: "0.16em", textTransform: "uppercase", opacity: 0.55 }}>
        <span>© 2026 · Oresta S.I. Hewryk</span>
        <span>Vol. I · v 0.1.0</span>
      </div>
    </div>
  </div>
);

const NBButton = ({ children, variant = "filled", style = {} }) => (
  <button style={{
    fontFamily: NB_MONO,
    fontSize: 12,
    letterSpacing: "0.18em",
    textTransform: "uppercase",
    fontWeight: 500,
    padding: "16px 28px",
    borderRadius: 999,
    border: `1.5px solid ${variant === "filled" ? NB.rust : NB.forest}`,
    background: variant === "filled" ? NB.rust : "transparent",
    color: variant === "filled" ? NB.bone : NB.forest,
    cursor: "pointer",
    ...style,
  }}>{children}</button>
);

// ============ HOME ============
const NotebookHome = () => (
  <div style={{ background: NB.bone, color: NB.ink, fontFamily: NB_BODY, width: 1280 }}>
    <NBNav active="Home" />

    {/* HERO — editorial split */}
    <section style={{ padding: "60px 48px 40px" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 56, alignItems: "start" }}>
        <div>
          <NBLabel>Issue No. 01 · Anno 2026</NBLabel>
          <h1 style={{
            fontFamily: NB_DISPLAY,
            fontSize: 76,
            lineHeight: 1.0,
            margin: "20px 0 24px",
            color: NB.forest,
            letterSpacing: "-0.01em",
          }}>
            The phytochemical ontology, <span style={{ color: NB.rust, fontStyle: "italic" }}>indexed</span>.
          </h1>
          <p style={{ fontFamily: NB_BODY, fontSize: 21, lineHeight: 1.55, color: NB.ink, maxWidth: 520, marginBottom: 36 }}>
            POPPy is the first structured ontology of phytochemicals, built so machine-learning models can reason over four millennia of medicinal plant knowledge — without losing the citation trail.
          </p>
          <div style={{ display: "flex", gap: 12, marginBottom: 30 }}>
            <NBButton>Explore the graph</NBButton>
            <NBButton variant="outline">Read the paper</NBButton>
          </div>

          {/* Search bar */}
          <div style={{ background: NB.paper, border: `1.5px solid ${NB.forest}`, borderRadius: 999, display: "flex", alignItems: "center", padding: 6, marginTop: 24, maxWidth: 540 }}>
            <div style={{ flex: 1, padding: "10px 22px", fontFamily: NB_MONO, fontSize: 13, color: NB.ink + "88" }}>
              Search plant, compound, target…
            </div>
            <div style={{ background: NB.forest, color: NB.bone, borderRadius: 999, padding: "10px 22px", fontFamily: NB_MONO, fontSize: 12, letterSpacing: "0.18em", textTransform: "uppercase", fontWeight: 500 }}>Go →</div>
          </div>
        </div>

        {/* Field plate */}
        <div>
          <div style={{ background: NB.paper, border: `1px solid ${NB.kraft}88`, padding: 16 }}>
            <PlatePlaceholder
              caption="FIELD PLATE · No. 01"
              binomial="Papaver somniferum"
              height={420}
              color={NB.forest}
              bg={NB.paper}
            />
            <div style={{ borderTop: `1px solid ${NB.kraft}88`, marginTop: 12, paddingTop: 12, display: "flex", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontFamily: NB_DISPLAY, fontSize: 18, color: NB.forest, fontStyle: "italic" }}>Papaver somniferum</div>
                <div style={{ fontFamily: NB_MONO, fontSize: 10, letterSpacing: "0.16em", textTransform: "uppercase", color: NB.kraft, marginTop: 2 }}>Opium poppy · Papaveraceae</div>
              </div>
              <div style={{ fontFamily: NB_MONO, fontSize: 10, letterSpacing: "0.16em", textTransform: "uppercase", color: NB.rust, alignSelf: "end" }}>412 compounds →</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    {/* STATS — journal table */}
    <section style={{ padding: "60px 48px", background: NB.paper, borderTop: `1px solid ${NB.kraft}66`, borderBottom: `1px solid ${NB.kraft}66`, marginTop: 40 }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 24, borderBottom: `2px solid ${NB.forest}`, paddingBottom: 14 }}>
          <NBLabel>Table I · The collection</NBLabel>
          <NBLabel color={NB.kraft}>As of 21 May 2026</NBLabel>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 0 }}>
          {[
            { n: "63,722", l: "Plants", s: "medicinal taxa" },
            { n: "70,062", l: "Compounds", s: "phytochemicals" },
            { n: "1,334", l: "Targets", s: "proteins & mechanisms" },
            { n: "184k+", l: "Citations", s: "peer-reviewed sources" },
          ].map((s, i, arr) => (
            <div key={i} style={{ padding: "10px 28px", borderRight: i < arr.length - 1 ? `1px solid ${NB.kraft}66` : "none" }}>
              <div style={{ fontFamily: NB_DISPLAY, fontSize: 64, color: NB.forest, lineHeight: 1 }}>{s.n}</div>
              <div style={{ fontFamily: NB_DISPLAY, fontSize: 22, fontStyle: "italic", color: NB.rust, marginTop: 6 }}>{s.l}</div>
              <div style={{ fontFamily: NB_MONO, fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: NB.kraft, marginTop: 4 }}>{s.s}</div>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* WHAT'S INSIDE — kraft cards */}
    <section style={{ padding: "80px 48px 60px" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 36 }}>
          <div>
            <NBLabel>What's inside · II</NBLabel>
            <h2 style={{ fontFamily: NB_DISPLAY, fontSize: 48, color: NB.forest, marginTop: 10, marginBottom: 0 }}>
              Five layers, one graph.
            </h2>
          </div>
          <div style={{ fontFamily: NB_BODY, fontStyle: "italic", fontSize: 17, color: NB.ink, opacity: 0.7, maxWidth: 360, textAlign: "right" }}>
            Every node carries its provenance. Every edge carries its citation.
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20 }}>
          {[
            { n: "01", t: "Plants", b: "Curated medicinal taxa with canonical identifiers and ethnobotanical provenance.", c: NB.forest },
            { n: "02", t: "Compounds", b: "Structure-resolved phytochemicals linked back to the plants that contain them.", c: NB.forest },
            { n: "03", t: "Targets", b: "Proteins and mechanisms the compounds are known to engage.", c: NB.rust },
            { n: "04", t: "Effects", b: "Therapeutic effects, indications, and observed phenotypes.", c: NB.rust },
            { n: "05", t: "Evidence", b: "Peer-reviewed sources backing every relationship in the graph.", c: NB.kraft },
          ].map((c, i) => (
            <div key={c.n} style={{
              background: NB.paper,
              border: `1px solid ${NB.kraft}88`,
              padding: "28px 28px 32px",
              position: "relative",
              gridColumn: i >= 3 ? "span 1" : undefined,
            }}>
              <div style={{ position: "absolute", top: 0, left: 0, width: 6, height: "100%", background: c.c }}></div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <NBLabel color={c.c}>No. {c.n}</NBLabel>
              </div>
              <h3 style={{ fontFamily: NB_DISPLAY, fontSize: 32, color: NB.forest, margin: "12px 0 10px" }}>{c.t}</h3>
              <p style={{ fontFamily: NB_BODY, fontSize: 16, lineHeight: 1.55, color: NB.ink, opacity: 0.85, margin: 0 }}>{c.b}</p>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* PULL QUOTE / RELATIONSHIPS */}
    <section style={{ padding: "60px 48px", background: NB.forest, color: NB.bone }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 64, alignItems: "center" }}>
        <div>
          <NBLabel color={NB.kraft}>Figure III · Schema</NBLabel>
          <h2 style={{ fontFamily: NB_DISPLAY, fontSize: 44, lineHeight: 1.1, marginTop: 14, marginBottom: 18 }}>
            "Plant → has compound → target → effect"
          </h2>
          <p style={{ fontFamily: NB_BODY, fontSize: 17, lineHeight: 1.6, opacity: 0.85, marginBottom: 20 }}>
            POPPy represents entities as typed nodes and relates them with typed edges. Common traversals connect a medicinal plant, through one of its phytochemicals, to the human protein the compound engages, to the therapeutic effect that follows.
          </p>
          <div style={{ fontFamily: NB_MONO, fontSize: 13, lineHeight: 2, opacity: 0.85 }}>
            <div>Plant <span style={{ color: NB.kraft }}>—hasCompound→</span> Compound</div>
            <div>Compound <span style={{ color: NB.kraft }}>—targets→</span> Protein</div>
            <div>Protein <span style={{ color: NB.kraft }}>—associatedWith→</span> Effect</div>
            <div>Entity <span style={{ color: NB.kraft }}>—supportedBy→</span> Citation</div>
          </div>
        </div>
        <div style={{ background: NB.forestDeep, border: `1px solid ${NB.kraft}55`, padding: 32 }}>
          <GraphSketch height={320} edgeColor={NB.bone + "55"} />
        </div>
      </div>
    </section>

    {/* CITE */}
    <section style={{ padding: "80px 48px" }}>
      <div style={{ maxWidth: 900, margin: "0 auto", textAlign: "center" }}>
        <NBLabel>Open access · CC-BY 4.0</NBLabel>
        <h2 style={{ fontFamily: NB_DISPLAY, fontSize: 56, color: NB.forest, marginTop: 18, marginBottom: 20, lineHeight: 1.05 }}>
          Cite us. <span style={{ fontStyle: "italic", color: NB.rust }}>Fork us.</span> Build on us.
        </h2>
        <p style={{ fontFamily: NB_BODY, fontSize: 19, color: NB.ink, opacity: 0.85, lineHeight: 1.55, maxWidth: 620, margin: "0 auto 32px" }}>
          The full ontology, in three serializations, with documentation, BibTeX, and a live SPARQL endpoint.
        </p>
        <div style={{ display: "flex", gap: 14, justifyContent: "center" }}>
          <NBButton>Download ontology</NBButton>
          <NBButton variant="outline">Citation (BibTeX)</NBButton>
        </div>
      </div>
    </section>

    <NBFooter />
  </div>
);

Object.assign(window, { NotebookHome, NBNav, NBFooter, NBButton, NBLabel, NB, NB_DISPLAY, NB_BODY, NB_MONO });
