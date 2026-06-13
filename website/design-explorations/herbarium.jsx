// HERBARIUM — apothecary book / pharmacopoeia
// Cream parchment, deep forest, hairlines and Latin binomials.

const HERB = {
  parchment: "#f3e9cd",
  parchmentDeep: "#ead9b0",
  ink: "#1a1f17",
  forest: "#243025",
  forestDeep: "#19211b",
  accent: "#3d5b3e",
  umber: "#7a5a3a",
  rule: "#8a7a4a",
  ruleSoft: "#bca97a",
};

const HERB_FONT_DISPLAY = '"EB Garamond", "Cardo", Georgia, serif';
const HERB_FONT_MONO = '"IBM Plex Mono", ui-monospace, monospace';

// Decorative hairline with center asterism
const HerbDivider = ({ glyph = "❦", color = HERB.rule }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 14, color, margin: "32px 0" }}>
    <div style={{ flex: 1, height: 1, background: color, opacity: 0.5 }}></div>
    <div style={{ flex: 1, height: 3, borderTop: `1px solid ${color}`, borderBottom: `1px solid ${color}`, opacity: 0.5 }}></div>
    <span style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 22, opacity: 0.7 }}>{glyph}</span>
    <div style={{ flex: 1, height: 3, borderTop: `1px solid ${color}`, borderBottom: `1px solid ${color}`, opacity: 0.5 }}></div>
    <div style={{ flex: 1, height: 1, background: color, opacity: 0.5 }}></div>
  </div>
);

