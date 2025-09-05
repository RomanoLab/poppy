async function loadStats() {
  const el = document.getElementById('stats');
  try {
    const res = await fetch('data/ontology_stats.json');
    if (!res.ok) throw new Error('No stats file found');
    const json = await res.json();
    el.innerHTML = `<strong>Triples:</strong> ${json.triples} &nbsp; <strong>Format:</strong> ${json.format} &nbsp; <code>${json.out_path}</code>`;
  } catch (e) {
    el.textContent = 'No stats yet. Build the ontology and copy results into web/data/.';
  }
}

async function listDownloads() {
  const ul = document.getElementById('download-list');
  try {
    const res = await fetch(''); // no directory listing on GitHub Pages; we just try known filenames
  } catch {}
  const candidates = ['phytotherapies_enriched.ttl', 'phytotherapies_final_with_ECFP.ttl', 'ontology_stats.json'];
  ul.innerHTML = '';
  for (const name of candidates) {
    const url = `data/${name}`;
    try {
      const head = await fetch(url, { method: 'HEAD' });
      if (head.ok) {
        const li = document.createElement('li');
        li.innerHTML = `<a href="${url}" download>${name}</a>`;
        ul.appendChild(li);
      }
    } catch {}
  }
  if (!ul.children.length) {
    ul.innerHTML = '<li>No downloadable files found yet in <code>web/data/</code>.</li>';
  }
}

loadStats();
listDownloads();
