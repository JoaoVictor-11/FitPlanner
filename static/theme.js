document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("sidebarToggle");
  const themeBtn = document.getElementById("themeToggle");

  /* === TEMA === */
  const saved = localStorage.getItem("theme");
  const current = saved || document.documentElement.getAttribute("data-theme") || "dark";

  document.documentElement.setAttribute("data-theme", current);
  localStorage.setItem("theme", current);

  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const now = document.documentElement.getAttribute("data-theme");
      const next = now === "light" ? "dark" : "light";

      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);

      fetch("/trocar_tema", { method: "POST" }).catch(() => {});
    });
  }

  /* === SIDEBAR === */
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      localStorage.setItem(
        "fp_sidebar_collapsed",
        sidebar.classList.contains("collapsed") ? "1" : "0"
      );
    });

    const savedState = localStorage.getItem("fp_sidebar_collapsed");
    if (savedState === "1") sidebar.classList.add("collapsed");
  }
});