const HerbNav = ({ active = "Home" }) => {
  const links = ["Home", "Ontology", "Visualization", "Download", "About", "Contact"];
  return (
    <div style={{
      borderTop: `3px double ${HERB.rule}`,
      borderBottom: `1px solid ${HERB.rule}66`,
      background: HERB.parchment,
      color: HERB.ink,
    }}>
      <div style={{
        maxWidth: 1180,
        margin: "0 auto",
        padding: "20px 48px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <div style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 36, fontWeight: 500, letterSpacing: "0.01em" }}>
            POPP<span style={{ fontStyle: "italic" }}>y</span>
          </div>
          <div style={{ fontFamily: HERB_FONT_MONO, fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", opacity: 0.6, paddingBottom: 4 }}>
            Pharmacopoeia<br/>Ontologica
          </div>
        </div>
        <div style={{ display: "flex", gap: 28, alignItems: "center" }}>
          {links.map(l => (
            <div
              key={l}
              style={{
                fontFamily: HERB_FONT_DISPLAY,
                fontVariantCaps: "all-small-caps",
                letterSpacing: "0.14em",
                fontSize: 16,
                color: l === active ? HERB.accent : HERB.ink,
                borderBottom: l === active ? `2px solid ${HERB.accent}` : "none",
                paddingBottom: 2,
              }}
            >
              {l}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const HerbFooter = () => (
  <div style={{
    background: HERB.forestDeep,
    color: HERB.parchment,
    padding: "56px 48px 28px",
    marginTop: 64,
  }}>
    <div style={{ maxWidth: 1180, margin: "0 auto" }}>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 48, paddingBottom: 36 }}>
        <div>
          <div style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 32, fontStyle: "italic" }}>POPPy</div>
          <div style={{ fontFamily: HERB_FONT_MONO, fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase", opacity: 0.6, marginTop: 8 }}>
            Phyto-Ontology Platform<br/>for Pharmacology
          </div>
          <p style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 15, lineHeight: 1.55, opacity: 0.75, marginTop: 18, maxWidth: 320 }}>
            An open registry of medicinal plants, their compounds, targets, and citations — for the next generation of AI-assisted drug discovery.
          </p>
        </div>
        {[
          { h: "Explore", items: ["Ontology", "Visualization", "Download", "API"] },
          { h: "About", items: ["Mission", "Team", "Method", "Citation"] },
          { h: "Legal", items: ["Privacy", "Terms", "License"] },
        ].map((col, i) => (
          <div key={i}>
            <div className="mono-caption" style={{ opacity: 0.55, marginBottom: 14 }}>{col.h}</div>
            {col.items.map(it => (
              <div key={it} style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 16, padding: "4px 0", opacity: 0.85 }}>{it}</div>
            ))}
          </div>
        ))}
      </div>
      <div style={{ borderTop: `1px solid ${HERB.parchment}33`, paddingTop: 18, display: "flex", justifyContent: "space-between", fontFamily: HERB_FONT_MONO, fontSize: 10, letterSpacing: "0.16em", textTransform: "uppercase", opacity: 0.55 }}>
        <span>© MMXXV · Oresta S.I. Hewryk</span>
        <span>Editio Prima · v 0.1</span>
      </div>
    </div>
  </div>
);

const HerbButton = ({ children, variant = "filled", style = {} }) => (
  <button style={{
    fontFamily: HERB_FONT_DISPLAY,
    fontSize: 16,
    fontVariantCaps: "all-small-caps",
    letterSpacing: "0.18em",
    padding: "14px 32px",
    borderRadius: 0,
    border: `1px solid ${HERB.forest}`,
    background: variant === "filled" ? HERB.forest : "transparent",
    color: variant === "filled" ? HERB.parchment : HERB.forest,
    cursor: "pointer",
    ...style,
  }}>{children}</button>
);

// ============ HOME ============
const HerbariumHome = () => (
  <div style={{ background: HERB.parchment, color: HERB.ink, fontFamily: HERB_FONT_DISPLAY, width: 1280 }}>
    <HerbNav active="Home" />

    {/* HERO */}
    <section style={{ padding: "80px 48px 40px", textAlign: "center" }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <div className="mono-caption" style={{ color: HERB.umber, marginBottom: 24 }}>
          Anno Domini MMXXV · Editio Prima · Open Access
        </div>
        <h1 style={{
          fontFamily: HERB_FONT_DISPLAY,
          fontWeight: 500,
          fontSize: 72,
          lineHeight: 1.05,
          letterSpacing: "-0.015em",
          margin: 0,
          color: HERB.forest,
        }}>
          The first structured <span style={{ fontStyle: "italic" }}>phytochemicals</span> ontology, for AI-based drug discovery.
        </h1>
        <p style={{
          fontFamily: HERB_FONT_DISPLAY,
          fontStyle: "italic",
          fontSize: 22,
          color: HERB.umber,
          marginTop: 28,
          lineHeight: 1.4,
        }}>
          Bridging four millennia of materia medica with modern computational pharmacology — a registry of plants, compounds, targets, and citations.
        </p>
        <HerbDivider />
      </div>

      {/* SEARCH */}
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <div style={{
          background: "#fdf8e9",
          border: `1px solid ${HERB.rule}`,
          padding: "6px",
          display: "flex",
          alignItems: "stretch",
        }}>
          <div style={{
            flex: 1,
            padding: "16px 20px",
            fontFamily: HERB_FONT_MONO,
            fontSize: 14,
            color: HERB.ink + "88",
            display: "flex",
            alignItems: "center",
          }}>
            <span style={{ color: HERB.accent, marginRight: 10 }}>⌕</span>
            Search plant, compound, target, or citation…
          </div>
          <HerbButton style={{ borderRadius: 0 }}>Inquire</HerbButton>
        </div>
        <div style={{ marginTop: 14, display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          <span className="mono-caption" style={{ opacity: 0.6 }}>Try:</span>
          {["Papaver somniferum", "Curcuma longa", "Salvia officinalis", "Withania somnifera"].map(b => (
            <span key={b} style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 15, color: HERB.accent, borderBottom: `1px dotted ${HERB.accent}`, paddingBottom: 1 }}>{b}</span>
          ))}
        </div>
      </div>
    </section>

    {/* STATS — Folia Statistica */}
    <section style={{ padding: "60px 48px", borderTop: `1px solid ${HERB.rule}55`, borderBottom: `1px solid ${HERB.rule}55`, marginTop: 40 }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <SectionLabel color={HERB.umber}>Folia Statistica · I</SectionLabel>
          <h2 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 36, fontWeight: 500, marginTop: 8, color: HERB.forest }}>
            The collection, by the numbers
          </h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 0 }}>
          {[
            { n: "63,722", lat: "Plantae", en: "medicinal plants & taxa" },
            { n: "70,062", lat: "Composita", en: "phytochemical compounds" },
            { n: "1,334", lat: "Obiectiva", en: "protein targets" },
          ].map((s, i) => (
            <div key={i} style={{
              textAlign: "center",
              padding: "20px 30px",
              borderLeft: i === 0 ? "none" : `1px solid ${HERB.rule}55`,
            }}>
              <div style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 80, fontWeight: 500, color: HERB.forest, lineHeight: 1, letterSpacing: "-0.01em" }}>
                {s.n}
              </div>
              <div style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 22, color: HERB.umber, marginTop: 10 }}>
                {s.lat}
              </div>
              <div className="mono-caption" style={{ opacity: 0.6, marginTop: 6 }}>{s.en}</div>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* WHAT'S INSIDE — printed register */}
    <section style={{ padding: "80px 48px 60px" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <SectionLabel color={HERB.umber}>Index Rerum · II</SectionLabel>
          <h2 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 36, fontWeight: 500, marginTop: 8, color: HERB.forest }}>
            What lies within
          </h2>
        </div>
        <div style={{ background: "#fdf8e9", border: `1px solid ${HERB.rule}55`, padding: "32px 48px" }}>
          {[
            { roman: "I.", name: "Plants", lat: "Plantae", desc: "Curated medicinal taxa with canonical identifiers and ethnobotanical provenance.", n: "63,722" },
            { roman: "II.", name: "Compounds", lat: "Composita", desc: "Structure-resolved phytochemicals linked to their botanical sources.", n: "70,062" },
            { roman: "III.", name: "Targets", lat: "Obiectiva", desc: "Proteins and biological mechanisms associated with each compound.", n: "1,334" },
            { roman: "IV.", name: "Effects", lat: "Effectus", desc: "Therapeutic effects, indications, and observed phenotypes.", n: "2,418" },
            { roman: "V.", name: "Evidence", lat: "Testimonia", desc: "Peer-reviewed citations and provenance trail for every relationship.", n: "184,500+" },
          ].map((row, i, arr) => (
            <div key={row.roman} style={{
              display: "grid",
              gridTemplateColumns: "60px 200px 1fr 120px",
              alignItems: "baseline",
              padding: "18px 0",
              borderBottom: i < arr.length - 1 ? `1px dotted ${HERB.rule}` : "none",
              gap: 28,
            }}>
              <div style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 24, color: HERB.umber }}>{row.roman}</div>
              <div>
                <div style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 24, fontWeight: 600, color: HERB.forest }}>{row.name}</div>
                <div style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 14, color: HERB.umber, marginTop: 2 }}>{row.lat}</div>
              </div>
              <div style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 17, lineHeight: 1.5, color: HERB.ink, opacity: 0.85 }}>
                {row.desc}
              </div>
              <div style={{ fontFamily: HERB_FONT_MONO, fontSize: 14, color: HERB.accent, textAlign: "right" }}>{row.n}</div>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* CORE RELATIONSHIPS — schema printed like a book figure */}
    <section style={{ padding: "60px 48px", background: HERB.parchmentDeep + "55" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <SectionLabel color={HERB.umber}>Schema Relationum · III</SectionLabel>
          <h2 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 36, fontWeight: 500, marginTop: 8, color: HERB.forest }}>
            Figure: how entities relate
          </h2>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 56, alignItems: "center" }}>
          <div style={{ background: "#fdf8e9", border: `1px solid ${HERB.rule}55`, padding: "32px" }}>
            <GraphSketch height={300} nodeColor={HERB.accent} edgeColor={HERB.ink + "55"} />
            <div className="mono-caption" style={{ opacity: 0.55, textAlign: "center", marginTop: 14 }}>
              Fig. III — typed relationships, by example
            </div>
          </div>
          <div>
            {[
              { l: "Plantum", r: "Compositum", verb: "hasCompound" },
              { l: "Compositum", r: "Obiectivum", verb: "targets" },
              { l: "Obiectivum", r: "Effectum", verb: "associatedWith" },
              { l: "Entitas", r: "Testimonium", verb: "supportedBy" },
            ].map((row, i) => (
              <div key={i} style={{ padding: "14px 0", borderBottom: `1px dotted ${HERB.rule}55`, display: "flex", alignItems: "baseline", gap: 14, fontFamily: HERB_FONT_DISPLAY, fontSize: 19 }}>
                <span style={{ color: HERB.forest, fontWeight: 600 }}>{row.l}</span>
                <span style={{ fontFamily: HERB_FONT_MONO, fontSize: 12, color: HERB.umber, letterSpacing: "0.08em" }}>—{row.verb}→</span>
                <span style={{ color: HERB.forest, fontWeight: 600 }}>{row.r}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>

    {/* PLATES — botanical illustrations */}
    <section style={{ padding: "80px 48px 60px" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <SectionLabel color={HERB.umber}>Tabulae · IV</SectionLabel>
          <h2 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 36, fontWeight: 500, marginTop: 8, color: HERB.forest }}>
            Featured species
          </h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 24 }}>
          {[
            { plate: "Plate I", lat: "Papaver somniferum", common: "Opium poppy", n: "412 compounds" },
            { plate: "Plate II", lat: "Curcuma longa", common: "Turmeric", n: "289 compounds" },
            { plate: "Plate III", lat: "Salvia officinalis", common: "Common sage", n: "176 compounds" },
            { plate: "Plate IV", lat: "Withania somnifera", common: "Ashwagandha", n: "203 compounds" },
          ].map((p, i) => (
            <div key={i}>
              <PlatePlaceholder
                caption={p.plate}
                binomial={p.lat}
                height={240}
                color={HERB.forest}
                bg="#fdf8e9"
              />
              <div style={{ marginTop: 14, textAlign: "center" }}>
                <div style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 18, color: HERB.forest }}>{p.lat}</div>
                <div className="mono-caption" style={{ opacity: 0.55, marginTop: 4 }}>{p.common} · {p.n}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* CITE / DOWNLOAD */}
    <section style={{ padding: "60px 48px 100px" }}>
      <div style={{ maxWidth: 920, margin: "0 auto", background: HERB.forest, color: HERB.parchment, padding: "56px 64px", textAlign: "center" }}>
        <SectionLabel color={HERB.parchment + "aa"}>Cite · Download · Reuse</SectionLabel>
        <h2 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 40, fontWeight: 500, marginTop: 10, marginBottom: 18, fontStyle: "italic" }}>
          Open access, freely reproducible
        </h2>
        <p style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 18, lineHeight: 1.55, opacity: 0.85, maxWidth: 560, margin: "0 auto 32px" }}>
          POPPy is released under CC-BY 4.0. Download OWL/Turtle/RDF exports, or pull entities directly from the SPARQL endpoint.
        </p>
        <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
          <HerbButton style={{ background: HERB.parchment, color: HERB.forest, borderColor: HERB.parchment }}>Download OWL</HerbButton>
          <HerbButton style={{ background: "transparent", color: HERB.parchment, borderColor: HERB.parchment }}>Read paper</HerbButton>
        </div>
      </div>
    </section>

    <HerbFooter />
  </div>
);

