/* ============================================================================
 * POPPy — shared ontology data + graph helpers   (window.POPPY)
 * ----------------------------------------------------------------------------
 * This is the SINGLE source of truth for the connection graph shown on the
 * Home page and the register listed on the Explore page.
 *
 * To wire up the real ontology later, replace NODES and EDGES below (or assign
 * window.POPPY.NODES / window.POPPY.EDGES before the pages run). Keep the same
 * shape:
 *     NODES[id] = { label, role, common?, props? }
 *       role  ∈ "Plant" | "Compound" | "Target" | "Effect" | "Citation"
 *       props = ordered list of [ propertyLabel, value ] pairs — the entity's
 *               data/datatype properties (hasMolecularFormula, hasGeography, …).
 *               Rendered automatically in the Explore subject block; omit or
 *               leave empty and the attributes panel simply doesn't appear.
 *     EDGES = [ { s: sourceId, t: targetId, p: predicate }, … ]   ← the connections
 *
 * Everything else (colours, display names, neighbourhood expansion, search)
 * derives from those two structures.
 * ==========================================================================*/
(function () {
  "use strict";

  // Internal role  →  on-screen concept colour
  var ROLE_COLOR = {
    Plant: "#009E73", Compound: "#0072B2", Target: "#E69F00",
    Effect: "#CC79A7", Citation: "#777", Other: "#888"
  };

  // Internal role  →  display name used in the UI (matches the graph legend)
  var ROLE_LABEL = {
    Plant: "Plant", Compound: "Chemical", Target: "Target",
    Effect: "Therapeutic", Citation: "Research", Other: "Other"
  };

  // Order concepts appear in the Explore register
  var ROLE_ORDER = ["Plant", "Compound", "Target", "Effect", "Citation", "Other"];

  var NODES = {
    // PLANTS
    "papaver-somniferum": { label: "Papaver somniferum", role: "Plant", common: "Opium poppy", props: [
      ["hasFamily", "Papaveraceae"],
      ["hasGeography", "Western Mediterranean; cultivated worldwide"],
      ["hasPartUsed", "Latex of the unripe capsule"]
    ] },
    "papaver-rhoeas":     { label: "Papaver rhoeas",     role: "Plant", common: "Corn poppy" },
    "curcuma-longa":      { label: "Curcuma longa",      role: "Plant", common: "Turmeric" },
    "salvia-officinalis": { label: "Salvia officinalis", role: "Plant", common: "Common sage" },
    "withania-somnifera": { label: "Withania somnifera", role: "Plant", common: "Ashwagandha" },
    "digitalis-purpurea":   { label: "Digitalis purpurea",   role: "Plant", common: "Foxglove", props: [
      ["hasFamily", "Plantaginaceae"],
      ["hasGeography", "Western & central Europe"],
      ["hasPartUsed", "Dried leaf"]
    ] },
    "camellia-thea":        { label: "Camellia thea",        role: "Plant", common: "Tea" },
    "nicotiana-tabacum":    { label: "Nicotiana tabacum",    role: "Plant", common: "Tobacco" },
    "cinnamomum-zeylanicum":{ label: "Cinnamomum zeylanicum",role: "Plant", common: "Ceylon cinnamon" },
    "datura-stramonium":    { label: "Datura stramonium",    role: "Plant", common: "Jimsonweed" },
    "croton-tiglium":       { label: "Croton tiglium",       role: "Plant", common: "Purging croton" },
    "rosa-centifolia":      { label: "Rosa centifolia",      role: "Plant", common: "Cabbage rose" },
    "citrus-limonum":       { label: "Citrus limonum",       role: "Plant", common: "Lemon" },
    "ipomoea-purga":        { label: "Ipomoea purga",        role: "Plant", common: "Jalap" },
    "verbascum-phlomoides": { label: "Verbascum phlomoides", role: "Plant", common: "Orange mullein" },
    "inula-helenium":       { label: "Inula helenium",       role: "Plant", common: "Elecampane" },
    "tussilago-farfara":    { label: "Tussilago farfara",    role: "Plant", common: "Coltsfoot" },
    "levisticum-officinale":{ label: "Levisticum officinale",role: "Plant", common: "Lovage" },
    "anacyclus-pyrethrum":  { label: "Anacyclus pyrethrum",  role: "Plant", common: "Pellitory" },
    "erythraea-centaurium": { label: "Erythraea centaurium", role: "Plant", common: "Common centaury" },
    "citrus-vulgaris":      { label: "Citrus vulgaris",      role: "Plant", common: "Bitter orange" },
    "rubus-idaeus":         { label: "Rubus idaeus",         role: "Plant", common: "Raspberry" },
    "prunus-cerasus":       { label: "Prunus cerasus",       role: "Plant", common: "Sour cherry" },
    "pirus-malus":          { label: "Pirus malus",          role: "Plant", common: "Apple" },
    "cydonia-vulgaris":     { label: "Cydonia vulgaris",     role: "Plant", common: "Quince" },
    "quercus-sessiliflora": { label: "Quercus sessiliflora", role: "Plant", common: "Sessile oak" },
    "cnicus-benedictus":    { label: "Cnicus benedictus",    role: "Plant", common: "Blessed thistle" },
    "chrysanthemum-roseum": { label: "Chrysanthemum roseum", role: "Plant", common: "Painted daisy" },
    // COMPOUNDS
    "morphine":          { label: "Morphine",          role: "Compound", props: [
      ["hasMolecularFormula", "C\u2081\u2087H\u2081\u2089NO\u2083"],
      ["hasMolecularWeight", "285.34 g/mol"],
      ["hasSmiles", "CN1CC[C@]23c4c5ccc(O)c4O[C@H]2[C@@H](O)C=C[C@H]3[C@H]1C5"]
    ] },
    "codeine":           { label: "Codeine",           role: "Compound" },
    "papaverine":        { label: "Papaverine",        role: "Compound" },
    "thebaine":          { label: "Thebaine",          role: "Compound" },
    "noscapine":         { label: "Noscapine",         role: "Compound" },
    "curcumin":          { label: "Curcumin",          role: "Compound" },
    "demethoxycurcumin": { label: "Demethoxycurcumin", role: "Compound" },
    "ar-turmerone":      { label: "ar-Turmerone",      role: "Compound" },
    "carnosic-acid":     { label: "Carnosic acid",     role: "Compound" },
    "thujone":           { label: "Thujone",           role: "Compound" },
    "rosmarinic-acid":   { label: "Rosmarinic acid",   role: "Compound" },
    "withanolide-a":     { label: "Withanolide A",     role: "Compound" },
    "withaferin-a":      { label: "Withaferin A",      role: "Compound" },
    "withanone":         { label: "Withanone",         role: "Compound" },
    "digoxin":           { label: "Digoxin",           role: "Compound" },
    "digitoxin":         { label: "Digitoxin",         role: "Compound" },
    "caffeine":          { label: "Caffeine",          role: "Compound", props: [
      ["hasMolecularFormula", "C\u2088H\u2081\u2080N\u2084O\u2082"],
      ["hasMolecularWeight", "194.19 g/mol"]
    ] },
    "egcg":              { label: "Epigallocatechin gallate", role: "Compound" },
    "l-theanine":        { label: "L-Theanine",        role: "Compound" },
    "nicotine":          { label: "Nicotine",          role: "Compound" },
    "cinnamaldehyde":    { label: "Cinnamaldehyde",    role: "Compound" },
    "eugenol":           { label: "Eugenol",           role: "Compound" },
    "atropine":          { label: "Atropine",          role: "Compound" },
    "scopolamine":       { label: "Scopolamine",       role: "Compound" },
    "hyoscyamine":       { label: "Hyoscyamine",       role: "Compound" },
    "phorbol":           { label: "Phorbol",           role: "Compound" },
    "crotonoside":       { label: "Crotonoside",       role: "Compound" },
    "citronellol":       { label: "Citronellol",       role: "Compound" },
    "geraniol":          { label: "Geraniol",          role: "Compound" },
    "limonene":          { label: "Limonene",          role: "Compound" },
    "hesperidin":        { label: "Hesperidin",        role: "Compound" },
    "ascorbic-acid":     { label: "Ascorbic acid",     role: "Compound" },
    "convolvulin":       { label: "Convolvulin",       role: "Compound" },
    "jalapin":           { label: "Jalapin",           role: "Compound" },
    "verbascoside":      { label: "Verbascoside",      role: "Compound" },
    "alantolactone":     { label: "Alantolactone",     role: "Compound" },
    "inulin":            { label: "Inulin",            role: "Compound" },
    "tussilagine":       { label: "Tussilagine",       role: "Compound" },
    "senkirkine":        { label: "Senkirkine",        role: "Compound" },
    "ligustilide":       { label: "Ligustilide",       role: "Compound" },
    "pellitorine":       { label: "Pellitorine",       role: "Compound" },
    "gentiopicroside":   { label: "Gentiopicroside",   role: "Compound" },
    "swertiamarin":      { label: "Swertiamarin",      role: "Compound" },
    "synephrine":        { label: "Synephrine",        role: "Compound" },
    "ellagic-acid":      { label: "Ellagic acid",      role: "Compound" },
    "raspberry-ketone":  { label: "Raspberry ketone",  role: "Compound" },
    "anthocyanins":      { label: "Anthocyanins",      role: "Compound" },
    "amygdalin":         { label: "Amygdalin",         role: "Compound" },
    "quercetin":         { label: "Quercetin",         role: "Compound" },
    "phloridzin":        { label: "Phloridzin",        role: "Compound" },
    "quercitannic-acid": { label: "Quercitannic acid", role: "Compound" },
    "pectin":            { label: "Pectin",            role: "Compound" },
    "cnicin":            { label: "Cnicin",            role: "Compound" },
    "pyrethrin-i":       { label: "Pyrethrin I",       role: "Compound" },
    "pyrethrin-ii":      { label: "Pyrethrin II",      role: "Compound" },
    // TARGETS
    "mor":      { label: "μ-opioid receptor",     role: "Target" },
    "dor":      { label: "δ-opioid receptor",     role: "Target" },
    "pde10a":   { label: "PDE10A",                role: "Target" },
    "cox2":     { label: "COX-2",                 role: "Target", props: [
      ["hasGene", "PTGS2"],
      ["hasProtein", "Prostaglandin G/H synthase 2"],
      ["hasUniProt", "P35354"]
    ] },
    "nfkb":     { label: "NF-κB",                 role: "Target", props: [
      ["hasGene", "NFKB1"],
      ["hasProtein", "Nuclear factor NF-kappa-B p105 subunit"],
      ["hasUniProt", "P19838"]
    ] },
    "5lox":     { label: "5-LOX",                 role: "Target" },
    "ache":     { label: "Acetylcholinesterase",  role: "Target", props: [
      ["hasGene", "ACHE"],
      ["hasProtein", "Acetylcholinesterase"],
      ["hasUniProt", "P22303"]
    ] },
    "gabaa":    { label: "GABA-A receptor",       role: "Target" },
    "vimentin": { label: "Vimentin",              role: "Target" },
    "nak-atpase":  { label: "Na\u207a/K\u207a-ATPase",            role: "Target" },
    "adenosine-r": { label: "Adenosine A\u2082\u2090 receptor",   role: "Target" },
    "nachr":       { label: "Nicotinic ACh receptor",   role: "Target" },
    "machr":       { label: "Muscarinic ACh receptor",  role: "Target" },
    "trpa1":       { label: "TRPA1 channel",            role: "Target" },
    "pkc":         { label: "Protein kinase C",         role: "Target" },
    "adra":        { label: "\u03b1-adrenergic receptor",  role: "Target" },
    "sglt2":       { label: "SGLT2 transporter",        role: "Target", props: [
      ["hasGene", "SLC5A2"],
      ["hasProtein", "Sodium/glucose cotransporter 2"],
      ["hasUniProt", "P31639"]
    ] },
    "vgsc":        { label: "Voltage-gated Na\u207a channel", role: "Target" },
    // EFFECTS
    "analgesia":         { label: "Analgesia",         role: "Effect" },
    "sedation":          { label: "Sedation",          role: "Effect" },
    "antitussive":       { label: "Antitussive",       role: "Effect" },
    "vasodilation":      { label: "Vasodilation",      role: "Effect" },
    "anti-inflammatory": { label: "Anti-inflammatory", role: "Effect" },
    "cognitive-support": { label: "Cognitive support", role: "Effect" },
    "adaptogenic":       { label: "Adaptogenic",       role: "Effect" },
    "antineoplastic":    { label: "Antineoplastic",    role: "Effect" },
    "anxiolytic":        { label: "Anxiolytic",        role: "Effect" },
    "cardiotonic":       { label: "Cardiotonic",       role: "Effect" },
    "stimulant":         { label: "Stimulant",         role: "Effect" },
    "antispasmodic":     { label: "Antispasmodic",     role: "Effect" },
    "antimicrobial":     { label: "Antimicrobial",     role: "Effect" },
    "antioxidant":       { label: "Antioxidant",       role: "Effect" },
    "expectorant":       { label: "Expectorant",       role: "Effect" },
    "astringent":        { label: "Astringent",        role: "Effect" },
    "bitter-tonic":      { label: "Bitter tonic",      role: "Effect" },
    "purgative":         { label: "Purgative",         role: "Effect" },
    "insecticidal":      { label: "Insecticidal",      role: "Effect" },
    "demulcent":         { label: "Demulcent",         role: "Effect" },
    "hypoglycemic":      { label: "Hypoglycemic",      role: "Effect" },
    // CITATIONS  (doi → resolves at https://doi.org/<doi>)
    "pasternak2021": { label: "Pasternak, 2021",     role: "Citation", doi: "10.1124/pharmrev.120.000083" },
    "khanna2024":    { label: "Khanna et al., 2024", role: "Citation", doi: "10.1038/s41586-024-07251-0" },
    "stein2020":     { label: "Stein, 2020",         role: "Citation", doi: "10.1056/NEJMra1807197" },
    "kumar2018":     { label: "Kumar et al., 2018",  role: "Citation", doi: "10.1016/j.cell.2018.03.001", props: [
      ["hasJournal", "Cell"],
      ["hasYear", "2018"],
      ["hasTitle", "Curcumin modulation of NF-\u03baB signalling in inflammation"]
    ] },
    "ramirez2022":   { label: "Ramirez, 2022",       role: "Citation", doi: "10.1021/acs.jnatprod.2c00135" },
    "gupta2019":     { label: "Gupta, 2019",         role: "Citation", doi: "10.1186/s13020-019-0270-9" },
    "withering1985": { label: "Withering (rev.), 1985", role: "Citation", doi: "10.1161/01.cir.72.6.1170" },
    "tanaka2021":    { label: "Tanaka et al., 2021",  role: "Citation", doi: "10.3390/molecules26010085" },
    "obrien2017":    { label: "O'Brien, 2017",        role: "Citation", doi: "10.1016/j.neuropharm.2017.04.003" },
    "lindqvist2023": { label: "Lindqvist et al., 2023", role: "Citation", doi: "10.1021/acs.jnatprod.3c00045" }
  };

  var EDGES = [
    { s: "papaver-somniferum", t: "morphine",          p: "hasCompound" },
    { s: "papaver-somniferum", t: "codeine",           p: "hasCompound" },
    { s: "papaver-somniferum", t: "papaverine",        p: "hasCompound" },
    { s: "papaver-somniferum", t: "thebaine",          p: "hasCompound" },
    { s: "papaver-somniferum", t: "noscapine",         p: "hasCompound" },
    { s: "papaver-rhoeas",     t: "morphine",          p: "hasCompound" },
    { s: "curcuma-longa",      t: "curcumin",          p: "hasCompound" },
    { s: "curcuma-longa",      t: "demethoxycurcumin", p: "hasCompound" },
    { s: "curcuma-longa",      t: "ar-turmerone",      p: "hasCompound" },
    { s: "salvia-officinalis", t: "carnosic-acid",     p: "hasCompound" },
    { s: "salvia-officinalis", t: "thujone",           p: "hasCompound" },
    { s: "salvia-officinalis", t: "rosmarinic-acid",   p: "hasCompound" },
    { s: "withania-somnifera", t: "withanolide-a",     p: "hasCompound" },
    { s: "withania-somnifera", t: "withaferin-a",      p: "hasCompound" },
    { s: "withania-somnifera", t: "withanone",         p: "hasCompound" },
    { s: "morphine",        t: "mor",      p: "targets" },
    { s: "morphine",        t: "dor",      p: "targets" },
    { s: "codeine",         t: "mor",      p: "targets" },
    { s: "papaverine",      t: "pde10a",   p: "targets" },
    { s: "curcumin",        t: "cox2",     p: "targets" },
    { s: "curcumin",        t: "nfkb",     p: "targets" },
    { s: "ar-turmerone",    t: "5lox",     p: "targets" },
    { s: "carnosic-acid",   t: "ache",     p: "targets" },
    { s: "thujone",         t: "gabaa",    p: "targets" },
    { s: "rosmarinic-acid", t: "cox2",     p: "targets" },
    { s: "withanolide-a",   t: "nfkb",     p: "targets" },
    { s: "withaferin-a",    t: "vimentin", p: "targets" },
    { s: "withanone",       t: "gabaa",    p: "targets" },
    { s: "morphine",        t: "analgesia",         p: "produces" },
    { s: "morphine",        t: "sedation",          p: "produces" },
    { s: "codeine",         t: "analgesia",         p: "produces" },
    { s: "codeine",         t: "antitussive",       p: "produces" },
    { s: "papaverine",      t: "vasodilation",      p: "produces" },
    { s: "curcumin",        t: "anti-inflammatory", p: "produces" },
    { s: "ar-turmerone",    t: "anti-inflammatory", p: "produces" },
    { s: "carnosic-acid",   t: "cognitive-support", p: "produces" },
    { s: "thujone",         t: "sedation",          p: "produces" },
    { s: "rosmarinic-acid", t: "anti-inflammatory", p: "produces" },
    { s: "withanolide-a",   t: "adaptogenic",       p: "produces" },
    { s: "withaferin-a",    t: "antineoplastic",    p: "produces" },
    { s: "withanone",       t: "anxiolytic",        p: "produces" },
    { s: "morphine",      t: "pasternak2021", p: "citedIn" },
    { s: "morphine",      t: "khanna2024",    p: "citedIn" },
    { s: "codeine",       t: "pasternak2021", p: "citedIn" },
    { s: "papaverine",    t: "stein2020",     p: "citedIn" },
    { s: "curcumin",      t: "kumar2018",     p: "citedIn" },
    { s: "curcumin",      t: "ramirez2022",   p: "citedIn" },
    { s: "carnosic-acid", t: "ramirez2022",   p: "citedIn" },
    { s: "withanolide-a", t: "gupta2019",     p: "citedIn" },

    // ── featured-species connections (illustrative; replaced by the real ontology) ──
    { s: "digitalis-purpurea", t: "digoxin",   p: "hasCompound" },
    { s: "digitalis-purpurea", t: "digitoxin", p: "hasCompound" },
    { s: "digoxin",   t: "nak-atpase", p: "targets" },
    { s: "digitoxin", t: "nak-atpase", p: "targets" },
    { s: "digoxin",   t: "cardiotonic", p: "produces" },
    { s: "digitoxin", t: "cardiotonic", p: "produces" },
    { s: "digoxin",   t: "withering1985", p: "citedIn" },

    { s: "camellia-thea", t: "caffeine",   p: "hasCompound" },
    { s: "camellia-thea", t: "egcg",       p: "hasCompound" },
    { s: "camellia-thea", t: "l-theanine", p: "hasCompound" },
    { s: "caffeine",   t: "adenosine-r", p: "targets" },
    { s: "caffeine",   t: "stimulant",        p: "produces" },
    { s: "caffeine",   t: "cognitive-support", p: "produces" },
    { s: "caffeine",   t: "tanaka2021", p: "citedIn" },
    { s: "egcg",       t: "nfkb",       p: "targets" },
    { s: "egcg",       t: "antioxidant",       p: "produces" },
    { s: "egcg",       t: "anti-inflammatory", p: "produces" },
    { s: "l-theanine", t: "gabaa",      p: "targets" },
    { s: "l-theanine", t: "anxiolytic", p: "produces" },

    { s: "nicotiana-tabacum", t: "nicotine", p: "hasCompound" },
    { s: "nicotine", t: "nachr",     p: "targets" },
    { s: "nicotine", t: "stimulant", p: "produces" },
    { s: "nicotine", t: "obrien2017", p: "citedIn" },

    { s: "cinnamomum-zeylanicum", t: "cinnamaldehyde", p: "hasCompound" },
    { s: "cinnamomum-zeylanicum", t: "eugenol",        p: "hasCompound" },
    { s: "cinnamaldehyde", t: "trpa1",        p: "targets" },
    { s: "cinnamaldehyde", t: "antimicrobial", p: "produces" },
    { s: "eugenol",        t: "cox2",         p: "targets" },
    { s: "eugenol",        t: "analgesia",     p: "produces" },
    { s: "eugenol",        t: "antimicrobial", p: "produces" },

    { s: "datura-stramonium", t: "atropine",    p: "hasCompound" },
    { s: "datura-stramonium", t: "scopolamine", p: "hasCompound" },
    { s: "datura-stramonium", t: "hyoscyamine", p: "hasCompound" },
    { s: "atropine",    t: "machr", p: "targets" },
    { s: "scopolamine", t: "machr", p: "targets" },
    { s: "hyoscyamine", t: "machr", p: "targets" },
    { s: "atropine",    t: "antispasmodic", p: "produces" },
    { s: "scopolamine", t: "sedation",      p: "produces" },
    { s: "hyoscyamine", t: "antispasmodic", p: "produces" },
    { s: "atropine",    t: "stein2020",     p: "citedIn" },

    { s: "croton-tiglium", t: "phorbol",     p: "hasCompound" },
    { s: "croton-tiglium", t: "crotonoside", p: "hasCompound" },
    { s: "phorbol",     t: "pkc",       p: "targets" },
    { s: "phorbol",     t: "purgative", p: "produces" },
    { s: "crotonoside", t: "purgative", p: "produces" },

    { s: "rosa-centifolia", t: "citronellol", p: "hasCompound" },
    { s: "rosa-centifolia", t: "geraniol",    p: "hasCompound" },
    { s: "citronellol", t: "antimicrobial", p: "produces" },
    { s: "geraniol",    t: "antimicrobial", p: "produces" },
    { s: "geraniol",    t: "antioxidant",   p: "produces" },

    { s: "citrus-limonum", t: "limonene",      p: "hasCompound" },
    { s: "citrus-limonum", t: "hesperidin",    p: "hasCompound" },
    { s: "citrus-limonum", t: "ascorbic-acid", p: "hasCompound" },
    { s: "limonene",     t: "antineoplastic", p: "produces" },
    { s: "limonene",     t: "antioxidant",    p: "produces" },
    { s: "hesperidin",   t: "cox2",           p: "targets" },
    { s: "hesperidin",   t: "anti-inflammatory", p: "produces" },
    { s: "ascorbic-acid", t: "antioxidant",   p: "produces" },

    { s: "ipomoea-purga", t: "convolvulin", p: "hasCompound" },
    { s: "ipomoea-purga", t: "jalapin",     p: "hasCompound" },
    { s: "convolvulin", t: "purgative", p: "produces" },
    { s: "jalapin",     t: "purgative", p: "produces" },

    { s: "verbascum-phlomoides", t: "verbascoside", p: "hasCompound" },
    { s: "verbascoside", t: "nfkb",        p: "targets" },
    { s: "verbascoside", t: "anti-inflammatory", p: "produces" },
    { s: "verbascoside", t: "expectorant", p: "produces" },

    { s: "inula-helenium", t: "alantolactone", p: "hasCompound" },
    { s: "inula-helenium", t: "inulin",        p: "hasCompound" },
    { s: "alantolactone", t: "antimicrobial", p: "produces" },
    { s: "alantolactone", t: "expectorant",   p: "produces" },
    { s: "inulin",        t: "demulcent",     p: "produces" },

    { s: "tussilago-farfara", t: "tussilagine", p: "hasCompound" },
    { s: "tussilago-farfara", t: "senkirkine",  p: "hasCompound" },
    { s: "tussilagine", t: "expectorant", p: "produces" },
    { s: "senkirkine",  t: "expectorant", p: "produces" },

    { s: "levisticum-officinale", t: "ligustilide", p: "hasCompound" },
    { s: "ligustilide", t: "antispasmodic", p: "produces" },
    { s: "ligustilide", t: "vasodilation",  p: "produces" },

    { s: "anacyclus-pyrethrum", t: "pellitorine", p: "hasCompound" },
    { s: "pellitorine", t: "analgesia", p: "produces" },

    { s: "erythraea-centaurium", t: "gentiopicroside", p: "hasCompound" },
    { s: "erythraea-centaurium", t: "swertiamarin",    p: "hasCompound" },
    { s: "gentiopicroside", t: "bitter-tonic", p: "produces" },
    { s: "swertiamarin",    t: "bitter-tonic", p: "produces" },
    { s: "swertiamarin",    t: "anti-inflammatory", p: "produces" },

    { s: "citrus-vulgaris", t: "synephrine", p: "hasCompound" },
    { s: "citrus-vulgaris", t: "hesperidin", p: "hasCompound" },
    { s: "synephrine", t: "adra",      p: "targets" },
    { s: "synephrine", t: "stimulant", p: "produces" },

    { s: "rubus-idaeus", t: "ellagic-acid",     p: "hasCompound" },
    { s: "rubus-idaeus", t: "raspberry-ketone", p: "hasCompound" },
    { s: "ellagic-acid",     t: "antioxidant",    p: "produces" },
    { s: "ellagic-acid",     t: "antineoplastic", p: "produces" },
    { s: "raspberry-ketone", t: "antioxidant",    p: "produces" },

    { s: "prunus-cerasus", t: "anthocyanins", p: "hasCompound" },
    { s: "prunus-cerasus", t: "amygdalin",    p: "hasCompound" },
    { s: "anthocyanins", t: "antioxidant",       p: "produces" },
    { s: "anthocyanins", t: "anti-inflammatory", p: "produces" },
    { s: "amygdalin",    t: "antitussive",       p: "produces" },
    { s: "anthocyanins", t: "lindqvist2023",     p: "citedIn" },

    { s: "pirus-malus", t: "quercetin",  p: "hasCompound" },
    { s: "pirus-malus", t: "phloridzin", p: "hasCompound" },
    { s: "quercetin",  t: "cox2",        p: "targets" },
    { s: "quercetin",  t: "antioxidant", p: "produces" },
    { s: "quercetin",  t: "anti-inflammatory", p: "produces" },
    { s: "phloridzin", t: "sglt2",       p: "targets" },
    { s: "phloridzin", t: "hypoglycemic", p: "produces" },

    { s: "cydonia-vulgaris", t: "amygdalin", p: "hasCompound" },
    { s: "cydonia-vulgaris", t: "pectin",    p: "hasCompound" },
    { s: "pectin", t: "demulcent", p: "produces" },

    { s: "quercus-sessiliflora", t: "quercitannic-acid", p: "hasCompound" },
    { s: "quercus-sessiliflora", t: "quercetin",         p: "hasCompound" },
    { s: "quercitannic-acid", t: "astringent",    p: "produces" },
    { s: "quercitannic-acid", t: "antimicrobial", p: "produces" },

    { s: "cnicus-benedictus", t: "cnicin", p: "hasCompound" },
    { s: "cnicin", t: "bitter-tonic",  p: "produces" },
    { s: "cnicin", t: "antimicrobial", p: "produces" },

    { s: "chrysanthemum-roseum", t: "pyrethrin-i",  p: "hasCompound" },
    { s: "chrysanthemum-roseum", t: "pyrethrin-ii", p: "hasCompound" },
    { s: "pyrethrin-i",  t: "vgsc",         p: "targets" },
    { s: "pyrethrin-ii", t: "vgsc",         p: "targets" },
    { s: "pyrethrin-i",  t: "insecticidal", p: "produces" },
    { s: "pyrethrin-ii", t: "insecticidal", p: "produces" }
  ];

  // ── helpers (read NODES/EDGES through the live window.POPPY object so a
  //    later data swap is picked up without re-binding) ───────────────────────
  function D() { return window.POPPY; }

  // total number of relationships touching an entity (its degree in the graph)
  function connectionCount(id) {
    var E = D().EDGES, n = 0;
    for (var i = 0; i < E.length; i++) if (E[i].s === id || E[i].t === id) n++;
    return n;
  }

  // the connected sub-graph around an entity (2 hops, so all concept types show)
  function neighborhood(centerId) {
    var N = D().NODES, E = D().EDGES;
    var center = N[centerId];
    if (!center) return null;
    var visited = {};
    visited[centerId] = true;
    function expand(id) {
      for (var i = 0; i < E.length; i++) {
        if (E[i].s === id) visited[E[i].t] = true;
        if (E[i].t === id) visited[E[i].s] = true;
      }
    }
    expand(centerId);
    var ring = Object.keys(visited);
    for (var r = 0; r < ring.length; r++) if (ring[r] !== centerId) expand(ring[r]);

    var ids = Object.keys(visited).filter(function (id) { return N[id]; });
    var nodes = ids.map(function (id) {
      var o = { id: id }; for (var k in N[id]) o[k] = N[id][k]; return o;
    });
    var edges = E.filter(function (e) { return visited[e.s] && visited[e.t]; })
      .map(function (e, i) {
        return { id: "e" + i + "-" + e.s + "-" + e.t, source: e.s, target: e.t, predicate: e.p };
      });
    return { center: centerId, label: center.label, common: center.common, role: center.role, nodes: nodes, edges: edges };
  }

  // direct relationships of an entity, each annotated with direction + the
  // predicate phrase — used to build the Explore register
  function relationsOf(centerId) {
    var N = D().NODES, E = D().EDGES;
    if (!N[centerId]) return [];
    var out = [];
    for (var i = 0; i < E.length; i++) {
      var e = E[i];
      if (e.s === centerId && N[e.t]) out.push({ id: e.t, predicate: e.p, dir: "out" });
      else if (e.t === centerId && N[e.s]) out.push({ id: e.s, predicate: e.p, dir: "in" });
    }
    // de-dupe (same neighbour reachable by >1 predicate keeps the first)
    var seen = {}, uniq = [];
    for (var j = 0; j < out.length; j++) { if (!seen[out[j].id]) { seen[out[j].id] = true; uniq.push(out[j]); } }
    return uniq;
  }

  function findByLabel(query) {
    var N = D().NODES;
    var q = String(query || "").toLowerCase().trim();
    if (!q) return null;
    if (N[q]) return q;                       // allow raw id (used by ?q= links)
    var id;
    for (id in N) {
      if (N[id].label.toLowerCase() === q) return id;
      if (N[id].common && N[id].common.toLowerCase() === q) return id;
    }
    for (id in N) {
      if (N[id].label.toLowerCase().indexOf(q) !== -1) return id;
      if (N[id].common && N[id].common.toLowerCase().indexOf(q) !== -1) return id;
    }
    return null;
  }

  function prettyPredicate(p) {
    return String(p || "").replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
  }

  window.POPPY = {
    NODES: NODES,
    EDGES: EDGES,
    ROLE_COLOR: ROLE_COLOR,
    ROLE_LABEL: ROLE_LABEL,
    ROLE_ORDER: ROLE_ORDER,
    connectionCount: connectionCount,
    neighborhood: neighborhood,
    relationsOf: relationsOf,
    findByLabel: findByLabel,
    prettyPredicate: prettyPredicate
  };
})();
