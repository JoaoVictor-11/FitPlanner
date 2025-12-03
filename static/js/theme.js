// theme.js — controlos de tema e sidebar (robusto)
document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("sidebarToggle");
  const themeBtn = document.getElementById("themeToggle");

  // carrega preferência (localStorage -> html attribute)
  const saved = localStorage.getItem("theme");
  const htmlAttr = document.documentElement.getAttribute("data-theme");
  const current = saved || htmlAttr || "dark";
  document.documentElement.setAttribute("data-theme", current);
  try { localStorage.setItem("theme", current); } catch(e){}

  // botão de alternar tema (se existir)
  if (themeBtn) {
    themeBtn.addEventListener("click", async () => {
      const now = document.documentElement.getAttribute("data-theme") || "dark";
      const next = now === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch(e){}

      // tenta notificar o servidor — tolerante a formatos de resposta
      try {
        const res = await fetch("/trocar_tema", { method: "POST", credentials: "same-origin" });
        if (res.ok) {
          const json = await res.json().catch(()=>null);
          // aceita ambas as chaves: "theme" ou "tema"
          const serverTheme = json && (json.theme || json.tema);
          if (serverTheme) {
            document.documentElement.setAttribute("data-theme", serverTheme);
            try { localStorage.setItem("theme", serverTheme); } catch(e){}
          }
        }
      } catch (e) {
        // ignore — manter mudança local
      }
    });
  }

  // sidebar collapse toggle (persist)
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      try { localStorage.setItem("fp_sidebar_collapsed", sidebar.classList.contains("collapsed") ? "1" : "0"); } catch(e){}
    });
    const savedState = localStorage.getItem("fp_sidebar_collapsed");
    if (savedState === "1") sidebar.classList.add("collapsed");
  }
});