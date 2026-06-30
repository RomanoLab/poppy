/* graph.js — shared pure-SVG neighbourhood renderer.
 *
 * Used by the Home landing example AND the Explore knowledge-graph view, so the
 * two stay in sync. Draws a window.POPPY.neighborhood(id) result into a container
 * element; node clicks are delegated to the caller via opts.onNodeClick(id).
 * Deliberately knows nothing about page-specific DOM (captions, search, etc.). */
(function () {
  "use strict";

  var SVG_NS = "http://www.w3.org/2000/svg";

  var NODE_R = { __center: 28, Plant: 16, Compound: 14, Target: 12, Effect: 11, Citation: 8, Other: 12 };
  var RING_FRAC = { Plant: 0.40, Compound: 0.62, Target: 0.78, Effect: 0.92, Citation: 1.00, Other: 1.00 };
  // per-ring start-angle offset so first nodes don't stack along the top axis
  var RING_OFFSET = { Plant: 0.8, Compound: 0, Target: 0.6, Effect: 0.3, Citation: 1.1, Other: 0 };

  function renderSubgraph(container, sub, opts) {
    opts = opts || {};
    var P = window.POPPY, ROLE_COLOR = P.ROLE_COLOR, prettyPredicate = P.prettyPredicate;

    while (container.firstChild) container.removeChild(container.firstChild);

    var cw = container.clientWidth || 1004, ch = container.clientHeight || 660;

    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.setAttribute("viewBox", "0 0 " + cw + " " + ch);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.style.display = "block";

    var defs = document.createElementNS(SVG_NS, "defs");
    defs.innerHTML =
      '<marker id="poppy-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">' +
      '<path d="M 0 0 L 10 5 L 0 10 z" fill="#8a7a4a"/></marker>';
    svg.appendChild(defs);

    var cx = cw / 2, cy = ch / 2;
    // full ellipse defined by the container (not min(w,h)) so it fills wide canvases
    var maxH = cw / 2 - 60, maxV = ch / 2 - 50;

    var nodeLookup = {};
    sub.nodes.forEach(function (n) { nodeLookup[n.id] = n; });

    // positions on per-ring ellipses (a = maxH * frac, b = maxV * frac)
    var positions = {};
    positions[sub.center] = { x: cx, y: cy };
    var buckets = { Plant: [], Compound: [], Target: [], Effect: [], Citation: [], Other: [] };
    sub.nodes.forEach(function (n) {
      if (n.id !== sub.center) (buckets[n.role] || buckets.Other).push(n);
    });
    ["Plant", "Compound", "Target", "Effect", "Citation", "Other"].forEach(function (role) {
      var items = buckets[role];
      if (!items.length) return;
      var a = maxH * RING_FRAC[role], b = maxV * RING_FRAC[role];
      var start = -Math.PI / 2 + (RING_OFFSET[role] || 0);
      items.forEach(function (item, i) {
        var angle = start + (2 * Math.PI * i) / items.length;
        positions[item.id] = { x: cx + a * Math.cos(angle), y: cy + b * Math.sin(angle) };
      });
    });

    function radiusOf(id) {
      return id === sub.center ? NODE_R.__center : (NODE_R[(nodeLookup[id] || {}).role] || 12);
    }

    // ─── edges ───
    var edgesG = document.createElementNS(SVG_NS, "g");
    edgesG.setAttribute("class", "edges");
    sub.edges.forEach(function (e) {
      var p1 = positions[e.source], p2 = positions[e.target];
      if (!p1 || !p2) return;
      var r1 = radiusOf(e.source), r2 = radiusOf(e.target);
      var dx = p2.x - p1.x, dy = p2.y - p1.y;
      var dist = Math.hypot(dx, dy) || 1;
      var ux = dx / dist, uy = dy / dist;
      var x1 = p1.x + ux * r1, y1 = p1.y + uy * r1;
      var x2 = p2.x - ux * (r2 + 4), y2 = p2.y - uy * (r2 + 4);

      var line = document.createElementNS(SVG_NS, "line");
      line.setAttribute("x1", x1); line.setAttribute("y1", y1);
      line.setAttribute("x2", x2); line.setAttribute("y2", y2);
      line.setAttribute("stroke", "#8a7a4a");
      line.setAttribute("stroke-width", "1");
      line.setAttribute("marker-end", "url(#poppy-arrow)");
      edgesG.appendChild(line);

      var mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
      var text = document.createElementNS(SVG_NS, "text");
      text.textContent = prettyPredicate(e.predicate);
      text.setAttribute("x", mx); text.setAttribute("y", my);
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("dominant-baseline", "middle");
      text.setAttribute("font-family", "IBM Plex Mono, ui-monospace, monospace");
      text.setAttribute("font-size", "9");
      text.setAttribute("letter-spacing", "1.2");
      text.setAttribute("fill", "#7a5a3a");
      text.setAttribute("stroke", "#fdf8e9");
      text.setAttribute("stroke-width", "4");
      text.setAttribute("paint-order", "stroke fill");
      text.style.textTransform = "uppercase";
      edgesG.appendChild(text);
    });
    svg.appendChild(edgesG);

    // ─── nodes ───
    var nodesG = document.createElementNS(SVG_NS, "g");
    sub.nodes.forEach(function (n) {
      var p = positions[n.id], r = radiusOf(n.id);
      var color = ROLE_COLOR[n.role] || ROLE_COLOR.Other;

      var g = document.createElementNS(SVG_NS, "g");
      g.style.cursor = "pointer";
      g.setAttribute("data-id", n.id);

      var circle = document.createElementNS(SVG_NS, "circle");
      circle.setAttribute("cx", p.x); circle.setAttribute("cy", p.y); circle.setAttribute("r", r);
      circle.setAttribute("fill", color);
      if (n.id === sub.center) { circle.setAttribute("stroke", "#243025"); circle.setAttribute("stroke-width", "3"); }
      g.appendChild(circle);

      var halo = document.createElementNS(SVG_NS, "circle");
      halo.setAttribute("cx", p.x); halo.setAttribute("cy", p.y); halo.setAttribute("r", r + 6);
      halo.setAttribute("fill", "transparent");
      halo.setAttribute("stroke", color);
      halo.setAttribute("stroke-width", "0");
      halo.setAttribute("opacity", "0.4");
      halo.style.transition = "stroke-width 150ms ease";
      g.appendChild(halo);
      g.addEventListener("mouseenter", function () { halo.setAttribute("stroke-width", "2"); });
      g.addEventListener("mouseleave", function () { halo.setAttribute("stroke-width", "0"); });

      var isCenter = n.id === sub.center;
      var fontSize = isCenter ? 18 : n.role === "Citation" ? 12 : 14;
      var italic = (n.role === "Plant" || n.role === "Compound" || n.role === "Citation");

      var label = document.createElementNS(SVG_NS, "text");
      label.textContent = n.label;
      label.setAttribute("x", p.x); label.setAttribute("y", p.y + r + fontSize + 4);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("font-family", "EB Garamond, Cardo, Georgia, serif");
      label.setAttribute("font-size", fontSize);
      label.setAttribute("fill", "#1a1f17");
      if (italic) label.setAttribute("font-style", "italic");
      label.setAttribute("stroke", "#fdf8e9");
      label.setAttribute("stroke-width", "3");
      label.setAttribute("paint-order", "stroke fill");
      g.appendChild(label);

      g.addEventListener("click", function () { if (opts.onNodeClick) opts.onNodeClick(n.id); });
      nodesG.appendChild(g);
    });
    svg.appendChild(nodesG);

    container.appendChild(svg);
  }

  // Look up a neighbourhood by id and render it. Returns the sub (or null).
  function show(container, id, opts) {
    var sub = window.POPPY.neighborhood(id);
    if (!sub) return null;
    renderSubgraph(container, sub, opts);
    return sub;
  }

  window.POPPY_GRAPH = { renderSubgraph: renderSubgraph, show: show };
})();
