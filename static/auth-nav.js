// Compartilhado entre todas as páginas: mostra o estado de login no menu.
async function carregarSessaoNoMenu() {
  const el = document.getElementById("nav-usuario");
  if (!el) return;

  // Réplica compacta (só ícones) sobreposta no canto inferior esquerdo do
  // banner — no celular, o bloco de conta/assinatura dentro do menu rolante
  // roubava espaço dos links que importam de verdade. Some no desktop (CSS).
  let elMobile = document.getElementById("nav-usuario-mobile");
  if (!elMobile) {
    const elHeader = document.querySelector("header");
    if (elHeader) {
      elMobile = document.createElement("div");
      elMobile.id = "nav-usuario-mobile";
      elMobile.className = "nav-usuario-mobile";
      elHeader.appendChild(elMobile);
    }
  }

  const elNavAdmin = document.getElementById("nav-admin");
  const elMeusAlunos = document.getElementById("nav-meus-alunos");
  const elTurmas = document.getElementById("nav-turmas");
  const elPlanos = document.getElementById("nav-planos");

  const ICONE_LOGOUT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>';
  const ICONE_LOGIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>';
  const ICONE_CADASTRO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>';
  const ICONE_ASSINATURA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>';

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
      // Desktop: "Minha Assinatura"/"Sair" viram um submenu no nome do
      // usuário, igual ao dropdown de Admin/Turmas (mesmas classes, reusa o
      // configurarDropdowns já existente). Mobile continua só com os ícones.
      el.innerHTML = `
        <div class="nav-admin-dropdown">
          <a href="#" class="nav-admin-toggle"><span class="nav-email">${dados.email}</span><span class="nav-admin-seta">▾</span></a>
          <div class="nav-admin-submenu">
            <a href="/assinatura">${ICONE_ASSINATURA}<span>Minha Assinatura</span></a>
            <a href="#" class="nav-sair">${ICONE_LOGOUT}<span>Sair</span></a>
          </div>
        </div>
      `;
      configurarDropdowns(el);
      if (elMobile) {
        elMobile.innerHTML = `<a href="/assinatura" title="Minha Assinatura">${ICONE_ASSINATURA}</a><a href="#" class="nav-sair" title="Sair">${ICONE_LOGOUT}</a>`;
      }
      document.querySelectorAll(".nav-sair").forEach((btn) => {
        btn.addEventListener("click", async (ev) => {
          ev.preventDefault();
          await fetch("/api/sair", { method: "POST" });
          window.location.reload();
        });
      });
      if (elNavAdmin) elNavAdmin.style.display = dados.admin ? "" : "none";
      if (elMeusAlunos) elMeusAlunos.style.display = dados.mestre ? "" : "none";
      if (elTurmas) elTurmas.style.display = dados.mestre ? "" : "none";
      if (elPlanos) elPlanos.style.display = "none";
      if (dados.mestre) await carregarSubmenuTurmas();
      aplicarSessao({ logado: true, mestre: !!dados.mestre, admin: !!dados.admin, email: dados.email });
    } else {
      const html = `<a href="/login" title="Entrar">${ICONE_LOGIN}<span>Entrar</span></a><a href="/cadastro" title="Cadastrar">${ICONE_CADASTRO}<span>Cadastrar</span></a>`;
      el.innerHTML = html;
      if (elMobile) elMobile.innerHTML = html;
      if (elNavAdmin) elNavAdmin.style.display = "none";
      if (elMeusAlunos) elMeusAlunos.style.display = "none";
      if (elTurmas) elTurmas.style.display = "none";
      if (elPlanos) elPlanos.style.display = "";
      aplicarSessao({ logado: false, mestre: false, admin: false });
    }
  } catch (err) {
    const html = `<a href="/login">Entrar</a><a href="/cadastro">Cadastrar</a>`;
    el.innerHTML = html;
    if (elMobile) elMobile.innerHTML = html;
    if (elNavAdmin) elNavAdmin.style.display = "none";
    if (elMeusAlunos) elMeusAlunos.style.display = "none";
    if (elTurmas) elTurmas.style.display = "none";
    if (elPlanos) elPlanos.style.display = "";
    aplicarSessao({ logado: false, mestre: false, admin: false });
  }
}

