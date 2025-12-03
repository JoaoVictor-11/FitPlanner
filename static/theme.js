document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("sidebarToggle");
  const themeBtn = document.getElementById("sidebarThemeBtn") || document.getElementById("themeToggle");
  const savedTheme = localStorage.getItem("theme");

  // aplica tema salvo no localStorage (se houver) ao carregar
  if (savedTheme) {
    document.documentElement.setAttribute("data-theme", savedTheme);
    if (savedTheme === "dark") {
      document.body.classList.add("dark");
    } else {
      document.body.classList.remove("dark");
    }
  } else {
    // se não houver, tenta usar atributo do html (server-side)
    const htmlTheme = document.documentElement.getAttribute("data-theme");
    if (htmlTheme) {
      localStorage.setItem("theme", htmlTheme);
      if (htmlTheme === "dark") document.body.classList.add("dark");
      else document.body.classList.remove("dark");
    }
  }

  // sidebar toggle (colapsar)
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      const isCollapsed = sidebar.classList.contains("collapsed");
      try { localStorage.setItem("sidebarCollapsed", isCollapsed ? "1" : "0"); } catch(e){}
    });

    // aplicar estado salvo
    const sc = localStorage.getItem("sidebarCollapsed");
    if (sc === "1") sidebar.classList.add("collapsed");
  }

  // alternar tema localmente e tentar notificar servidor
  if (themeBtn) {
    themeBtn.addEventListener("click", async () => {
      const current = document.documentElement.getAttribute("data-theme") || "dark";
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      if (next === "dark') {
        document.body.classList.add('dark');
      } else {
        document.body.classList.remove('dark');
      }
      localStorage.setItem("theme", next);

      // tentar atualizar preferência do usuário no servidor (rota /trocar_tema)
      try {
        await fetch("/trocar_tema", { method: "POST", credentials: "same-origin" });
      } catch (e) { /* sem problemas se falhar */ }
    });
  }
});