// ============ ABOUT ============
const HerbariumAbout = () => (
  <div style={{ background: HERB.parchment, color: HERB.ink, fontFamily: HERB_FONT_DISPLAY, width: 1280 }}>
    <HerbNav active="About" />

    <section style={{ padding: "80px 48px 40px", textAlign: "center" }}>
      <SectionLabel color={HERB.umber}>De Nobis · About</SectionLabel>
      <h1 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 64, fontWeight: 500, color: HERB.forest, margin: "16px 0 24px", lineHeight: 1.05 }}>
        Reuniting the <span style={{ fontStyle: "italic" }}>materia medica</span> with the molecule.
      </h1>
      <p style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 22, color: HERB.umber, maxWidth: 760, margin: "0 auto", lineHeight: 1.4 }}>
        For most of human history, medicine was made from plants. POPPy is a quiet attempt to render that knowledge legible to machines.
      </p>
      <HerbDivider />
    </section>

    <section style={{ padding: "20px 48px 60px" }}>
      <div style={{ maxWidth: 920, margin: "0 auto", display: "grid", gridTemplateColumns: "260px 1fr", gap: 56 }}>
        <SectionLabel color={HERB.umber}>The Mission</SectionLabel>
        <div style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 21, lineHeight: 1.6, color: HERB.ink }}>
          <p style={{ marginTop: 0 }}>
            POPPy — the <em>Phyto-Ontology Platform for Pharmacology</em> — is the first structured ontology of phytochemicals built for AI-based drug discovery. We catalogue medicinal plants, the compounds they contain, the human targets those compounds engage, and the therapeutic effects they produce — each relationship traceable to the peer-reviewed literature that established it.
          </p>
          <p>
            The goal is simple: make four millennia of accumulated botanical pharmacology queryable by a graph, a SPARQL endpoint, or a language model — without losing the citation trail along the way.
          </p>
        </div>
      </div>
    </section>

    <section style={{ padding: "60px 48px", borderTop: `1px solid ${HERB.rule}55`, borderBottom: `1px solid ${HERB.rule}55` }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 50 }}>
          <SectionLabel color={HERB.umber}>Methodus</SectionLabel>
          <h2 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 36, fontWeight: 500, color: HERB.forest, marginTop: 8 }}>
            How POPPy is built
          </h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 28 }}>
          {[
            { n: "i", t: "Curate", b: "Plant taxa are reconciled against canonical sources (Kew, GBIF). Each entry carries its original ethnobotanical reference." },
            { n: "ii", t: "Resolve", b: "Compounds are mapped to InChI/SMILES via PubChem and ChEBI. Duplicates are merged; structures are sanitized." },
            { n: "iii", t: "Annotate", b: "Targets and effects are linked through the peer-reviewed literature, with every claim retaining its primary citation." },
          ].map(c => (
            <div key={c.n} style={{ background: "#fdf8e9", border: `1px solid ${HERB.rule}55`, padding: "28px 32px" }}>
              <div style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 48, color: HERB.umber, lineHeight: 1 }}>{c.n}.</div>
              <h3 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 24, color: HERB.forest, marginTop: 12, marginBottom: 8 }}>{c.t}</h3>
              <p style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 16, lineHeight: 1.55, opacity: 0.85 }}>{c.b}</p>
            </div>
          ))}
        </div>
      </div>
    </section>

    <section style={{ padding: "80px 48px 60px" }}>
      <div style={{ maxWidth: 920, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <SectionLabel color={HERB.umber}>Auctores · Authors</SectionLabel>
          <h2 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 36, fontWeight: 500, color: HERB.forest, marginTop: 8 }}>The people behind it</h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {[
            { name: "Oresta S.I. Hewryk", role: "Principal investigator · Lead curator", inst: "Institution placeholder" },
            { name: "Co-author placeholder", role: "Ontology engineering", inst: "Institution placeholder" },
            { name: "Co-author placeholder", role: "Cheminformatics", inst: "Institution placeholder" },
            { name: "Co-author placeholder", role: "Ethnobotanical review", inst: "Institution placeholder" },
          ].map((p, i) => (
            <div key={i} style={{ display: "flex", gap: 20, alignItems: "center", padding: "20px 0", borderBottom: `1px dotted ${HERB.rule}` }}>
              <div style={{ width: 72, height: 72, borderRadius: "50%", background: HERB.parchmentDeep, border: `1px solid ${HERB.rule}`, fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 28, color: HERB.umber, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {p.name.split(" ").map(w => w[0]).slice(0, 2).join("")}
              </div>
              <div>
                <div style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 20, color: HERB.forest, fontWeight: 600 }}>{p.name}</div>
                <div style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 15, color: HERB.umber, marginTop: 2 }}>{p.role}</div>
                <div className="mono-caption" style={{ opacity: 0.55, marginTop: 4 }}>{p.inst}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>

    <HerbFooter />
  </div>
);

