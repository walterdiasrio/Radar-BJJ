// Compartilhado entre todas as páginas: mostra o estado de login no menu.
async function carregarSessaoNoMenu() {
  const el = document.getElementById("nav-usuario");
  if (!el) return;

  const elNavAdmin = document.getElementById("nav-admin");
  const elMeusAlunos = document.getElementById("nav-meus-alunos");
  const elTurmas = document.getElementById("nav-turmas");
  const elAssinatura = document.getElementById("nav-assinatura");

  const ICONE_LOGOUT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>';
  const ICONE_LOGIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>';
  const ICONE_CADASTRO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>';

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
      el.innerHTML = `<span class="nav-email">${dados.email}</span><a href="#" id="nav-sair">${ICONE_LOGOUT}<span>Sair</span></a>`;
      document.getElementById("nav-sair").addEventListener("click", async (ev) => {
        ev.preventDefault();
        await fetch("/api/sair", { method: "POST" });
        window.location.reload();
      });
      if (elNavAdmin) elNavAdmin.style.display = dados.admin ? "" : "none";
      if (elMeusAlunos) elMeusAlunos.style.display = dados.mestre ? "" : "none";
      if (elTurmas) elTurmas.style.display = dados.mestre ? "" : "none";
      if (elAssinatura) elAssinatura.style.display = "";
      if (dados.mestre) carregarSubmenuTurmas();
      aplicarSessao({ logado: true, mestre: !!dados.mestre, admin: !!dados.admin, email: dados.email });
    } else {
      el.innerHTML = `<a href="/login">${ICONE_LOGIN}<span>Entrar</span></a><a href="/cadastro">${ICONE_CADASTRO}<span>Cadastrar</span></a>`;
      if (elNavAdmin) elNavAdmin.style.display = "none";
      if (elMeusAlunos) elMeusAlunos.style.display = "none";
      if (elTurmas) elTurmas.style.display = "none";
      if (elAssinatura) elAssinatura.style.display = "none";
      aplicarSessao({ logado: false, mestre: false, admin: false });
    }
  } catch (err) {
    el.innerHTML = `<a href="/login">Entrar</a><a href="/cadastro">Cadastrar</a>`;
    if (elNavAdmin) elNavAdmin.style.display = "none";
    if (elMeusAlunos) elMeusAlunos.style.display = "none";
    if (elTurmas) elTurmas.style.display = "none";
    if (elAssinatura) elAssinatura.style.display = "none";
    aplicarSessao({ logado: false, mestre: false, admin: false });
  }
}

carregarSessaoNoMenu();

// Menu flutua transparente sobre o banner (como cbjj.com.br) até a página
// rolar o suficiente pra cobrir onde ele "flutuaria" — a partir daí vira
// fixo e sólido (classe .flutuante) pra continuar legível e utilizável.
(() => {
  const elMenu = document.querySelector(".menu-lateral");
  const elHeader = document.querySelector("header");
  if (!elMenu || !elHeader) return;

  const aoRolar = () => {
    // Vira sólida assim que a barra transparente (sobreposta ao banner)
    // sairia de vista rolando — não espera o banner inteiro passar.
    const limite = Math.max(elMenu.offsetHeight - 20, 40);
    elMenu.classList.toggle("flutuante", window.scrollY > limite);
  };
  window.addEventListener("scroll", aoRolar, { passive: true });
  window.addEventListener("resize", aoRolar);
  aoRolar();
})();

// Submenu "Turmas": lista as turmas já criadas pelo Mestre, com link direto
// pra cada uma dentro de /turmas.
async function carregarSubmenuTurmas() {
  const elSubmenu = document.getElementById("nav-turmas-submenu");
  if (!elSubmenu) return;
  try {
    const resp = await fetch("/api/turmas");
    if (!resp.ok) return;
    const turmas = await resp.json();
    elSubmenu.innerHTML = turmas.length
      ? turmas.map(t => `<a href="/turmas?turma=${t.id}">${t.nome ? t.nome + " — " : ""}${t.categoria}</a>`).join("")
      : `<a href="/turmas">Nenhuma turma ainda</a>`;
  } catch {
    // silencioso — submenu só é um atalho, a página /turmas continua acessível
  }
}

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
