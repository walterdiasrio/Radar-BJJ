// Compartilhado entre todas as páginas: mostra o estado de login no menu.
async function carregarSessaoNoMenu() {
  const el = document.getElementById("nav-usuario");
  if (!el) return;

  const elImportarAdcc = document.getElementById("nav-importar-adcc");

  try {
    const resp = await fetch("/api/sessao");
    const dados = await resp.json();
    if (dados.logado) {
      el.innerHTML = `<span class="nav-email">${dados.email}</span><a href="#" id="nav-sair">Sair</a>`;
      document.getElementById("nav-sair").addEventListener("click", async (ev) => {
        ev.preventDefault();
        await fetch("/api/sair", { method: "POST" });
        window.location.reload();
      });
      if (elImportarAdcc) elImportarAdcc.style.display = dados.admin ? "" : "none";
    } else {
      el.innerHTML = `<a href="/login">Entrar</a><a href="/cadastro">Cadastrar</a>`;
      if (elImportarAdcc) elImportarAdcc.style.display = "none";
    }
  } catch (err) {
    el.innerHTML = `<a href="/login">Entrar</a><a href="/cadastro">Cadastrar</a>`;
    if (elImportarAdcc) elImportarAdcc.style.display = "none";
  }
}

carregarSessaoNoMenu();

// Wrapper de fetch para chamadas de API que exigem login: se a sessão
// expirou (401), manda direto pro login em vez de mostrar erro genérico.
async function fetchAutenticado(url, opts) {
  const resp = await fetch(url, opts);
  if (resp.status === 401) {
    window.location.href = "/login";
    throw new Error("sessão expirada, redirecionando para login");
  }
  return resp;
}
