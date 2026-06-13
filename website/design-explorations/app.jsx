// App — composes all variants into the DesignCanvas

const { DesignCanvas, DCSection, DCArtboard, DCPostIt } = window;

const App = () => (
  <DesignCanvas title="POPPy — direction exploration" subtitle="Three apothecary-modern directions for the site. Pick one and I'll commit it to .astro source.">
    <DCSection
      id="home-directions"
      title="Home — three directions"
      subtitle="Same content, three different visual systems. Compare the home page across all three before drilling into the chosen one."
    >
      <DCArtboard id="herbarium-home" label="A · Herbarium" width={1280} height={3520}>
        <HerbariumHome />
      </DCArtboard>
      <DCArtboard id="notebook-home" label="B · Field Notebook" width={1280} height={2700}>
        <NotebookHome />
      </DCArtboard>
      <DCArtboard id="modern-home" label="C · Modern Apothecary" width={1280} height={3300}>
        <ModernHome />
      </DCArtboard>
    </DCSection>

    <DCSection
      id="herbarium-system"
      title="Herbarium — full system"
      subtitle="The other three pages, rendered in direction A so you can see how the system extends. If you pick B or C, I'll port these into that direction."
    >
      <DCArtboard id="herbarium-about" label="About" width={1280} height={1950}>
        <HerbariumAbout />
      </DCArtboard>
      <DCArtboard id="herbarium-download" label="Download" width={1280} height={1700}>
        <HerbariumDownload />
      </DCArtboard>
      <DCArtboard id="herbarium-contact" label="Contact" width={1280} height={1500}>
        <HerbariumContact />
      </DCArtboard>
    </DCSection>

    <DCSection
      id="notes"
      title="Notes & next steps"
      subtitle="Pick a direction below and I'll commit it to .astro source."
    >
      <DCArtboard id="notes-card" label="Notes" width={1280} height={420}>
        <div style={{ background: "#fef4a8", color: "#5a4a2a", padding: "32px 40px", fontFamily: "system-ui, sans-serif", width: 1280, height: 420, lineHeight: 1.55 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 32, marginBottom: 24 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>A · Herbarium</div>
              <div style={{ fontSize: 14 }}>Most "old apothecary." Centered axial composition, hairline rules, Latin binomials, EB Garamond + IBM Plex Mono. Quietest, most scholarly.</div>
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>B · Field Notebook</div>
              <div style={{ fontSize: 14 }}>Editorial / journal feel. Forest + bone + rust accent. Asymmetric grid, DM Serif Display headlines, Spectral body. Best for showcasing imagery.</div>
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>C · Modern Apothecary</div>
              <div style={{ fontSize: 14 }}>Boldest, most contemporary. Solid forest blocks with cream knockout, big Cardo italic display. Feels like a modern pharma lab that respects the lineage.</div>
            </div>
          </div>
          <div style={{ borderTop: "1px solid #c4a05a55", paddingTop: 20, fontSize: 14 }}>
            <b>Next step:</b> tell me which letter (A / B / C) you want — I'll write the actual <code>.astro</code> files into <code>src/pages/</code> for Home, About, Download and Contact, and update <code>src/styles/main.css</code> with the new palette and type stack. Botanical plates are placeholders and can be swapped for an <code>&lt;image-slot&gt;</code> when you have real plates to drop in.
          </div>
        </div>
      </DCArtboard>
    </DCSection>
  </DesignCanvas>
);

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
