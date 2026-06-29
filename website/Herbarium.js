    const PLATES = [
      ["papaver-somniferum", "Papaver somniferum", "Opium poppy"],
      ["digitalis-purpurea", "Digitalis purpurea", "Common foxglove"],
      ["datura-stramonium", "Datura stramonium", "Thorn-apple"],
      ["nicotiana-tabacum", "Nicotiana tabacum", "Cultivated tobacco"],
      ["rosa-centifolia", "Rosa centifolia", "Cabbage rose"],
      ["camellia-thea", "Camellia thea", "Tea tree"],
      ["anacyclus-pyrethrum", "Anacyclus pyrethrum", "Spanish chamomile"],
      ["cinnamomum-zeylanicum", "Cinnamomum zeylanicum", "Cinnamon"],
      ["citrus-limonum", "Citrus limonum", "Citrus lemon"],
      ["citrus-vulgaris", "Citrus vulgaris", "Bitter orange"],
      ["inula-helenium", "Inula helenium", "Elecampane"],
      ["croton-tiglium", "Croton tiglium", "Croton"],
      ["levisticum-officinale", "Levisticum officinale", "Lovage"],
      ["erythraea-centaurium", "Erythraea centaurium", "Centaury"],
      ["tussilago-farfara", "Tussilago farfara", "Coltsfoot"],
      ["verbascum-phlomoides", "Verbascum phlomoides", "Orange mullein"],
      ["cnicus-benedictus", "Cnicus benedictus", "St. Benedict's thistle"],
      ["chrysanthemum-roseum", "Chrysanthemum roseum", "Painted daisy"],
      ["ipomoea-purga", "Ipomoea purga", "Jalap"],
      ["rubus-idaeus", "Rubus idaeus", "Red raspberry"],
      ["prunus-cerasus", "Prunus cerasus", "Sour cherry"],
      ["pirus-malus", "Pirus malus", "Common apple tree"],
      ["cydonia-vulgaris", "Cydonia vulgaris", "Quince"],
      ["quercus-sessiliflora", "Quercus sessiliflora", "Sessile oak"]
    ];
    const roman = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX","XXI","XXII","XXIII","XXIV"];
    const grid = document.getElementById("grid");
    PLATES.forEach((p, i) => {
      const fig = document.createElement("div");
      fig.className = "specimen";
      fig.innerHTML =
        '<div class="art">' +
          '<img loading="lazy" decoding="async" src="assets/plates/' + p[0] + '.jpg" alt="' + p[1] + ' plate">' +
        '</div>' +
        '<div class="label"><div class="tabnum">Tab. ' + roman[i] + '</div>' +
        '<div class="lat">' + p[1] + '</div><div class="common">' + p[2] + '</div></div>';

      grid.appendChild(fig);
    });
  
