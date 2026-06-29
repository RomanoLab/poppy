    document.getElementById("bibtex-toggle").addEventListener("click", function () {
      const wrap = document.getElementById("bibtex-wrap");
      const open = wrap.classList.toggle("open");
      this.setAttribute("aria-expanded", String(open));
      this.textContent = open ? "Hide BibTeX" : "Show BibTeX";
    });
    document.getElementById("copy-bibtex").addEventListener("click", async function () {
      const text = document.querySelector(".bibtex").innerText;
      try {
        await navigator.clipboard.writeText(text);
        this.textContent = "Copied";
        this.classList.add("copied");
        setTimeout(() => { this.textContent = "Copy"; this.classList.remove("copied"); }, 1500);
      } catch (e) { console.error(e); }
    });
  
