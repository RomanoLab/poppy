    // ─── Real data layer — client-side slice generation (Phase 1) ─────
    // Slices are assembled in the browser from the sharded JSON in data/.
    // Phase 1: plants + compounds (+ their links); CSV and JSON-LD output.
    // No backend — the full graph (all formats) is the Box download above.
    function djb2(s){var h=5381;for(var i=0;i<s.length;i++){h=((h*33)^s.charCodeAt(i))&0xFFFFFFFF;}return h&255;}

    let PLANTS = [];                 // [{id, name, nc, trials, papers}]
    const META = { plants: 44769, compounds: 185041 };
    const edgeShardCache = {};       // shard -> {plantId: [compoundId,...]}
    const compShardCache = {};       // shard -> {compoundId: {name,formula,mw,inchikey,trials}}
    const plantEdges = {};           // plantId -> [compoundId,...] (loaded on demand)

    let plantsState = "loading";   // "loading" | "ready" | "error"
    fetch("data/plants_index.json")
      .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(a => { PLANTS = a; plantsState = "ready"; render(); })
      .catch(() => { plantsState = "error"; render(); });
    fetch("data/meta.json").then(r=>r.ok?r.json():null).then(m=>{ if(m){ META.plants=m.plants; META.compounds=m.compounds; render(); } }).catch(()=>{});

    // ─── State ────────────────────────────────────────────────────────
    const state = {
      entities: { plants: true, compounds: true },
      selectedPlants: [],            // [{id, name, nc}]
      format: "csv",
    };

    const FORMAT_LABELS = { jsonld: "JSON-LD", csv: "CSV (plant–compound table)" };

    // fetch a plant's compound-id list (cached by shard)
    async function getEdges(pid){
      if (plantEdges[pid]) return plantEdges[pid];
      const sh = djb2(pid);
      if (!edgeShardCache[sh]) edgeShardCache[sh] = await fetch(`data/plant_edges/${sh}.json`).then(r=>r.ok?r.json():{});
      return (plantEdges[pid] = edgeShardCache[sh][pid] || []);
    }
    // unique compound-id set across selected plants (edges must be preloaded)
    function sliceCompoundIds(){
      const set = new Set();
      for (const p of state.selectedPlants) (plantEdges[p.id]||[]).forEach(c=>set.add(c));
      return set;
    }
    // fetch compound records for a set of ids (cached by shard)
    async function getCompounds(ids){
      const byShard = {};
      ids.forEach(c=>{ const s=djb2(c); (byShard[s]=byShard[s]||[]).push(c); });
      const out = {};
      for (const s of Object.keys(byShard)){
        if (!compShardCache[s]) compShardCache[s] = await fetch(`data/compounds/${s}.json`).then(r=>r.ok?r.json():{});
        for (const c of byShard[s]) if (compShardCache[s][c]) out[c] = compShardCache[s][c];
      }
      return out;
    }

    // ─── Compute real slice counts ────────────────────────────────────
    function computeCounts() {
      if (state.selectedPlants.length === 0) {
        return { plants: META.plants, compounds: META.compounds, full: true };
      }
      const cids = sliceCompoundIds();
      return {
        plants: state.entities.plants ? state.selectedPlants.length : 0,
        compounds: state.entities.compounds ? cids.size : 0,
        full: false,
      };
    }
    // rough byte estimate from real counts (exact size is the generated Blob)
    function estBytes(r) {
      const per = state.format === "jsonld" ? 240 : 130;
      return (r.plants + r.compounds) * per;
    }

    function fmtBytes(b) {
      if (!b) return "0 B";
      if (b < 1024) return `~ ${Math.round(b)} B`;
      if (b < 1024 * 1024) return `~ ${(b / 1024).toFixed(1)} KB`;
      if (b < 1024 * 1024 * 1024) return `~ ${(b / 1024 / 1024).toFixed(1)} MB`;
      return `~ ${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
    }
    function fmtN(n) { return n.toLocaleString(); }

    // ─── Render ───────────────────────────────────────────────────────
    function render() {
      const r = computeCounts();
      document.getElementById("cnt-plants").textContent = state.entities.plants ? fmtN(r.plants) : "0";
      document.getElementById("cnt-compounds").textContent = state.entities.compounds ? fmtN(r.compounds) : "0";
      document.querySelector('.summary-row[data-row="plants"]').classList.toggle("disabled", !state.entities.plants);
      document.querySelector('.summary-row[data-row="compounds"]').classList.toggle("disabled", !state.entities.compounds);
      document.getElementById("cnt-size").textContent = r.full ? "full → use Box ↑" : fmtBytes(estBytes(r));
      document.getElementById("cnt-format").textContent = FORMAT_LABELS[state.format] || state.format;

      const dl = document.getElementById("download-btn");
      if (r.full) { dl.textContent = "Select plants to build a slice"; dl.classList.add("is-disabled"); }
      else { dl.textContent = "Download slice"; dl.classList.remove("is-disabled"); }

      // chips
      const chipsHost = document.getElementById("entity-chips");
      const chipsEmpty = document.getElementById("entity-chips-empty");
      chipsHost.innerHTML = "";
      for (const p of state.selectedPlants) {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.innerHTML = `<em>${p.name}</em><button data-remove="${p.id}" aria-label="remove">×</button>`;
        chipsHost.appendChild(chip);
      }
      chipsEmpty.style.display = state.selectedPlants.length ? "none" : "block";
    }

    // ─── Wire events ──────────────────────────────────────────────────
    // entity checkboxes
    document.querySelectorAll('input[name="entity"]').forEach((cb) => {
      cb.addEventListener("change", () => {
        state.entities[cb.value] = cb.checked;
        render();
      });
    });

    // plant typeahead
    const searchEl = document.getElementById("entity-search");
    const dropdown = document.getElementById("entity-dropdown");

    function renderDropdown(q) {
      // data not loaded yet → say why instead of silently showing nothing
      if (!PLANTS.length) {
        dropdown.innerHTML = `<div class="dropdown-empty">${
          plantsState === "error"
            ? "Couldn’t load the plant list. This page must be served over HTTP — open it through a web server, not as a file:// page."
            : "Loading the plant list…"
        }</div>`;
        dropdown.classList.add("open");
        return;
      }
      const query = q.toLowerCase().trim();
      const selectedIds = new Set(state.selectedPlants.map((p) => p.id));
      const matches = PLANTS
        .filter((p) => !selectedIds.has(p.id))
        .filter((p) => !query || p.name.toLowerCase().includes(query))
        .slice(0, 8);

      dropdown.innerHTML = "";
      if (!matches.length) {
        dropdown.innerHTML = `<div class="dropdown-empty">${query ? "No matches." : "Type a plant name…"}</div>`;
      } else {
        for (const p of matches) {
          const it = document.createElement("div");
          it.className = "dropdown-item";
          it.dataset.id = p.id;
          it.innerHTML = `
            <div>
              <div class="lat">${p.name}</div>
            </div>
            <div class="cnt">${(p.nc || 0).toLocaleString()} cmpds</div>`;
          dropdown.appendChild(it);
        }
      }
      dropdown.classList.add("open");
    }

    searchEl.addEventListener("focus", () => renderDropdown(searchEl.value));
    searchEl.addEventListener("input", () => renderDropdown(searchEl.value));
    searchEl.addEventListener("blur", () => {
      // delay so a click on a dropdown item registers first
      setTimeout(() => dropdown.classList.remove("open"), 150);
    });
    dropdown.addEventListener("mousedown", (e) => {
      const it = e.target.closest(".dropdown-item");
      if (!it) return;
      e.preventDefault();
      const id = it.dataset.id;
      const p = PLANTS.find((x) => x.id === id);
      if (p && !state.selectedPlants.find((x) => x.id === id)) {
        state.selectedPlants.push(p);
        searchEl.value = "";
        renderDropdown("");
        render();
        getEdges(p.id).then(render);   // load this plant's compounds, then refresh counts
      }
    });

    // chip remove
    document.getElementById("entity-chips").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-remove]");
      if (!btn) return;
      const id = btn.dataset.remove;
      state.selectedPlants = state.selectedPlants.filter((p) => p.id !== id);
      render();
    });

    // format chips (RDF formats are Phase 2 → marked .is-disabled, ignored)
    document.getElementById("formats").addEventListener("click", (e) => {
      const chip = e.target.closest(".format-chip");
      if (!chip || chip.classList.contains("is-disabled")) return;
      document.querySelectorAll(".format-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.format = chip.dataset.format;
      render();
    });

    // ─── Download — client-side slice generation ──────────────────────
    document.getElementById("download-btn").addEventListener("click", async () => {
      const dl = document.getElementById("download-btn");
      if (state.selectedPlants.length === 0) {
        alert("Select one or more plants to build a slice — or use “Download full ontology (RDF · Box)” above for the complete graph.");
        return;
      }
      const label = dl.textContent;
      dl.textContent = "Building…";
      dl.classList.add("is-disabled");
      try {
        for (const p of state.selectedPlants) await getEdges(p.id);
        const cidSet = sliceCompoundIds();
        const comps = state.entities.compounds ? await getCompounds(cidSet) : {};
        const [blob, fname] = state.format === "jsonld" ? buildJSONLD(comps) : buildCSV(comps);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = fname;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 4000);
      } catch (err) {
        alert("Sorry — slice generation failed: " + (err && err.message ? err.message : err));
      } finally {
        dl.textContent = label;
        dl.classList.remove("is-disabled");
      }
    });

    function csvCell(v) { v = (v == null ? "" : String(v)); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
    function buildCSV(comps) {
      const rows = [["plant_id", "plant_name", "compound_id", "compound_name", "formula", "molecular_weight", "inchikey", "compound_trials"].join(",")];
      for (const p of state.selectedPlants) {
        for (const cid of (plantEdges[p.id] || [])) {
          const c = comps[cid] || {};
          rows.push([p.id, p.name, cid, c.name, c.formula, c.mw, c.inchikey, c.trials].map(csvCell).join(","));
        }
      }
      return [new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" }), "poppy-slice.csv"];
    }
    function buildJSONLD(comps) {
      const graph = [];
      for (const p of state.selectedPlants) {
        graph.push({ "@id": "poppy:" + p.id, "@type": "Plant", "label": p.name,
                     "producesCompound": (plantEdges[p.id] || []).map((c) => "poppy:" + c) });
      }
      const seen = new Set();
      for (const p of state.selectedPlants) for (const cid of (plantEdges[p.id] || [])) {
        if (seen.has(cid)) continue; seen.add(cid);
        const c = comps[cid] || {};
        graph.push({ "@id": "poppy:" + cid, "@type": "Chemical", "label": c.name,
                     "formula": c.formula, "molecularWeight": c.mw, "inchikey": c.inchikey });
      }
      const doc = { "@context": {
          "poppy": "https://poppyontology.org/id/",
          "label": "http://www.w3.org/2000/01/rdf-schema#label",
          "producesCompound": { "@id": "https://poppyontology.org/prop/producesCompound", "@type": "@id" },
          "formula": "https://poppyontology.org/prop/formula",
          "molecularWeight": "https://poppyontology.org/prop/molecularWeight",
          "inchikey": "https://poppyontology.org/prop/inchikey"
        }, "@graph": graph };
      return [new Blob([JSON.stringify(doc, null, 2)], { type: "application/ld+json" }), "poppy-slice.jsonld"];
    }

    render();
  