// ============ DOWNLOAD ============
const HerbariumDownload = () => (
  <div style={{ background: HERB.parchment, color: HERB.ink, fontFamily: HERB_FONT_DISPLAY, width: 1280 }}>
    <HerbNav active="Download" />

    <section style={{ padding: "80px 48px 40px", textAlign: "center" }}>
      <SectionLabel color={HERB.umber}>Editio · Download</SectionLabel>
      <h1 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 64, fontWeight: 500, color: HERB.forest, margin: "16px 0 24px", lineHeight: 1.05 }}>
        Take a <span style={{ fontStyle: "italic" }}>printing</span> of the ontology.
      </h1>
      <p style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 21, color: HERB.umber, maxWidth: 700, margin: "0 auto", lineHeight: 1.4 }}>
        Released open under CC-BY 4.0. Pick the serialization that suits your tools.
      </p>
      <HerbDivider />
    </section>

    {/* Big download card */}
    <section style={{ padding: "20px 48px 60px" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto" }}>
        <div style={{ background: "#fdf8e9", border: `1px solid ${HERB.rule}55`, padding: "40px 48px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: `2px solid ${HERB.rule}`, paddingBottom: 16, marginBottom: 24 }}>
            <div>
              <div className="mono-caption" style={{ opacity: 0.55 }}>Editio Prima</div>
              <div style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 32, color: HERB.forest, marginTop: 4 }}>POPPy ontology · v 0.1.0</div>
            </div>
            <div className="mono-caption" style={{ opacity: 0.7 }}>Released 21 May 2026</div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 0 }}>
            {[
              { fmt: "OWL", file: "poppy.owl", size: "48.2 MB", desc: "RDF/XML serialization, for Protégé and OWL API tooling." },
              { fmt: "TTL", file: "poppy.ttl", size: "31.5 MB", desc: "Turtle — concise, human-readable triple syntax." },
              { fmt: "RDF", file: "poppy.rdf", size: "52.8 MB", desc: "Plain RDF/XML for graph databases and SPARQL stores." },
            ].map((f, i) => (
              <div key={f.fmt} style={{
                padding: "20px 24px",
                borderLeft: i === 0 ? "none" : `1px dotted ${HERB.rule}`,
              }}>
                <div style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 36, color: HERB.forest, fontStyle: "italic" }}>{f.fmt}</div>
                <div style={{ fontFamily: HERB_FONT_MONO, fontSize: 13, color: HERB.accent, marginTop: 6 }}>{f.file}</div>
                <div className="mono-caption" style={{ opacity: 0.55, marginTop: 4 }}>{f.size}</div>
                <p style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 15, lineHeight: 1.5, opacity: 0.85, marginTop: 12, marginBottom: 18 }}>{f.desc}</p>
                <HerbButton style={{ padding: "10px 22px", fontSize: 14 }}>Download</HerbButton>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>

    {/* Companion materials */}
    <section style={{ padding: "20px 48px 60px" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <SectionLabel color={HERB.umber}>Adjuncta · Companions</SectionLabel>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {[
            { title: "Documentation", file: "poppy-docs.pdf", desc: "Schema overview, provenance notes, and usage guidance." },
            { title: "Citation", file: "citation.txt", desc: "BibTeX entry and recommended citation form." },
            { title: "Changelog", file: "CHANGELOG.md", desc: "Release notes and provenance for every version." },
            { title: "SPARQL endpoint", file: "/sparql", desc: "Query the live graph without downloading anything." },
          ].map((a, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "20px 24px", background: "#fdf8e9", border: `1px solid ${HERB.rule}55` }}>
              <div>
                <div style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 22, color: HERB.forest }}>{a.title}</div>
                <div style={{ fontFamily: HERB_FONT_MONO, fontSize: 12, color: HERB.accent, marginTop: 4 }}>{a.file}</div>
                <p style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 15, opacity: 0.8, marginTop: 8, marginBottom: 0 }}>{a.desc}</p>
              </div>
              <HerbButton variant="outline" style={{ padding: "8px 20px", fontSize: 13, whiteSpace: "nowrap" }}>Open</HerbButton>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* License */}
    <section style={{ padding: "20px 48px 80px" }}>
      <div style={{ maxWidth: 800, margin: "0 auto", textAlign: "center" }}>
        <Asterism color={HERB.umber} glyph="❦" />
        <p style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 20, color: HERB.umber, marginTop: 20, lineHeight: 1.5 }}>
          Released under Creative Commons Attribution 4.0. Cite us, fork us, build on us — only do not forget where the knowledge came from.
        </p>
      </div>
    </section>

    <HerbFooter />
  </div>
);

