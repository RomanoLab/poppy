// MODERN APOTHECARY — bold, confident, contemporary
// Big solid blocks of deep forest with cream knockout type.
// Cardo italic display + Public Sans body + Space Mono numerals.

const MA = {
  forest: "#1f3324",
  forestDeep: "#13201a",
  forestMid: "#2d4732",
  cream: "#f4ecd4",
  creamLight: "#faf3e0",
  sand: "#d8c498",
  ink: "#0d1410",
  accent: "#c89860",  // warm bronze accent, used sparingly
};

const MA_DISPLAY = '"Cardo", "EB Garamond", Georgia, serif';
const MA_BODY = '"Public Sans", system-ui, sans-serif';
const MA_MONO = '"Space Mono", ui-monospace, monospace';

const MALabel = ({ children, color = MA.sand, style = {} }) => (
  <div style={{
    fontFamily: MA_MONO,
    fontSize: 11,
    letterSpacing: "0.24em",
    textTransform: "uppercase",
    color,
    ...style,
  }}>{children}</div>
);

const MANav = ({ active = "Home" }) => {
  const links = ["Home", "Ontology", "Visualization", "Download", "About", "Contact"];
  return (
    <div style={{
      background: MA.forest,
      color: MA.cream,
    }}>
      <div style={{
        maxWidth: 1180,
        margin: "0 auto",
        padding: "24px 48px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <div style={{ fontFamily: MA_DISPLAY, fontSize: 30, fontStyle: "italic", color: MA.cream, lineHeight: 1 }}>POPPy</div>
          <div style={{ fontFamily: MA_MONO, fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase", color: MA.sand }}>/ phyto-ontology</div>
        </div>
        <div style={{ display: "flex", gap: 30 }}>
          {links.map(l => (
            <div key={l} style={{
              fontFamily: MA_BODY,
              fontSize: 13,
              fontWeight: l === active ? 600 : 400,
              letterSpacing: "0.06em",
              color: l === active ? MA.sand : MA.cream,
              borderBottom: l === active ? `1px solid ${MA.sand}` : "1px solid transparent",
              paddingBottom: 4,
            }}>{l}</div>
          ))}
        </div>
      </div>
    </div>
  );
};

const MAFooter = () => (
  <div style={{ background: MA.forestDeep, color: MA.cream, padding: "64px 48px 28px" }}>
    <div style={{ maxWidth: 1180, margin: "0 auto" }}>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 48, paddingBottom: 40 }}>
        <div>
          <div style={{ fontFamily: MA_DISPLAY, fontSize: 56, fontStyle: "italic", color: MA.cream, lineHeight: 1 }}>POPPy</div>
          <p style={{ fontFamily: MA_BODY, fontSize: 15, lineHeight: 1.6, color: MA.sand, marginTop: 20, maxWidth: 320 }}>
            The first structured phytochemicals ontology for AI-based drug discovery.
          </p>
        </div>
        {[
          { h: "Explore", items: ["Ontology", "Visualization", "Download", "SPARQL"] },
          { h: "About", items: ["Mission", "Team", "Method", "Citation"] },
          { h: "Legal", items: ["Privacy", "Terms", "License"] },
        ].map((col, i) => (
          <div key={i}>
            <MALabel>{col.h}</MALabel>
            <div style={{ marginTop: 14 }}>
              {col.items.map(it => (
                <div key={it} style={{ fontFamily: MA_BODY, fontSize: 14, padding: "5px 0" }}>{it}</div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div style={{ borderTop: `1px solid ${MA.cream}22`, paddingTop: 18, display: "flex", justifyContent: "space-between" }}>
        <MALabel style={{ opacity: 0.55 }}>© 2026 · Oresta S.I. Hewryk</MALabel>
        <MALabel style={{ opacity: 0.55 }}>v 0.1.0 · CC-BY 4.0</MALabel>
      </div>
    </div>
  </div>
);

const MAButton = ({ children, variant = "filled", style = {} }) => (
  <button style={{
    fontFamily: MA_BODY,
    fontSize: 14,
    fontWeight: 600,
    letterSpacing: "0.04em",
    padding: "16px 32px",
    borderRadius: 4,
    border: variant === "outline" ? `1.5px solid ${MA.cream}` : "1.5px solid transparent",
    background: variant === "outline" ? "transparent" : MA.cream,
    color: variant === "outline" ? MA.cream : MA.forest,
    cursor: "pointer",
    ...style,
  }}>{children}</button>
);

// ============ HOME ============
const ModernHome = () => (
  <div style={{ background: MA.cream, color: MA.ink, fontFamily: MA_BODY, width: 1280 }}>
    <MANav active="Home" />

    {/* HERO — solid forest block */}
    <section style={{ background: MA.forest, color: MA.cream, padding: "100px 48px 110px", position: "relative", overflow: "hidden" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", position: "relative" }}>
        <MALabel>Open phytochemical ontology · v 0.1 · 2026</MALabel>

        <h1 style={{
          fontFamily: MA_DISPLAY,
          fontSize: 124,
          lineHeight: 0.95,
          letterSpacing: "-0.02em",
          margin: "32px 0 32px",
          color: MA.cream,
          maxWidth: 1000,
        }}>
          The medicine cabinet,<br/>
          <span style={{ fontStyle: "italic", color: MA.sand }}>structured for machines.</span>
        </h1>

        <p style={{
          fontFamily: MA_BODY,
          fontSize: 22,
          lineHeight: 1.5,
          color: MA.cream,
          opacity: 0.85,
          maxWidth: 640,
          marginTop: 0,
          marginBottom: 40,
        }}>
          POPPy is the first structured ontology of phytochemicals — a queryable graph of plants, compounds, targets, and citations, built so AI can finally reason over the materia medica.
        </p>

        {/* Search */}
        <div style={{ background: MA.cream, borderRadius: 6, display: "flex", alignItems: "center", padding: 8, maxWidth: 640, marginBottom: 24 }}>
          <div style={{ flex: 1, padding: "12px 20px", fontFamily: MA_BODY, fontSize: 15, color: MA.ink + "88" }}>
            Search plant, compound, target, or citation…
          </div>
          <div style={{ background: MA.forest, color: MA.cream, borderRadius: 4, padding: "12px 26px", fontFamily: MA_BODY, fontSize: 14, fontWeight: 600 }}>Search</div>
        </div>

        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <MALabel>Try:</MALabel>
          {["Papaver somniferum", "Curcuma longa", "Salvia officinalis"].map(b => (
            <div key={b} style={{ fontFamily: MA_DISPLAY, fontStyle: "italic", fontSize: 17, color: MA.cream, borderBottom: `1px solid ${MA.sand}66`, paddingBottom: 1 }}>{b}</div>
          ))}
        </div>
      </div>
    </section>

    {/* STATS — cream block, big sans numerals */}
    <section style={{ padding: "80px 48px" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 0, alignItems: "stretch" }}>
          {[
            { n: "63,722", l: "Plants", s: "medicinal taxa" },
            { n: "70,062", l: "Compounds", s: "phytochemicals" },
            { n: "1,334", l: "Targets", s: "proteins" },
            { n: "184k+", l: "Citations", s: "peer-reviewed" },
          ].map((s, i, arr) => (
            <div key={i} style={{
              padding: "20px 32px",
              borderLeft: i === 0 ? "none" : `1px solid ${MA.forest}22`,
            }}>
              <div style={{ fontFamily: MA_BODY, fontSize: 64, fontWeight: 700, color: MA.forest, lineHeight: 1, letterSpacing: "-0.03em" }}>{s.n}</div>
              <div style={{ fontFamily: MA_DISPLAY, fontStyle: "italic", fontSize: 24, color: MA.forestMid, marginTop: 10 }}>{s.l}</div>
              <MALabel color={MA.forest + "99"} style={{ marginTop: 6 }}>{s.s}</MALabel>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* WHAT'S INSIDE — big editorial section */}
    <section style={{ padding: "80px 48px 100px" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 64, marginBottom: 48 }}>
          <div>
            <MALabel color={MA.forest + "99"}>§ 02 · The graph</MALabel>
            <h2 style={{ fontFamily: MA_DISPLAY, fontSize: 64, color: MA.forest, marginTop: 14, marginBottom: 0, lineHeight: 1.0, fontStyle: "italic" }}>
              What's inside.
            </h2>
          </div>
          <p style={{ fontFamily: MA_BODY, fontSize: 19, lineHeight: 1.55, color: MA.ink, opacity: 0.85, marginTop: 14 }}>
            Five entity types. Typed relationships between them. Every node, every edge, traceable back to the peer-reviewed source that established it. No black boxes, no hallucinations — just a graph you can query.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0 }}>
          {[
            { n: "01", t: "Plants", lat: "Plantae", b: "Curated medicinal taxa with canonical identifiers, ethnobotanical provenance, and traditional usage notes." },
            { n: "02", t: "Compounds", lat: "Composita", b: "Structure-resolved phytochemicals — InChI, SMILES — linked back to the plants that contain them." },
            { n: "03", t: "Targets", lat: "Obiectiva", b: "Proteins and biological mechanisms each compound is known to engage, with affinities where available." },
            { n: "04", t: "Effects", lat: "Effectus", b: "Therapeutic effects, indications, and observed phenotypes — each linked to its supporting evidence." },
            { n: "05", t: "Evidence", lat: "Testimonia", b: "Peer-reviewed citations backing every relationship — DOI, PMID, year, and authors preserved." },
          ].map((row, i, arr) => (
            <div key={row.n} style={{
              padding: "32px 36px",
              borderTop: `1px solid ${MA.forest}22`,
              borderBottom: i === arr.length - 1 || i === arr.length - 2 ? `1px solid ${MA.forest}22` : "none",
              borderRight: i % 2 === 0 && i < arr.length - 1 ? `1px solid ${MA.forest}22` : "none",
              gridColumn: i === arr.length - 1 ? "span 2" : undefined,
            }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 14 }}>
                <div style={{ fontFamily: MA_MONO, fontSize: 14, color: MA.accent, letterSpacing: "0.1em" }}>{row.n}</div>
                <div style={{ fontFamily: MA_DISPLAY, fontSize: 42, color: MA.forest, lineHeight: 1 }}>{row.t}</div>
                <div style={{ fontFamily: MA_DISPLAY, fontStyle: "italic", fontSize: 22, color: MA.forestMid, opacity: 0.7 }}>{row.lat}</div>
              </div>
              <p style={{ fontFamily: MA_BODY, fontSize: 17, lineHeight: 1.55, color: MA.ink, opacity: 0.85, margin: 0, maxWidth: 540 }}>{row.b}</p>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* SCHEMA / GRAPH */}
    <section style={{ background: MA.forest, color: MA.cream, padding: "100px 48px" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 80, alignItems: "center" }}>
        <div>
          <MALabel>§ 03 · Schema</MALabel>
          <h2 style={{ fontFamily: MA_DISPLAY, fontSize: 64, color: MA.cream, marginTop: 14, marginBottom: 28, lineHeight: 1.0, fontStyle: "italic" }}>
            One traversal, end to end.
          </h2>
          <p style={{ fontFamily: MA_BODY, fontSize: 18, lineHeight: 1.6, color: MA.cream, opacity: 0.85, marginBottom: 32 }}>
            A plant contains a compound. That compound engages a target. That target produces an effect. POPPy makes every step queryable, with every edge backed by a citation.
          </p>
          <div style={{ background: MA.forestDeep, padding: "24px 28px", border: `1px solid ${MA.sand}33`, borderRadius: 6, fontFamily: MA_MONO, fontSize: 13, lineHeight: 2, color: MA.cream }}>
            <div><span style={{ color: MA.sand }}>?plant</span> ex:hasCompound <span style={{ color: MA.sand }}>?cmpd</span> .</div>
            <div><span style={{ color: MA.sand }}>?cmpd</span> ex:targets <span style={{ color: MA.sand }}>?protein</span> .</div>
            <div><span style={{ color: MA.sand }}>?protein</span> ex:associatedWith <span style={{ color: MA.sand }}>?effect</span> .</div>
            <div><span style={{ color: MA.sand }}>?_</span> ex:supportedBy <span style={{ color: MA.sand }}>?citation</span> .</div>
          </div>
        </div>
        <div style={{ background: MA.forestDeep, border: `1px solid ${MA.sand}33`, borderRadius: 6, padding: 36 }}>
          <GraphSketch height={340} edgeColor={MA.cream + "55"} />
        </div>
      </div>
    </section>

    {/* PLATES STRIP */}
    <section style={{ padding: "100px 48px" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        <div style={{ marginBottom: 36 }}>
          <MALabel color={MA.forest + "99"}>§ 04 · Featured</MALabel>
          <h2 style={{ fontFamily: MA_DISPLAY, fontSize: 64, color: MA.forest, marginTop: 14, marginBottom: 0, lineHeight: 1.0, fontStyle: "italic" }}>
            Plants, indexed.
          </h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 16 }}>
          {[
            { lat: "Papaver somniferum", common: "Opium poppy", n: 412 },
            { lat: "Curcuma longa", common: "Turmeric", n: 289 },
            { lat: "Salvia officinalis", common: "Common sage", n: 176 },
            { lat: "Withania somnifera", common: "Ashwagandha", n: 203 },
          ].map((p, i) => (
            <div key={i}>
              <PlatePlaceholder
                caption={`No. 0${i + 1}`}
                binomial={p.lat}
                height={260}
                color={MA.forest}
                bg={MA.creamLight}
                style={{ border: `1px solid ${MA.forest}33` }}
              />
              <div style={{ marginTop: 16 }}>
                <div style={{ fontFamily: MA_DISPLAY, fontStyle: "italic", fontSize: 22, color: MA.forest }}>{p.lat}</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 6 }}>
                  <MALabel color={MA.forest + "99"}>{p.common}</MALabel>
                  <div style={{ fontFamily: MA_MONO, fontSize: 13, color: MA.accent }}>{p.n} cmpds →</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* CTA */}
    <section style={{ padding: "0 48px 100px" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", background: MA.forest, color: MA.cream, padding: "80px 80px", borderRadius: 8, display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 56, alignItems: "center" }}>
        <div>
          <MALabel>Open access · CC-BY 4.0</MALabel>
          <h2 style={{ fontFamily: MA_DISPLAY, fontSize: 64, marginTop: 16, marginBottom: 20, lineHeight: 1.0 }}>
            Take it, <span style={{ fontStyle: "italic", color: MA.sand }}>use it</span>, cite it.
          </h2>
          <p style={{ fontFamily: MA_BODY, fontSize: 18, lineHeight: 1.55, color: MA.cream, opacity: 0.85, margin: 0, maxWidth: 480 }}>
            Three serializations, full documentation, BibTeX citation, and a live SPARQL endpoint. Released under CC-BY 4.0.
          </p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <MAButton>Download ontology</MAButton>
          <MAButton variant="outline">Read the paper</MAButton>
        </div>
      </div>
    </section>

    <MAFooter />
  </div>
);

Object.assign(window, { ModernHome, MANav, MAFooter, MAButton, MALabel, MA, MA_DISPLAY, MA_BODY, MA_MONO });
