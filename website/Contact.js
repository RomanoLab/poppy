    // Demo handler — simulates Formspree round-trip with a small delay.
    // The real Astro page does an actual fetch() against your form endpoint.
    const form = document.getElementById("contact-form");
    const status = document.getElementById("form-status");
    const button = document.getElementById("contact-submit");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      status.textContent = "";
      status.className = "form-status";

      // simple in-browser validation
      const name = form.elements["name"].value.trim();
      const email = form.elements["email"].value.trim();
      const message = form.elements["message"].value.trim();
      if (!name || !email || !message) {
        status.textContent = "All three fields are required.";
        status.classList.add("error");
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        status.textContent = "That email doesn't look right.";
        status.classList.add("error");
        return;
      }

      button.disabled = true;
      const oldLabel = button.textContent;
      button.textContent = "Sending…";

      // Simulated round-trip
      await new Promise((r) => setTimeout(r, 800));

      form.reset();
      status.textContent = "Thank you. We've received your letter and will reply within a few days.";
      status.classList.add("success");
      button.disabled = false;
      button.textContent = oldLabel;
    });
  
