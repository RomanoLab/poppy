  (function () {
    "use strict";
    // Top 24 species by node/edge count in the ontology. `bin` is the antique
    // Köhler binomial shown on the plate; `wiki` is the modern Wikipedia title
    // used only to resolve a live photo from Wikimedia Commons.
    var SPECIES = [
      { slug:"papaver-somniferum",    bin:"Papaver somniferum",    common:"Opium poppy",      wiki:"Papaver somniferum",   conn:524 },
      { slug:"digitalis-purpurea",    bin:"Digitalis purpurea",    common:"Foxglove",         wiki:"Digitalis purpurea",   conn:487 },
      { slug:"camellia-thea",         bin:"Camellia thea",         common:"Tea",              wiki:"Camellia sinensis",    conn:463 },
      { slug:"nicotiana-tabacum",     bin:"Nicotiana tabacum",     common:"Tobacco",          wiki:"Nicotiana tabacum",    conn:451 },
      { slug:"cinnamomum-zeylanicum", bin:"Cinnamomum zeylanicum", common:"Ceylon cinnamon",  wiki:"Cinnamomum verum",     conn:432 },
      { slug:"datura-stramonium",     bin:"Datura stramonium",     common:"Jimsonweed",       wiki:"Datura stramonium",    conn:418 },
      { slug:"croton-tiglium",        bin:"Croton tiglium",        common:"Purging croton",   wiki:"Croton tiglium",       conn:401 },
      { slug:"rosa-centifolia",       bin:"Rosa centifolia",       common:"Cabbage rose",     wiki:"Rosa × centifolia",    conn:389 },
      { slug:"citrus-limonum",        bin:"Citrus limonum",        common:"Lemon",            wiki:"Lemon",                conn:376 },
      { slug:"ipomoea-purga",         bin:"Ipomoea purga",         common:"Jalap",            wiki:"Ipomoea purga",        conn:364 },
      { slug:"verbascum-phlomoides",  bin:"Verbascum phlomoides",  common:"Orange mullein",   wiki:"Verbascum phlomoides", conn:352 },
      { slug:"inula-helenium",        bin:"Inula helenium",        common:"Elecampane",       wiki:"Inula helenium",       conn:341 },
      { slug:"tussilago-farfara",     bin:"Tussilago farfara",     common:"Coltsfoot",        wiki:"Tussilago farfara",    conn:333 },
      { slug:"levisticum-officinale", bin:"Levisticum officinale", common:"Lovage",           wiki:"Levisticum officinale",conn:322 },
      { slug:"anacyclus-pyrethrum",   bin:"Anacyclus pyrethrum",   common:"Pellitory",        wiki:"Anacyclus pyrethrum",  conn:314 },
      { slug:"erythraea-centaurium",  bin:"Erythraea centaurium",  common:"Common centaury",  wiki:"Centaurium erythraea", conn:305 },
      { slug:"citrus-vulgaris",       bin:"Citrus vulgaris",       common:"Bitter orange",    wiki:"Bitter orange",        conn:297 },
      { slug:"rubus-idaeus",          bin:"Rubus idaeus",          common:"Raspberry",        wiki:"Rubus idaeus",         conn:288 },
      { slug:"prunus-cerasus",        bin:"Prunus cerasus",        common:"Sour cherry",      wiki:"Prunus cerasus",       conn:279 },
      { slug:"pirus-malus",           bin:"Pirus malus",           common:"Apple",            wiki:"Malus domestica",      conn:271 },
      { slug:"cydonia-vulgaris",      bin:"Cydonia vulgaris",      common:"Quince",           wiki:"Cydonia oblonga",      conn:263 },
      { slug:"quercus-sessiliflora",  bin:"Quercus sessiliflora",  common:"Sessile oak",      wiki:"Quercus petraea",      conn:254 },
      { slug:"cnicus-benedictus",     bin:"Cnicus benedictus",     common:"Blessed thistle",  wiki:"Centaurea benedicta",  conn:246 },
      { slug:"chrysanthemum-roseum",  bin:"Chrysanthemum roseum",  common:"Painted daisy",    wiki:"Tanacetum coccineum",  conn:238 }
    ];

    var SHOW = 8;                 // cards rendered per visit
    var ROMAN = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"];
    var CACHE_KEY = "poppy-featured-img-v2";  // { slug: url | "none" }
    var grid = document.getElementById("tabulae-grid");
    if (!grid) return;

    function readCache() {
      try { return JSON.parse(localStorage.getItem(CACHE_KEY) || "{}"); } catch (e) { return {}; }
    }
    function writeCache(c) { try { localStorage.setItem(CACHE_KEY, JSON.stringify(c)); } catch (e) {} }

    function shuffle(a) {
      a = a.slice();
      for (var i = a.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var t = a[i]; a[i] = a[j]; a[j] = t;
      }
      return a;
    }

    // (thumbnail size is requested directly from the MediaWiki API below)

    var cache = readCache();

    function resolveImage(sp, imgEl, box) {
      // cached hit
      if (cache[sp.slug] && cache[sp.slug] !== "none") { applyImg(imgEl, box, cache[sp.slug]); return; }
      if (cache[sp.slug] === "none") { box.classList.remove("is-loading"); return; }

      // Ask the MediaWiki API for the page's lead image at 500px. The API
      // generates a guaranteed-valid (cached) thumbnail URL and follows the
      // redirect from antique synonyms to the modern accepted name.
      var url = "https://en.wikipedia.org/w/api.php?action=query&format=json&origin=*"
              + "&redirects=1&prop=pageimages&piprop=thumbnail&pithumbsize=500&titles="
              + encodeURIComponent(sp.wiki);
      fetch(url, { headers: { accept: "application/json" } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) {
          var src = null;
          try {
            var pages = j.query.pages;
            var p = pages[Object.keys(pages)[0]];
            src = p && p.thumbnail && p.thumbnail.source;
          } catch (e) {}
          if (src) { cache[sp.slug] = src; writeCache(cache); applyImg(imgEl, box, src); }
          else { cache[sp.slug] = "none"; writeCache(cache); box.classList.remove("is-loading"); }
        })
        .catch(function () { box.classList.remove("is-loading"); });
    }

    function applyImg(imgEl, box, src) {
      imgEl.onload = function () {
        box.classList.remove("is-loading");
        box.classList.add("has-img");
        // Set the reveal inline and synchronously (no rAF — it pauses on
        // backgrounded tabs). The element was painted at the base opacity:0,
        // so an active tab still fades in via the CSS transition.
        imgEl.style.opacity = "1";
        imgEl.style.transform = "scale(1)";
        var pb = box.querySelector(".pb");
        if (pb) pb.style.opacity = "0";
      };
      imgEl.onerror = function () { box.classList.remove("is-loading"); };
      imgEl.src = src;
    }

    function render() {
      var pick = shuffle(SPECIES).slice(0, SHOW);
      grid.innerHTML = "";
      pick.forEach(function (sp, i) {
        var plate = document.createElement("a");
        plate.className = "tab-plate";
        plate.href = "Explore.html?q=" + encodeURIComponent(sp.bin);
        plate.setAttribute("aria-label", "Explore " + sp.bin + " (" + sp.common + ")");

        var box = document.createElement("div");
        box.className = "plate-box is-loading";

        var pc = document.createElement("div");
        pc.className = "pc";
        pc.textContent = "Tab. " + (ROMAN[i] || (i + 1));

        var pb = document.createElement("div");
        pb.className = "pb";
        pb.textContent = sp.bin;

        var img = document.createElement("img");
        img.className = "plate-img";
        img.alt = sp.bin + " — " + sp.common;
        img.referrerPolicy = "no-referrer";

        box.appendChild(pc);
        box.appendChild(pb);
        box.appendChild(img);

        var cap = document.createElement("div");
        cap.className = "tab-caption";
        var lat = document.createElement("div");
        lat.className = "lat";
        lat.textContent = sp.bin;
        var tc = document.createElement("div");
        tc.className = "mono-cap tc";
        tc.textContent = sp.common + " · " + sp.conn + " connections";
        cap.appendChild(lat);
        cap.appendChild(tc);

        plate.appendChild(box);
        plate.appendChild(cap);
        grid.appendChild(plate);

        resolveImage(sp, img, box);
      });
    }

    render();
  })();
  

    // ─── Pure-SVG graph renderer. No cytoscape, no library quirks ───

    // Ontology data + graph helpers come from the shared file (ontology-data.js),
    // which is the single source to swap when the real ontology is wired in.
    const { NODES, EDGES, ROLE_COLOR, neighborhood, findByLabel, prettyPredicate } = window.POPPY;

    // ─── SVG rendering ───
    const SVG_NS = "http://www.w3.org/2000/svg";

    const NODE_R = {
      __center: 28,
      Plant: 16, Compound: 14, Target: 12, Effect: 11, Citation: 8, Other: 12,
    };
    const RING_FRAC = {
      Plant: 0.40, Compound: 0.62, Target: 0.78, Effect: 0.92, Citation: 1.00, Other: 1.00,
    };
    // per-ring start angle offset so first nodes don't stack along the top axis
    const RING_OFFSET = {
      Plant: 0.8, Compound: 0, Target: 0.6, Effect: 0.3, Citation: 1.1, Other: 0,
    };

    let lastSub = null;
    let currentCenter = null;

    function renderSubgraph(sub, opts) {
      lastSub = sub;
      const container = document.getElementById("graph");
      // wipe existing
      while (container.firstChild) container.removeChild(container.firstChild);

      const cw = container.clientWidth  || 1004;
      const ch = container.clientHeight || 660;

      const svg = document.createElementNS(SVG_NS, "svg");
      svg.setAttribute("width", "100%");
      svg.setAttribute("height", "100%");
      svg.setAttribute("viewBox", `0 0 ${cw} ${ch}`);
      svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
      svg.style.display = "block";

      // arrowhead marker
      const defs = document.createElementNS(SVG_NS, "defs");
      defs.innerHTML =
        `<marker id="poppy-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
           <path d="M 0 0 L 10 5 L 0 10 z" fill="#8a7a4a"/>
         </marker>`;
      svg.appendChild(defs);

      const cx = cw / 2, cy = ch / 2;
      // Use the full ellipse defined by the container, not min(w,h). This makes
      // the graph fill wide canvases without horizontal stretch math.
      const maxH = cw / 2 - 60;
      const maxV = ch / 2 - 50;

      // node lookup for sizing during edge drawing
      const nodeLookup = {};
      for (const n of sub.nodes) nodeLookup[n.id] = n;

      // compute positions on per-ring ellipses (a = maxH * frac, b = maxV * frac)
      const positions = { [sub.center]: { x: cx, y: cy } };
      const buckets = { Plant: [], Compound: [], Target: [], Effect: [], Citation: [], Other: [] };
      for (const n of sub.nodes) {
        if (n.id === sub.center) continue;
        (buckets[n.role] || buckets.Other).push(n);
      }
      for (const role of ["Plant", "Compound", "Target", "Effect", "Citation", "Other"]) {
        const items = buckets[role];
        if (!items.length) continue;
        const a = maxH * RING_FRAC[role];
        const b = maxV * RING_FRAC[role];
        const start = -Math.PI / 2 + (RING_OFFSET[role] || 0);
        items.forEach((item, i) => {
          const angle = start + (2 * Math.PI * i) / items.length;
          positions[item.id] = {
            x: cx + a * Math.cos(angle),
            y: cy + b * Math.sin(angle),
          };
        });
      }

      const radiusOf = (id) =>
        id === sub.center ? NODE_R.__center : (NODE_R[nodeLookup[id]?.role] || 12);

      // ─── edges ───
      const edgesG = document.createElementNS(SVG_NS, "g");
      edgesG.setAttribute("class", "edges");
      for (const e of sub.edges) {
        const p1 = positions[e.source];
        const p2 = positions[e.target];
        if (!p1 || !p2) continue;
        const r1 = radiusOf(e.source);
        const r2 = radiusOf(e.target);
        const dx = p2.x - p1.x, dy = p2.y - p1.y;
        const dist = Math.hypot(dx, dy) || 1;
        const ux = dx / dist, uy = dy / dist;
        const x1 = p1.x + ux * r1;
        const y1 = p1.y + uy * r1;
        const x2 = p2.x - ux * (r2 + 4);
        const y2 = p2.y - uy * (r2 + 4);

        const line = document.createElementNS(SVG_NS, "line");
        line.setAttribute("x1", x1); line.setAttribute("y1", y1);
        line.setAttribute("x2", x2); line.setAttribute("y2", y2);
        line.setAttribute("stroke", "#8a7a4a");
        line.setAttribute("stroke-width", "1");
        line.setAttribute("marker-end", "url(#poppy-arrow)");
        edgesG.appendChild(line);

        // label at midpoint with parchment background (paint-order stroke trick)
        const mx = (x1 + x2) / 2;
        const my = (y1 + y2) / 2;
        const label = prettyPredicate(e.predicate);

        const text = document.createElementNS(SVG_NS, "text");
        text.textContent = label;
        text.setAttribute("x", mx);
        text.setAttribute("y", my);
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
      }
      svg.appendChild(edgesG);

      // ─── nodes ───
      const nodesG = document.createElementNS(SVG_NS, "g");
      for (const n of sub.nodes) {
        const p = positions[n.id];
        const r = radiusOf(n.id);
        const color = ROLE_COLOR[n.role] || ROLE_COLOR.Other;

        const g = document.createElementNS(SVG_NS, "g");
        g.style.cursor = "pointer";
        g.setAttribute("data-id", n.id);

        const circle = document.createElementNS(SVG_NS, "circle");
        circle.setAttribute("cx", p.x);
        circle.setAttribute("cy", p.y);
        circle.setAttribute("r", r);
        circle.setAttribute("fill", color);
        if (n.id === sub.center) {
          circle.setAttribute("stroke", "#243025");
          circle.setAttribute("stroke-width", "3");
        }
        g.appendChild(circle);

        // hover halo
        const halo = document.createElementNS(SVG_NS, "circle");
        halo.setAttribute("cx", p.x);
        halo.setAttribute("cy", p.y);
        halo.setAttribute("r", r + 6);
        halo.setAttribute("fill", "transparent");
        halo.setAttribute("stroke", color);
        halo.setAttribute("stroke-width", "0");
        halo.setAttribute("opacity", "0.4");
        halo.style.transition = "stroke-width 150ms ease";
        g.appendChild(halo);
        g.addEventListener("mouseenter", () => halo.setAttribute("stroke-width", "2"));
        g.addEventListener("mouseleave", () => halo.setAttribute("stroke-width", "0"));

        // label below
        const isCenter = n.id === sub.center;
        const fontSize = isCenter ? 18 : n.role === "Citation" ? 12 : 14;
        const italic = (n.role === "Plant" || n.role === "Compound" || n.role === "Citation");

        const label = document.createElementNS(SVG_NS, "text");
        label.textContent = n.label;
        label.setAttribute("x", p.x);
        label.setAttribute("y", p.y + r + fontSize + 4);
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("font-family", "EB Garamond, Cardo, Georgia, serif");
        label.setAttribute("font-size", fontSize);
        label.setAttribute("fill", "#1a1f17");
        if (italic) label.setAttribute("font-style", "italic");
        // parchment outline so labels stay legible when an edge runs under them
        label.setAttribute("stroke", "#fdf8e9");
        label.setAttribute("stroke-width", "3");
        label.setAttribute("paint-order", "stroke fill");
        g.appendChild(label);

        g.addEventListener("click", () => focusOn(n.id));
        nodesG.appendChild(g);
      }
      svg.appendChild(nodesG);

      container.appendChild(svg);

      // caption + status
      const role = sub.role || "";
      const ex = opts && opts.example;
      document.getElementById("graph-caption").innerHTML =
        (ex ? `<span style="color:var(--umber); font-family:var(--mono); font-size:11px; letter-spacing:0.16em; text-transform:uppercase; margin-right:10px;">An example ❦</span>` : "") +
        `Centered on <em>${sub.label}</em>` +
        (sub.common ? ` <span style="color:var(--umber)">· ${sub.common}</span>` : "") +
        ` <span style="color:var(--umber); font-style:normal; font-family:var(--mono); font-size:11px; letter-spacing:0.18em; text-transform:uppercase; margin-left:8px;">${role}</span>`;
      document.getElementById("msg").textContent = ex
        ? `${sub.nodes.length} entities · ${sub.edges.length} relationships — search above, or click any circle, to explore your own.`
        : `Showing ${sub.nodes.length} entities and ${sub.edges.length} relationships. Click any circle to refocus.`;
    }

    function focusOn(id, opts) {
      opts = opts || {};
      const sub = neighborhood(id);
      if (!sub) return;
      currentCenter = id;
      if (!opts.example) document.getElementById("search").value = sub.label;
      // point "Explore further" at this entity's register
      const ef = document.getElementById("explore-further");
      if (ef) ef.href = "Explore.html?q=" + encodeURIComponent(id);
      document.body.classList.add("graph-active");
      // unhide BEFORE rendering so clientWidth/clientHeight read correctly
      const wrap = document.getElementById("graph-wrap");
      wrap.hidden = false;
      // give the browser one frame to lay out the now-visible container
      requestAnimationFrame(() => {
        renderSubgraph(sub, opts);
        if (!opts.example) {   // an auto-example stays put in the hero; a real pick scrolls into view
          const rect = wrap.getBoundingClientRect();
          if (rect.top > window.innerHeight * 0.6) {
            window.scrollTo({ top: window.scrollY + rect.top - 100, behavior: "smooth" });
          }
        }
      });
    }

    function runSearch(q) {
      const query = (q || document.getElementById("search").value || "").trim();
      const msg = document.getElementById("msg");
      if (!query) { msg.textContent = "Type a plant name, compound, or target."; return; }
      const id = findByLabel(query);
      if (!id) { msg.textContent = `No results for "${query}". Try one of the suggestions below.`; return; }
      focusOn(id);
    }

    // ─── Search + autosuggest ──────────────────────────────────────────
    // Tier 1: all ~45k plants, lazy-loaded from plants_index.json on first focus.
    // Tier 2: curated compounds / targets / citations already in memory (window.POPPY.NODES).
    (function () {
      const input = document.getElementById("search");
      const box = document.getElementById("suggest");
      const btn = document.getElementById("searchBtn");
      if (!input || !box) return;

      const CURATED = Object.keys(NODES).map((id) => ({
        id, name: NODES[id].label, common: NODES[id].common || "", role: NODES[id].role || "", source: "curated",
      }));
      const curatedLabels = new Set(CURATED.map((e) => e.name.toLowerCase()));

      let PLANTS = null, loading = false;
      function loadPlants() {
        if (PLANTS || loading) return;
        loading = true;
        fetch("data/plants_index.json")
          .then((r) => (r.ok ? r.json() : []))
          .then((a) => { PLANTS = a || []; if (document.activeElement === input && input.value.trim()) render(input.value); })
          .catch(() => { PLANTS = []; });   // degrade gracefully → curated-only suggestions
      }

      let items = [], active = -1;
      const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
      const rank = (name, q) => { name = name.toLowerCase(); return name === q ? 0 : name.indexOf(q) === 0 ? 1 : 2; };

      function build(q) {
        q = q.toLowerCase();
        const out = [];
        CURATED.forEach((e) => {
          if (e.name.toLowerCase().includes(q) || (e.common && e.common.toLowerCase().includes(q)))
            out.push({ ...e, s: rank(e.name, q) - 0.5, nc: 1e9 });   // curated float to top within a tier
        });
        if (PLANTS) {
          for (let i = 0; i < PLANTS.length; i++) {
            const p = PLANTS[i];
            if (curatedLabels.has((p.name || "").toLowerCase())) continue;   // dedupe vs curated
            if ((p.name || "").toLowerCase().includes(q))
              out.push({ id: p.id, name: p.name, common: "", role: "Plant", source: "plant", s: rank(p.name, q), nc: p.nc || 0, trials: p.trials || 0 });
          }
        }
        out.sort((a, b) => (a.s - b.s) || (b.nc - a.nc) || a.name.localeCompare(b.name));
        return { list: out.slice(0, 10), total: out.length };
      }

      function render(val) {
        const q = (val || "").trim();
        if (q.length < 2) return close();
        const r = build(q); items = r.list; active = -1;
        if (!items.length) return close();
        const rows = items.map((it, i) => {
          const color = (ROLE_COLOR && ROLE_COLOR[it.role]) || "var(--umber)";
          const common = it.common ? `<span class="s-common">${esc(it.common)}</span>` : "";
          let meta = "";
          if (it.source === "plant" && it.nc)
            meta = `<span class="s-meta">${it.nc} link${it.nc === 1 ? "" : "s"}${it.trials ? ` · ${it.trials} trial${it.trials === 1 ? "" : "s"}` : ""}</span>`;
          return `<li role="option" data-i="${i}"><span class="s-dot" style="background:${color}"></span>`
               + `<span class="s-name">${esc(it.name)}${common}</span>${meta}<span class="s-type">${esc(it.role)}</span></li>`;
        });
        const more = r.total - items.length;
        if (more > 0) rows.push(`<li class="s-more" aria-disabled="true">+${more.toLocaleString()} more — keep typing to narrow</li>`);
        box.innerHTML = rows.join("");
        box.hidden = false; input.setAttribute("aria-expanded", "true");
      }
      function close() { box.hidden = true; box.innerHTML = ""; items = []; active = -1; input.setAttribute("aria-expanded", "false"); }
      function setActive(i) {
        const lis = box.querySelectorAll("li");
        if (lis[active]) lis[active].classList.remove("active");
        active = items.length ? (i + items.length) % items.length : -1;
        if (lis[active]) { lis[active].classList.add("active"); lis[active].scrollIntoView({ block: "nearest" }); }
      }
      function choose(it) {
        if (!it) return;
        input.value = it.name; close();
        if (it.source === "curated") focusOn(it.id);
        else window.location.href = "Explore.html?q=" + encodeURIComponent(it.name);
      }

      input.addEventListener("focus", loadPlants);
      let t;
      input.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => render(input.value), 70); });
      input.addEventListener("keydown", (e) => {
        if (box.hidden) { if (e.key === "Enter") runSearch(); return; }
        if (e.key === "ArrowDown") { e.preventDefault(); setActive(active + 1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); setActive(active - 1); }
        else if (e.key === "Enter") { e.preventDefault(); active >= 0 ? choose(items[active]) : runSearch(); }
        else if (e.key === "Escape") { close(); }
      });
      box.addEventListener("mousedown", (e) => {   // mousedown beats input blur
        const li = e.target.closest("li"); if (!li) return;
        e.preventDefault(); choose(items[+li.dataset.i]);
      });
      input.addEventListener("blur", () => setTimeout(close, 120));

      btn.addEventListener("click", () => runSearch());
      document.querySelectorAll(".try-chips .chip").forEach((c) => {
        if (c.id === "surprise") return;
        c.addEventListener("click", () => { input.value = c.dataset.q; runSearch(c.dataset.q); });
      });
      // "Surprise me" → a random curated species' graph, instantly (rich + no fetch)
      const surpriseBtn = document.getElementById("surprise");
      if (surpriseBtn) surpriseBtn.addEventListener("click", () => {
        const pool = CURATED.filter((e) => e.role === "Plant");
        if (!pool.length) return;
        let pick = pool[Math.floor(Math.random() * pool.length)];
        for (let i = 0; i < 6 && pick.id === currentCenter; i++) pick = pool[Math.floor(Math.random() * pool.length)];
        close(); focusOn(pick.id);
      });
    })();

    // Deep-link: Home.html?q=<id|label> opens the graph centered on that entity
    // (used by the Explore page rows to close the overview → focus loop).
    (function () {
      let q = null;
      try { q = new URLSearchParams(window.location.search).get("q"); } catch (e) {}
      const id = q && findByLabel(q);
      if (id) focusOn(id);
      else focusOn("papaver-somniferum", { example: true });   // show a live example graph on landing
    })();

    // "What can you ask POPPy?" cards → run the question live on a concrete curated example
    document.querySelectorAll(".ask-card[data-example]").forEach((card) => {
      const go = () => {
        const exId = card.getAttribute("data-example");
        if (!exId) return;
        focusOn(exId);
        document.getElementById("graph-wrap").scrollIntoView({ behavior: "smooth", block: "center" });
      };
      card.addEventListener("click", go);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); }
      });
    });

    // Re-render when the viewport changes so the graph keeps filling the container
    let resizeT;
    window.addEventListener("resize", () => {
      clearTimeout(resizeT);
      resizeT = setTimeout(() => { if (lastSub) renderSubgraph(lastSub); }, 150);
    });
  

    // ─── Botanical plate rotator ───
    (function () {
      const INTERVAL_MS = 5000;
      const rotator = document.getElementById("rotator");
      if (!rotator) return;
      const images = Array.from(rotator.querySelectorAll(".plate-slide"));
      const caption = rotator.querySelector(".caption");
      const dotsEl = rotator.querySelector(".dots");
      let current = 0;
      let timer;

      images.forEach((_, i) => {
        const dot = document.createElement("button");
        dot.className = "dot" + (i === 0 ? " active" : "");
        dot.setAttribute("aria-label", "Go to plate " + (i + 1));
        dot.addEventListener("click", () => { goTo(i); resetTimer(); });
        dotsEl.appendChild(dot);
      });

      function goTo(index) {
        images[current].classList.remove("active");
        dotsEl.children[current].classList.remove("active");
        current = (index + images.length) % images.length;
        images[current].classList.add("active");
        dotsEl.children[current].classList.add("active");
        const bin = images[current].dataset.bin || "";
        const common = images[current].dataset.common || "";
        caption.innerHTML = bin + (common ? `<span class="common">${common}</span>` : "");
        rotator.classList.toggle("show-caption", !!bin);
      }

      function advance() { goTo(current + 1); }
      function resetTimer() { clearInterval(timer); timer = setInterval(advance, INTERVAL_MS); }

      rotator.addEventListener("mouseenter", () => clearInterval(timer));
      rotator.addEventListener("mouseleave", resetTimer);

      goTo(0);
      resetTimer();
    })();
  
