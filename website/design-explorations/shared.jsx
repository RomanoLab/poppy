// Shared primitives across all directions

const PlatePlaceholder = ({ caption = "BOTANICAL PLATE", binomial = "", height = 220, color = "#1a1f1a", bg = "transparent", style = {} }) => (
  <div
    className="plate-placeholder"
    style={{
      height,
      color,
      background: bg,
      border: `1px solid ${color}33`,
      ...style,
    }}
  >
    <div className="plate-caption">{caption}</div>
    {binomial && <div className="plate-binomial" style={{ fontFamily: '"EB Garamond", serif', fontSize: 14 }}>{binomial}</div>}
  </div>
);

// Small ornamental divider — three dots, asterism, etc.
const Asterism = ({ color = "currentColor", glyph = "❦", size = 16, gap = 18 }) => (
  <div style={{
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap,
    color,
    fontSize: size,
    opacity: 0.7,
    lineHeight: 1,
  }}>
    <span style={{ flex: "0 0 60px", height: 1, background: color, opacity: 0.4 }}></span>
    <span>{glyph}</span>
    <span style={{ flex: "0 0 60px", height: 1, background: color, opacity: 0.4 }}></span>
  </div>
);

const SectionLabel = ({ children, color = "currentColor" }) => (
  <div className="mono-caption" style={{ color, opacity: 0.7 }}>
    {children}
  </div>
);

// Real graph-shape sketch (nodes + edges) for the explorer area — kept abstract so it
// reads as "this is where the cytoscape graph lives" without faking specific data.
const GraphSketch = ({ width = "100%", height = 280, nodeColor = "#3d5b3e", edgeColor = "#1a1f1a55", bg = "transparent" }) => (
  <svg viewBox="0 0 600 280" width={width} height={height} style={{ background: bg, display: "block" }}>
    <g stroke={edgeColor} strokeWidth="1" fill="none">
      <path d="M 300 140 L 160 70" />
      <path d="M 300 140 L 470 60" />
      <path d="M 300 140 L 90 170" />
      <path d="M 300 140 L 510 200" />
      <path d="M 300 140 L 230 235" />
      <path d="M 300 140 L 400 230" />
      <path d="M 160 70 L 90 170" />
      <path d="M 470 60 L 510 200" />
      <path d="M 230 235 L 400 230" />
    </g>
    {[
      { x: 300, y: 140, r: 22, label: "Plant", fill: "#009E73" },
      { x: 160, y: 70, r: 14, label: "Cmpd", fill: "#0072B2" },
      { x: 470, y: 60, r: 14, label: "Cmpd", fill: "#0072B2" },
      { x: 90, y: 170, r: 14, label: "Cmpd", fill: "#0072B2" },
      { x: 510, y: 200, r: 12, label: "Tgt", fill: "#E69F00" },
      { x: 230, y: 235, r: 12, label: "Tgt", fill: "#E69F00" },
      { x: 400, y: 230, r: 12, label: "Eff", fill: "#CC79A7" },
    ].map((n, i) => (
      <g key={i}>
        <circle cx={n.x} cy={n.y} r={n.r} fill={n.fill} opacity="0.95" />
      </g>
    ))}
  </svg>
);

Object.assign(window, { PlatePlaceholder, Asterism, SectionLabel, GraphSketch });