// ============ CONTACT ============
const HerbariumContact = () => (
  <div style={{ background: HERB.parchment, color: HERB.ink, fontFamily: HERB_FONT_DISPLAY, width: 1280 }}>
    <HerbNav active="Contact" />

    <section style={{ padding: "80px 48px 40px", textAlign: "center" }}>
      <SectionLabel color={HERB.umber}>Epistola · Contact</SectionLabel>
      <h1 style={{ fontFamily: HERB_FONT_DISPLAY, fontSize: 64, fontWeight: 500, color: HERB.forest, margin: "16px 0 24px", lineHeight: 1.05 }}>
        Write us a <span style={{ fontStyle: "italic" }}>letter</span>.
      </h1>
      <p style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 21, color: HERB.umber, maxWidth: 700, margin: "0 auto", lineHeight: 1.4 }}>
        Questions, collaborations, corrections, or a species we ought to have included.
      </p>
      <HerbDivider />
    </section>

    <section style={{ padding: "20px 48px 80px" }}>
      <div style={{ maxWidth: 1000, margin: "0 auto", display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 48 }}>
        {/* Form */}
        <div style={{ background: "#fdf8e9", border: `1px solid ${HERB.rule}55`, padding: "40px 44px" }}>
          {[
            { label: "Nomen · Name", placeholder: "Your name" },
            { label: "Electronica · Email", placeholder: "you@institution.org" },
            { label: "Institutio · Affiliation (optional)", placeholder: "University, lab, or independent" },
          ].map(field => (
            <div key={field.label} style={{ marginBottom: 22 }}>
              <div className="mono-caption" style={{ opacity: 0.7, marginBottom: 6 }}>{field.label}</div>
              <div style={{ borderBottom: `1px solid ${HERB.rule}`, paddingBottom: 8, fontFamily: HERB_FONT_DISPLAY, fontSize: 18, fontStyle: "italic", color: HERB.ink + "66" }}>
                {field.placeholder}
              </div>
            </div>
          ))}
          <div style={{ marginBottom: 28 }}>
            <div className="mono-caption" style={{ opacity: 0.7, marginBottom: 6 }}>Epistola · Message</div>
            <div style={{ borderBottom: `1px solid ${HERB.rule}`, paddingBottom: 8, fontFamily: HERB_FONT_DISPLAY, fontSize: 18, fontStyle: "italic", color: HERB.ink + "66", minHeight: 120 }}>
              Tell us what you're working on…
            </div>
          </div>
          <HerbButton>Send letter</HerbButton>
        </div>

        {/* Sidebar */}
        <div style={{ paddingTop: 12 }}>
          <SectionLabel color={HERB.umber}>Other ways to reach us</SectionLabel>
          <div style={{ marginTop: 20 }}>
            {[
              { k: "Mail", v: "hello@poppyontology.org" },
              { k: "GitHub", v: "github.com/poppy-ontology" },
              { k: "ORCID", v: "0000-0000-0000-0000" },
            ].map(c => (
              <div key={c.k} style={{ padding: "16px 0", borderBottom: `1px dotted ${HERB.rule}` }}>
                <div style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 15, color: HERB.umber }}>{c.k}</div>
                <div style={{ fontFamily: HERB_FONT_MONO, fontSize: 14, color: HERB.forest, marginTop: 4 }}>{c.v}</div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 36, padding: "24px 28px", background: HERB.forest, color: HERB.parchment }}>
            <div className="mono-caption" style={{ opacity: 0.7, marginBottom: 8 }}>Office Hours</div>
            <p style={{ fontFamily: HERB_FONT_DISPLAY, fontStyle: "italic", fontSize: 17, lineHeight: 1.5, margin: 0 }}>
              Open virtual office every Thursday, 16:00–17:00 UTC. For ontology questions, drop in — no appointment needed.
            </p>
          </div>
        </div>
      </div>
    </section>

    <HerbFooter />
  </div>
);

Object.assign(window, { HerbariumHome, HerbariumAbout, HerbariumDownload, HerbariumContact });
