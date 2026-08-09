// Compartilhado entre todas as páginas: mostra o estado de login no menu.
async function carregarSessaoNoMenu() {
  const el = document.getElementById("nav-usuario");
  if (!el) return;

  const elNavAdmin = document.getElementById("nav-admin");
  const elMeusAlunos = document.getElementById("nav-meus-alunos");

  const aplicarSessao = (dados) => {
    window.sessaoAtual = dados;
    const elEquipe = document.getElementById("equipe");
    if (elEquipe) {
      const campo = elEquipe.closest(".campo");
      if (campo) campo.style.display = dados.mestre ? "" : "none";
    }
    document.dispatchEvent(new CustomEvent("sessao-carregada", { detail: dados }));
  };

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
      if (elNavAdmin) elNavAdmin.style.display = dados.admin ? "" : "none";
      if (elMeusAlunos) elMeusAlunos.style.display = dados.mestre ? "" : "none";
      aplicarSessao({ logado: true, mestre: !!dados.mestre, admin: !!dados.admin, email: dados.email });
    } else {
      el.innerHTML = `<a href="/login">Entrar</a><a href="/cadastro">Cadastrar</a>`;
      if (elNavAdmin) elNavAdmin.style.display = "none";
      if (elMeusAlunos) elMeusAlunos.style.display = "none";
      aplicarSessao({ logado: false, mestre: false, admin: false });
    }
  } catch (err) {
    el.innerHTML = `<a href="/login">Entrar</a><a href="/cadastro">Cadastrar</a>`;
    if (elNavAdmin) elNavAdmin.style.display = "none";
    if (elMeusAlunos) elMeusAlunos.style.display = "none";
    aplicarSessao({ logado: false, mestre: false, admin: false });
  }
}

carregarSessaoNoMenu();

// Submenu "Admin": abre com hover no desktop (via CSS), e com clique/toque
// em qualquer dispositivo (essencial no celular, que não tem hover) —
// fecha ao clicar fora.
(() => {
  const elDropdown = document.getElementById("nav-admin");
  const elToggle = elDropdown ? elDropdown.querySelector(".nav-admin-toggle") : null;
  if (!elToggle) return;

  elToggle.addEventListener("click", (ev) => {
    ev.preventDefault();
    elDropdown.classList.toggle("aberto");
  });

  document.addEventListener("click", (ev) => {
    if (!elDropdown.contains(ev.target)) elDropdown.classList.remove("aberto");
  });
})();

// Wrapper de fetch para chamadas de API que exigem login: se a sessão
// expirou (401), manda direto para o login em vez de mostrar erro genérico.
async function fetchAutenticado(url, opts) {
  const resp = await fetch(url, opts);
  if (resp.status === 401) {
    window.location.href = "/login";
    throw new Error("sessão expirada, redirecionando para login");
  }
  if (resp.status === 402) {
    window.location.href = "/assinatura";
    throw new Error("assinatura necessária, redirecionando");
  }
  return resp;
}
