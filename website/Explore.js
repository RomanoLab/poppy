    (function () {
      "use strict";
      var P = window.POPPY;
      var NODES = P.NODES, ROLE_COLOR = P.ROLE_COLOR, ROLE_LABEL = P.ROLE_LABEL, ROLE_ORDER = P.ROLE_ORDER;

      var root = document.getElementById("register-root");
      var msg = document.getElementById("reg-msg");
      var input = document.getElementById("reg-search");
      var currentId = null;
      // ---- full-ontology browse: search all plants, lazy-load shards ----
      var FULL = [], FULL_BY_ID = {}, COMP_CACHE = {}, pendingQ = null;
      function djb2(s){var h=5381;for(var i=0;i<s.length;i++){h=((h*33)^s.charCodeAt(i))&0xFFFFFFFF;}return h&255;}
      fetch("data/plants_index.json").then(function(r){return r.ok?r.json():[];}).then(function(a){
        FULL=a||[]; for(var i=0;i<FULL.length;i++){FULL_BY_ID[FULL[i].id]=FULL[i];}
        if(pendingQ){var want=pendingQ;pendingQ=null;var pm=fullFindAll(want);
          if(pm.length===1){loadFullPlant(pm[0].r.id);}
          else if(pm.length>1){msg.textContent="";renderDisambig(pm,want);}
          else{msg.textContent='No entry for "'+want+'".';render("papaver-somniferum");}}
      }).catch(function(){if(pendingQ){msg.textContent='Could not load the entity index.';pendingQ=null;}});
      // split a "a; b [lang]; c" string into clean lowercased names (drops [lang] tags)
      function splitNames(s){
        if(!s) return [];
        return String(s).split(";").map(function(x){
          return x.replace(/\s*\[[a-z?]+\]\s*$/i,"").trim();
        }).filter(Boolean);
      }
      // every searchable name for a record: scientific + common(s) + synonym(s)
      function allNames(r){
        var out=[(r.name||"")];
        return out.concat(splitNames(r.common)).concat(splitNames(r.syn)).filter(Boolean);
      }
      function fullFindPlant(q){
        q=String(q||"").toLowerCase().trim(); if(!q)return null;
        if(FULL_BY_ID[q])return q;
        var partial=null;
        for(var i=0;i<FULL.length;i++){
          var arr=allNames(FULL[i]);
          for(var k=0;k<arr.length;k++){
            var nm=arr[k].toLowerCase();
            if(nm===q)return FULL[i].id;
            if(!partial&&nm.indexOf(q)!==-1)partial=FULL[i].id;
          }
        }
        return partial;
      }
      // all matching plants for a query: exact matches (on any name) first, then partial.
      function fullFindAll(q){
        q=String(q||"").toLowerCase().trim(); if(!q) return [];
        if(FULL_BY_ID[q]) return [{r:FULL_BY_ID[q], via:FULL_BY_ID[q].name||q}];
        var exact=[], partial=[], seen={};
        for(var i=0;i<FULL.length;i++){
          var r=FULL[i], arr=allNames(r), ex=null, pa=null;
          for(var k=0;k<arr.length;k++){
            var nm=arr[k].toLowerCase();
            if(nm===q){ex=arr[k];break;}
            if(!pa && nm.indexOf(q)!==-1) pa=arr[k];
          }
          if(ex){ if(!seen[r.id]){seen[r.id]=1; exact.push({r:r,via:ex});} }
          else if(pa){ if(!seen[r.id]){seen[r.id]=1; partial.push({r:r,via:pa});} }
        }
        return exact.concat(partial);
      }
      // clickable list when a query (often a shared common name) matches several plants.
      function renderDisambig(matches, query){
        var cap=60, shown=matches.slice(0,cap);
        var h='<section class="register"><div class="reg-disambig">'
             +'<div class="reg-disambig-head"><b>'+matches.length+'</b> plants match “'+esc(query)+'”'
             +(matches.length>cap?' (showing first '+cap+')':'')+'</div><ul class="reg-hits">';
        shown.forEach(function(m){
          var r=m.r, commons=splitNames(r.common).slice(0,4).map(esc).join(" · ");
          var via=(m.via && m.via.toLowerCase()!==String(r.name||"").toLowerCase())
                  ? '<span class="hit-via">matched “'+esc(m.via)+'”</span>' : '';
          h+='<li class="reg-hit" data-id="'+esc(r.id)+'" tabindex="0">'
             +'<span class="hit-latin">'+esc(r.name||r.id)+'</span>'
             +(commons?'<span class="hit-common">'+commons+'</span>':'')+via+'</li>';
        });
        h+='</ul></div></section>';
        root.innerHTML=h;
        function go(li){ msg.textContent=""; loadFullPlant(li.dataset.id); }
        root.querySelectorAll(".reg-hit").forEach(function(li){
          li.addEventListener("click", function(){ go(li); });
          li.addEventListener("keydown", function(e){ if(e.key==="Enter"||e.key===" "){ e.preventDefault(); go(li); } });
        });
      }
      function fetchCompShard(b){
        if(COMP_CACHE[b])return Promise.resolve(COMP_CACHE[b]);
        return fetch("data/compounds/"+b+".json").then(function(r){return r.ok?r.json():{};})
          .then(function(j){COMP_CACHE[b]=j;return j;}).catch(function(){COMP_CACHE[b]={};return {};});
      }
      function loadFullPlant(pid){
        var meta=FULL_BY_ID[pid]||{name:pid};
        msg.textContent="Loading "+(meta.name||pid)+"...";
        root.innerHTML='<section class="register"><div class="reg-empty">Loading…</div></section>';
        currentId=null;   // don't let stale data linger while shards load
        fetch("data/plant_edges/"+djb2(pid)+".json").then(function(r){return r.ok?r.json():{};}).then(function(ed){
          var cids=ed[pid]||[], bk={}; cids.forEach(function(c){bk[djb2(c)]=true;});
          return Promise.all(Object.keys(bk).map(fetchCompShard)).then(function(){
            var N=window.POPPY.NODES, E=window.POPPY.EDGES;
            N[pid]={label:meta.name||pid, role:"Plant", common:meta.common||"", syn:meta.syn||"",
              props:[["clinicalTrialCount",String(meta.trials||0)],["compoundCount",String(cids.length)]]};
            cids.forEach(function(c){
              var rec=(COMP_CACHE[djb2(c)]||{})[c];
              if(!N[c]){var p=[];
                if(rec){if(rec.formula)p.push(["hasMolecularFormula",rec.formula]);
                        if(rec.mw)p.push(["hasMolecularWeight",rec.mw]);
                        if(rec.inchikey)p.push(["hasInChIKey",rec.inchikey]);}
                N[c]={label:(rec&&rec.name)||c, role:"Compound", props:p};}
              if(!E.some(function(e){return e.s===pid&&e.t===c;}))E.push({s:pid,t:c,p:"hasCompound"});
            });
            msg.textContent=""; render(pid);
          });
        }).catch(function(){msg.textContent="Could not load "+(meta.name||pid)+".";});
      }


      // ── CSV export — the focused entity's neighbourhood as a triple table.
      //    (subject, predicate, object, object_type) keeps the connections
      //    intact: each relationship is one row in true direction, and the
      //    entity's own data properties are emitted as `literal` triples. ──
      function csvCell(v) {
        v = String(v == null ? "" : v);
        return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
      }
      function buildCSV(id) {
        var subject = NODES[id];
        if (!subject) return "";
        var rows = [["subject", "predicate", "object", "object_type"]];
        (subject.props || []).forEach(function (p) { rows.push([subject.label, p[0], p[1], "literal"]); });
        if (subject.role === "Citation" && subject.doi) rows.push([subject.label, "hasDOI", subject.doi, "literal"]);
        P.relationsOf(id).forEach(function (rel) {
          var other = NODES[rel.id];
          if (!other) return;
          if (rel.dir === "out") rows.push([subject.label, rel.predicate, other.label, ROLE_LABEL[other.role] || other.role]);
          else rows.push([other.label, rel.predicate, subject.label, ROLE_LABEL[subject.role] || subject.role]);
        });
        return rows.map(function (r) { return r.map(csvCell).join(","); }).join("\r\n");
      }
      function downloadCSV(id) {
        var subject = NODES[id];
        if (!subject) return;
        var blob = new Blob([buildCSV(id)], { type: "text/csv;charset=utf-8;" });
        var url = URL.createObjectURL(blob);
        var slug = String(subject.label || "entity").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
        var a = document.createElement("a");
        a.href = url; a.download = "poppy-" + slug + ".csv";
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      }
      // delegate (root persists across re-renders)
      root.addEventListener("click", function (e) {
        if (e.target.closest("#dl-csv") && currentId) downloadCSV(currentId);
      });

      function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

      // "Also known as" / "Scientific synonyms" block: each common name and synonym
      // rendered as its own searchable-looking entry rather than one semicolon blob.
      function otherNamesHtml(n) {
        var html = "";
        var commons = splitNames(n.common);
        if (commons.length) {
          html += '<div class="common"><span class="lbl">Also known as:</span> '
                + commons.map(esc).join(" &middot; ") + '</div>';
        }
        var syns = splitNames(n.syn);
        if (syns.length) {
          html += '<div class="common syn"><span class="lbl">Scientific synonyms:</span> <em>'
                + syns.map(esc).join('</em> &middot; <em>') + '</em></div>';
        }
        return html;
      }

      // name cell: italic Latin binomial for plants, roman for everything else,
      // with the first vernacular name appended in umber when present.
      function nameCell(n) {
        var latin = n.role === "Plant"
          ? '<span class="latin">' + esc(n.label) + '</span>'
          : esc(n.label);
        var first = splitNames(n.common)[0];
        var vern = first ? '<span class="vern">' + esc(first) + '</span>' : "";
        return latin + vern;
      }

      // DOI link (research/citation entities only) — resolves at doi.org
      function doiLink(n) {
        if (n.role !== "Citation" || !n.doi) return "";
        return '<a class="doi-link" href="https://doi.org/' + esc(n.doi) + '" target="_blank" rel="noopener">doi:'
             + esc(n.doi) + '<span class="ext">\u2197</span></a>';
      }

      // Inline multiomics tags — surfaces the NCBI gene-layer attributes
      // (gene symbol, protein, UniProt) right in a target's register row, with
      // the gene symbol linking out to its NCBI Gene record. Reads whatever the
      // ontology recorded in props, so it lights up automatically per entity.
      function propVal(n, key) {
        if (!n.props) return null;
        for (var i = 0; i < n.props.length; i++) {
          if (String(n.props[i][0]).toLowerCase() === key.toLowerCase()) return n.props[i][1];
        }
        return null;
      }
      function geneTags(n) {
        var gene = propVal(n, "hasGene");
        var protein = propVal(n, "hasProtein");
        var uniprot = propVal(n, "hasUniProt");
        if (!gene && !protein && !uniprot) return "";
        var tags = [];
        if (gene) {
          tags.push('<a class="gtag gtag-gene" href="https://www.ncbi.nlm.nih.gov/gene/?term='
            + encodeURIComponent(gene) + '%5Bsym%5D" target="_blank" rel="noopener" title="NCBI Gene">'
            + '<span class="gk">gene</span>' + esc(gene) + '<span class="ext">\u2197</span></a>');
        }
        if (protein) tags.push('<span class="gtag"><span class="gk">protein</span>' + esc(protein) + '</span>');
        if (uniprot) {
          tags.push('<a class="gtag" href="https://www.uniprot.org/uniprotkb/' + encodeURIComponent(uniprot)
            + '/entry" target="_blank" rel="noopener" title="UniProt"><span class="gk">uniprot</span>' + esc(uniprot) + '<span class="ext">\u2197</span></a>');
        }
        return '<div class="gtags">' + tags.join("") + '</div>';
      }

      function setSubjectURL(id) {
        try { history.replaceState(null, "", "Explore.html?q=" + encodeURIComponent(id)); } catch (e) {}
      }

      function render(id) {
        var subject = NODES[id];
        if (!subject) { renderEmpty(); return; }
        currentId = id;
        msg.textContent = "";
        input.value = subject.label;
        setSubjectURL(id);

        var relations = P.relationsOf(id);
        var totalConn = P.connectionCount(id);

        // group related entities by concept type
        var groups = {};
        relations.forEach(function (rel) {
          var n = NODES[rel.id];
          if (!n) return;
          (groups[n.role] = groups[n.role] || []).push(rel);
        });

        var subjColor = ROLE_COLOR[subject.role] || ROLE_COLOR.Other;
        var html = "";

        // ── subject block ──
        html += '<section class="subject">';
        html += '<div class="subject-top">';
        html += '<div class="subject-text">';
        html += '<span class="subject-type"><span class="swatch" style="background:' + subjColor + '"></span>'
              + '<span class="mono-cap" style="opacity:0.85">' + esc(ROLE_LABEL[subject.role] || subject.role) + '</span></span>';
        html += '<h1>' + esc(subject.label) + '</h1>';
        html += otherNamesHtml(subject);
        if (subject.role === "Citation" && subject.doi) {
          html += '<div class="doi"><a href="https://doi.org/' + esc(subject.doi) + '" target="_blank" rel="noopener">doi:'
                + esc(subject.doi) + '<span class="ext">\u2197</span></a></div>';
        }
        html += '<div class="meta">';
        html += '<span class="count"><b>' + totalConn + '</b> direct connection' + (totalConn === 1 ? "" : "s") + ' across ' + Object.keys(groups).length + ' concept' + (Object.keys(groups).length === 1 ? "" : "s") + '</span>';
        html += '<button class="dl-link" id="dl-csv" type="button">Download as CSV ↓</button>';
        html += '</div>';
        html += '</div>'; // .subject-text

        // specimen plate — Wikimedia photo (plants) or PubChem 2D structure (compounds)
        if (subject.role === "Plant" || subject.role === "Compound") {
          var capText = subject.role === "Plant" ? "Photograph · Wikimedia Commons" : "2D structure · PubChem";
          var fallText = subject.role === "Plant" ? "No specimen photograph found" : "No structure diagram found";
          html += '<figure class="subject-media is-loading" id="subject-media" data-kind="' + subject.role + '">'
                + '<div class="plate"><span class="plate-fallback">' + fallText + '</span>'
                + '<img alt="' + esc(subject.label) + '" referrerpolicy="no-referrer"></div>'
                + '<figcaption class="src-cap">' + capText + '</figcaption>'
                + '</figure>';
        }
        html += '</div>'; // .subject-top

        // ── recorded data properties (datatype attributes) ──
        if (subject.props && subject.props.length) {
          html += '<div class="attrs">';
          html += '<div class="attrs-head">Recorded attributes</div>';
          html += '<div class="attrs-list">';
          subject.props.forEach(function (pair) {
            html += '<div class="attrs-row"><div class="k">' + esc(pair[0]) + '</div><div class="v">' + esc(pair[1]) + '</div></div>';
          });
          html += '</div>';
          html += '</div>';
        }
        html += '</section>';

        // ── knowledge-graph view of this entity (shared graph.js) ──
        html += '<section class="reg-graph"><div class="reg-graph-cap" id="reg-graph-cap"></div><div class="reg-graph-canvas" id="reg-graph"></div></section>';

        // ── register groups ──
        html += '<section class="register">';
        if (!relations.length) {
          html += '<div class="reg-empty">No recorded connections for this entity yet.</div>';
        } else {
          ROLE_ORDER.forEach(function (role) {
            var rows = groups[role];
            if (!rows || !rows.length) return;
            var color = ROLE_COLOR[role] || ROLE_COLOR.Other;
            html += '<div class="reg-group">';
            html += '<div class="reg-group-head">'
                  + '<span class="swatch" style="background:' + color + '"></span>'
                  + '<span class="concept">' + esc(ROLE_LABEL[role] || role) + '</span>'
                  + '<span class="tally">' + rows.length + ' linked</span>'
                  + '</div>';

            // alphabetical within a concept for a true register feel
            rows.sort(function (a, b) { return NODES[a.id].label.localeCompare(NODES[b.id].label); });

            rows.forEach(function (rel) {
              var n = NODES[rel.id];
              var pred = P.prettyPredicate(rel.predicate);
              var arrow = rel.dir === "out" ? "▸" : "◂";
              var conn = P.connectionCount(rel.id);
              html += '<div class="reg-row">';
              html += '<div class="pred"><span class="arrow">' + arrow + '</span> ' + esc(pred) + '</div>';
              html += '<div class="name"><a class="name-link" href="Explore.html?q=' + encodeURIComponent(rel.id) + '">' + nameCell(n) + '</a>' + (doiLink(n) ? '<br>' + doiLink(n) : '') + geneTags(n) + '</div>';
              html += '<div class="conn"><span class="dot" style="background:' + color + '"></span>' + conn + ' connection' + (conn === 1 ? "" : "s") + '</div>';
              html += '</div>';
            });
            html += '</div>';
          });
        }
        html += '</section>';

        root.innerHTML = html;
        renderGraph(id, subject);
        window.scrollTo({ top: 0, behavior: "auto" });
        resolveMedia(subject);
      }

      // ── interactive knowledge graph for the focused entity (shared graph.js) ──
      function onGraphNode(nid) { if (NODES[nid]) render(nid); }   // refocus in-page
      function trimSub(sub, max) {   // cap neighbours so high-degree plants stay readable
        var c = sub.center, neigh = sub.nodes.filter(function (n) { return n.id !== c; });
        if (neigh.length <= max) return 0;
        neigh.sort(function (a, b) { return P.connectionCount(b.id) - P.connectionCount(a.id); });
        var keep = {}; keep[c] = true;
        neigh.slice(0, max).forEach(function (n) { keep[n.id] = true; });
        sub.nodes = sub.nodes.filter(function (n) { return keep[n.id]; });
        sub.edges = sub.edges.filter(function (e) { return keep[e.source] && keep[e.target]; });
        return neigh.length - max;
      }
      function renderGraph(id, subject) {
        var gc = document.getElementById("reg-graph"), cap = document.getElementById("reg-graph-cap");
        if (!gc || !window.POPPY_GRAPH) return;
        var sub = window.POPPY.neighborhood(id);
        if (!sub) { gc.innerHTML = ""; if (cap) cap.innerHTML = "No connections to graph yet."; return; }
        var total = sub.nodes.length - 1;
        var omitted = trimSub(sub, 32);
        window.POPPY_GRAPH.renderSubgraph(gc, sub, { onNodeClick: onGraphNode });
        if (cap) cap.innerHTML = 'Centered on <em>' + esc(subject.label) + '</em> · '
          + (omitted ? 'showing the ' + (total - omitted) + ' best-connected of ' + total + ' neighbours'
                     : sub.edges.length + ' relationship' + (sub.edges.length === 1 ? '' : 's'))
          + ' — click any circle to refocus.';
      }

      // ── specimen plate imagery (Explore page only, hot-linked, nothing stored) ──
      // Plants  → lead photograph via the MediaWiki pageimages API (Wikimedia Commons)
      // Compounds → 2D skeletal structure via the PubChem PUG REST image endpoint
      var IMG_CACHE_KEY = "poppy-explore-media";
      function imgCache() { try { return JSON.parse(localStorage.getItem(IMG_CACHE_KEY) || "{}"); } catch (e) { return {}; } }
      function saveImgCache(c) { try { localStorage.setItem(IMG_CACHE_KEY, JSON.stringify(c)); } catch (e) {} }

      function setPlate(fig, src) {
        if (!fig) return;
        var img = fig.querySelector("img");
        img.onload = function () { fig.classList.remove("is-loading"); fig.classList.add("has-img"); };
        img.onerror = function () { fig.classList.remove("is-loading"); }; // leaves the fallback note
        img.src = src;
      }

      function resolveMedia(subject) {
        var fig = document.getElementById("subject-media");
        if (!fig) return;

        // Compounds: PubChem renders a structure by chemical name directly — no
        // lookup round-trip needed, just point the <img> at the PUG REST endpoint.
        if (subject.role === "Compound") {
          var name = subject.pubchem || subject.label;
          setPlate(fig, "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
            + encodeURIComponent(name) + "/PNG");
          return;
        }

        // Plants: resolve the Wikipedia lead image (cached per entity).
        var cache = imgCache();
        var key = subject.id || subject.label;
        if (cache[key] === "none") { fig.classList.remove("is-loading"); return; }
        if (cache[key]) { setPlate(fig, cache[key]); return; }

        var title = subject.wiki || subject.label;
        var url = "https://en.wikipedia.org/w/api.php?action=query&format=json&origin=*"
                + "&redirects=1&prop=pageimages&piprop=thumbnail&pithumbsize=600&titles="
                + encodeURIComponent(title);
        fetch(url, { headers: { accept: "application/json" } })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (j) {
            var src = null;
            try { var pages = j.query.pages; var p = pages[Object.keys(pages)[0]]; src = p && p.thumbnail && p.thumbnail.source; } catch (e) {}
            if (src) { cache[key] = src; saveImgCache(cache); setPlate(fig, src); }
            else { cache[key] = "none"; saveImgCache(cache); fig.classList.remove("is-loading"); }
          })
          .catch(function () { fig.classList.remove("is-loading"); });
      }

      function renderEmpty() {
        root.innerHTML = '<section class="register"><div class="reg-empty">'
          + 'Look up an entity above to see its register of connections.</div></section>';
      }

      function lookup(q) {
        var query = (q || input.value || "").trim();
        if (!query) { msg.textContent = "Type a name to look up."; return; }
        var id = P.findByLabel(query);
        if (id) { render(id); return; }
        var matches = fullFindAll(query);
        if (matches.length === 0) { msg.textContent = 'No entry for "' + query + '".'; return; }
        if (matches.length === 1) { msg.textContent = ""; loadFullPlant(matches[0].r.id); return; }
        msg.textContent = "";
        renderDisambig(matches, query);
      }

      document.getElementById("reg-search-btn").addEventListener("click", function () { lookup(); });
      input.addEventListener("keydown", function (e) { if (e.key === "Enter") lookup(); });
      document.querySelectorAll(".reg-chips .chip").forEach(function (c) {
        c.addEventListener("click", function () { lookup(c.dataset.q); });
      });

      // keep the graph filling its container as the viewport changes
      var _grT;
      window.addEventListener("resize", function () {
        clearTimeout(_grT);
        _grT = setTimeout(function () {
          if (currentId && NODES[currentId]) renderGraph(currentId, NODES[currentId]);
        }, 200);
      });

      // initial: ?q= from the Home "Explore further" button, else a sensible default
      var q = null;
      try { q = new URLSearchParams(window.location.search).get("q"); } catch (e) {}
      var cur = q && P.findByLabel(q);
      if (cur) { render(cur); }
      else if (q) {
        // non-curated plant: show a loading state — NOT the default — and resolve via the index
        msg.textContent = "Loading " + q + "…";
        root.innerHTML = '<section class="register"><div class="reg-empty">Loading…</div></section>';
        var fid = fullFindPlant(q);                       // by name/id, once the index is ready
        if (fid) loadFullPlant(fid); else pendingQ = q;   // else resolve when plants_index loads
      } else { render("papaver-somniferum"); }
    })();
  