// Submenu "Turmas": lista as turmas já criadas pelo Mestre, com link direto
// pra cada uma dentro de /turmas.
async function carregarSubmenuTurmas() {
  const elSubmenu = document.getElementById("nav-turmas-submenu");
  if (!elSubmenu) return;
  try {
    const resp = await fetch("/api/turmas");
    if (!resp.ok) return;
    const turmas = await resp.json();
    const itemNova = `<a href="/turmas?nova=1"><strong>+ Nova turma</strong></a>`;
    elSubmenu.innerHTML = itemNova + (turmas.length
      ? turmas.map(t => `<a href="/turmas?turma=${t.id}">${t.nome ? t.nome + " — " : ""}${t.categoria}</a>`).join("")
      : "");
  } catch {
    // silencioso — submenu só é um atalho, a página /turmas continua acessível
  }
}

// Submenus "Admin" e "Turmas": abrem com hover no desktop (via CSS), e com
// clique/toque em qualquer dispositivo (essencial no celular, que não tem
// hover) — fecham ao clicar fora. No desktop o menu principal tem
// overflow-x:auto (pra caber numa linha só), o que o navegador também trata
// como overflow-y:auto — cortando um submenu position:absolute. Por isso o
// submenu vira position:fixed em telas largas (ver style.css), e aqui a
// gente calcula o top/left exatos toda vez que ele for aparecer.
// Recebe um "escopo" (document, ou o menu clonado no rodapé) porque essa
// função roda duas vezes: uma pro menu do topo, outra pro clone de baixo.
function configurarDropdowns(escopo) {
  escopo.querySelectorAll(".nav-admin-dropdown").forEach((elDropdown) => {
    const elToggle = elDropdown.querySelector(":scope > a");
    const elSubmenu = elDropdown.querySelector(".nav-admin-submenu");
    if (!elToggle || !elSubmenu) return;

    // No rodapé abre pra cima (ancorado por "bottom", não "top" — assim não
    // precisa saber a altura do submenu antes dele estar visível pra medir).
    const posicionarParaCima = () => {
      const r = elToggle.getBoundingClientRect();
      elSubmenu.style.top = "auto";
      elSubmenu.style.bottom = `${window.innerHeight - r.top}px`;
      elSubmenu.style.left = `${r.left}px`;
    };
    const posicionarNormal = () => {
      const r = elToggle.getBoundingClientRect();
      elSubmenu.style.bottom = "auto";
      elSubmenu.style.top = `${r.bottom}px`;
      elSubmenu.style.left = `${r.left}px`;
    };
    const ehRodape = elDropdown.closest(".menu-lateral-rodape") !== null;

    elDropdown.addEventListener("mouseenter", ehRodape ? posicionarParaCima : posicionarNormal);

    if (elToggle.classList.contains("nav-admin-toggle")) {
      elToggle.addEventListener("click", (ev) => {
        ev.preventDefault();
        (ehRodape ? posicionarParaCima : posicionarNormal)();
        elDropdown.classList.toggle("aberto");
      });
    }

    document.addEventListener("click", (ev) => {
      if (!elDropdown.contains(ev.target)) elDropdown.classList.remove("aberto");
    });
  });
}
configurarDropdowns(document);

// Réplica do menu principal fixa no rodapé (mesmos links, dropdowns e
// estado de login) — clona só depois que o menu do topo está pronto de
// verdade (sessão carregada e submenu de Turmas populado), pra não duplicar
// um menu ainda incompleto.
async function montarMenuRodape() {
  const elTopo = document.querySelector(".menu-lateral:not(.menu-lateral-rodape)");
  const elRodape = document.getElementById("menu-rodape");
  if (!elTopo || !elRodape) return;
  elRodape.innerHTML = elTopo.innerHTML;
  configurarDropdowns(elRodape);

  // O botão "Sair" tem um listener preso ao elemento original (não a uma
  // classe) — o clone precisa do próprio, senão o botão de baixo fica morto.
  const elSairRodape = elRodape.querySelector(".nav-sair");
  if (elSairRodape) {
    elSairRodape.addEventListener("click", async (ev) => {
      ev.preventDefault();
      await fetch("/api/sair", { method: "POST" });
      window.location.reload();
    });
  }

  montarRodapeLegal(elRodape);
}

// Faixa fixa com os links legais (Termos de Uso / Política de Privacidade),
// logo abaixo do menu replicado no rodapé — presente em toda página, sem
// precisar mexer no HTML de cada uma.
function montarRodapeLegal(elRodape) {
  if (document.querySelector(".rodape-legal")) return;
  elRodape.insertAdjacentHTML(
    "afterend",
    '<div class="rodape-legal">© Radar BJJ · <a href="/termos">Termos de Uso</a> · <a href="/privacidade">Política de Privacidade</a></div>'
  );
}

carregarSessaoNoMenu().then(montarMenuRodape);

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
