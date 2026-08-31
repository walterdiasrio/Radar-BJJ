// Páginas de ferramenta exclusiva do Plano PRO (Radar de Atletas, Meus
// Alunos, Turmas, detalhe de aluno) não exigem mais assinatura só pra
// ABRIR — a pessoa consegue ver a página, mas com esse aviso por cima do
// conteúdo em vez do formulário/lista de verdade, com um link pra testar
// grátis. As rotas de API continuam bloqueadas por conta própria
// (api_assinatura_necessaria, em app.py), então mesmo se essa checagem
// falhasse por algum motivo, não dava pra usar a ferramenta de fato —
// isso aqui é só a experiência visual, não a proteção real dos dados.
// `seletorConteudo` é o elemento (ou seletor) a esconder; o aviso entra
// no lugar dele.
// Retorna true se bloqueou (sem acesso) — quem chama usa isso pra pular
// outras chamadas de API que também exigem assinatura (essas continuam
// dando 402, e fetchAutenticado já redireciona sozinho nesse caso — sem
// pular, a pessoa via o aviso por uma fração de segundo e já saía voando
// pra /assinatura de novo, por causa de alguma OUTRA chamada da página).
async function bloquearSePlanoFree(seletorConteudo) {
  let dados;
  try {
    const resp = await fetch("/api/sessao");
    dados = await resp.json();
  } catch (err) {
    return false;
  }
  if (!dados.logado) return false;
  if (dados.admin || (dados.assinatura && dados.assinatura.tem_acesso)) return false;

  const elConteudo = typeof seletorConteudo === "string" ? document.querySelector(seletorConteudo) : seletorConteudo;
  if (!elConteudo) return true;

  const aviso = document.createElement("div");
  aviso.className = "aviso-plano-pro";
  aviso.innerHTML = `🔒 Ferramenta exclusiva para o Plano PRO. <a href="/assinatura">Teste Grátis clicando aqui</a>.`;
  elConteudo.parentNode.insertBefore(aviso, elConteudo);
  elConteudo.style.display = "none";
  return true;
}

// Barrinha fixa por cima do banner, só no desktop (CSS esconde no mobile,
// que já tem seu próprio tratamento de conta — ver .nav-usuario-mobile) —
// os 2 atalhos mais usados + a conta, pra não depender de rolar até o
// menu lateral pra essas ações do dia a dia. Criada em JS (não em cada
// HTML) pra não precisar duplicar esse bloco em todas as páginas do site.
function montarBarraTopoDesktop() {
  let elTopo = document.getElementById("nav-usuario-topo");
  if (elTopo) return elTopo;

  const barra = document.createElement("div");
  barra.id = "barra-topo-desktop";
  barra.className = "barra-topo-desktop";
  barra.innerHTML = `
    <div class="atalhos-topo">
      <a href="/buscador" class="atalho-topo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16" y2="16"/></svg><span>Radar de Atletas</span></a>
      <a href="/competicoes" class="atalho-topo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8"/><path d="M12 17v4"/><path d="M7 4h10v5a5 5 0 0 1-10 0V4Z"/><path d="M7 5H4v1a4 4 0 0 0 4 4"/><path d="M17 5h3v1a4 4 0 0 1-4 4"/></svg><span>Competições</span></a>
    </div>
    <div id="nav-usuario-topo" class="nav-usuario"></div>
  `;
  document.body.insertBefore(barra, document.body.firstChild);
  return document.getElementById("nav-usuario-topo");
}

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

  // Réplica da conta na barrinha fixa do topo (desktop) — o menu lateral
  // tem só a navegação; conta fica ali em cima, junto dos 2 atalhos mais
  // usados (ver montarBarraTopoDesktop, mais abaixo). Mesmo conteúdo do
  // #nav-usuario "de baixo" (que continua existindo — no mobile ele é a
  // fonte de Entrar/Cadastrar dentro do menu rolante), só que num elemento
  // à parte, porque um mesmo nó não pode estar em dois lugares do DOM.
  const elTopo = montarBarraTopoDesktop();

  const elNavAdmin = document.getElementById("nav-admin");
  const elNavAdminMobile = document.getElementById("nav-admin-toggle-mobile");
  const elMeusAlunos = document.getElementById("nav-meus-alunos");
  const elTurmas = document.getElementById("nav-turmas");
  const elTurmasMobile = document.getElementById("nav-turmas-toggle-mobile");
  const elPlanos = document.getElementById("nav-planos");

  // Pra quem ainda não tem login, "Planos" é o link mais importante do menu
  // (é o caminho pra virar assinante) — por isso fica antes de "Radar de
  // Atletas", não escondido lá no fim da fila.
  const reordenarPlanosAntesDoRadar = () => {
    if (!elPlanos) return;
    const elRadar = document.querySelector('.nav-item-atleta[href="/buscador"]');
    if (elRadar && elRadar.parentNode) elRadar.parentNode.insertBefore(elPlanos, elRadar);
  };

  const ICONE_LOGOUT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>';
  const ICONE_LOGIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>';
  const ICONE_CADASTRO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>';
  const ICONE_ASSINATURA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>';
  const ICONE_PERFIL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a8 8 0 0 1 16 0v1"/></svg>';

  const aplicarSessao = (dados) => {
    window.sessaoAtual = dados;
    const elEquipe = document.getElementById("equipe");
    if (elEquipe) {
      const campo = elEquipe.closest(".campo");
      if (campo) campo.style.display = dados.mestre ? "" : "none";
    }
    document.dispatchEvent(new CustomEvent("sessao-carregada", { detail: dados }));
    // Itens do menu mudam de visibilidade conforme a sessão (Admin só pra
    // admin, Turmas só pra mestre etc) — precisa recalcular onde o
    // degradê do menu lateral começa depois de aplicar isso (ver
    // ajustarDegradeMenu, definida mais abaixo).
    ajustarDegradeMenu();
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
            <a href="/perfil">${ICONE_PERFIL}<span>Meu Perfil</span></a>
            <a href="/assinatura">${ICONE_ASSINATURA}<span>Minha Assinatura</span></a>
            <a href="#" class="nav-sair">${ICONE_LOGOUT}<span>Sair</span></a>
          </div>
        </div>
      `;
      configurarDropdowns(el);
      el.classList.add("nav-usuario-compacto-mobile");
      if (elTopo) {
        elTopo.innerHTML = el.innerHTML;
        configurarDropdowns(elTopo);
      }
      if (elMobile) {
        elMobile.style.display = "";
        elMobile.innerHTML = `<a href="/perfil" title="Meu Perfil">${ICONE_PERFIL}</a><a href="/assinatura" title="Minha Assinatura">${ICONE_ASSINATURA}</a><a href="#" class="nav-sair" title="Sair">${ICONE_LOGOUT}</a>`;
      }
      document.querySelectorAll(".nav-sair").forEach((btn) => {
        btn.addEventListener("click", async (ev) => {
          ev.preventDefault();
          await fetch("/api/sair", { method: "POST" });
          window.location.reload();
        });
      });
      if (elNavAdmin) elNavAdmin.style.display = dados.admin ? "" : "none";
      if (elNavAdminMobile) elNavAdminMobile.style.display = dados.admin ? "" : "none";
      if (elMeusAlunos) elMeusAlunos.style.display = dados.mestre ? "" : "none";
      if (elTurmas) elTurmas.style.display = dados.mestre ? "" : "none";
      if (elTurmasMobile) elTurmasMobile.style.display = dados.mestre ? "" : "none";
      if (elPlanos) elPlanos.style.display = "none";
      if (dados.mestre) await carregarSubmenuTurmas();
      aplicarSessao({ logado: true, mestre: !!dados.mestre, admin: !!dados.admin, email: dados.email });
    } else {
      // Entrar/Cadastrar continuam dentro do menu rolante (CSS manda pro
      // fim da fila no mobile) — só a conta já logada (Sair/Assinatura) é
      // que sai do menu e vira ícone compacto no banner, no mobile.
      el.classList.remove("nav-usuario-compacto-mobile");
      el.innerHTML = `<a href="/login" title="Entrar">${ICONE_LOGIN}<span>Entrar</span></a><a href="/cadastro" title="Cadastrar">${ICONE_CADASTRO}<span>Cadastrar</span></a>`;
      if (elTopo) elTopo.innerHTML = el.innerHTML;
      if (elMobile) { elMobile.style.display = "none"; elMobile.innerHTML = ""; }
      if (elNavAdmin) elNavAdmin.style.display = "none";
      if (elNavAdminMobile) elNavAdminMobile.style.display = "none";
      if (elMeusAlunos) elMeusAlunos.style.display = "none";
      if (elTurmas) elTurmas.style.display = "none";
      if (elTurmasMobile) elTurmasMobile.style.display = "none";
      if (elPlanos) elPlanos.style.display = "";
      reordenarPlanosAntesDoRadar();
      aplicarSessao({ logado: false, mestre: false, admin: false });
    }
  } catch (err) {
    el.classList.remove("nav-usuario-compacto-mobile");
    el.innerHTML = `<a href="/login">Entrar</a><a href="/cadastro">Cadastrar</a>`;
    if (elTopo) elTopo.innerHTML = el.innerHTML;
    if (elMobile) { elMobile.style.display = "none"; elMobile.innerHTML = ""; }
    if (elNavAdmin) elNavAdmin.style.display = "none";
    if (elNavAdminMobile) elNavAdminMobile.style.display = "none";
    if (elMeusAlunos) elMeusAlunos.style.display = "none";
    if (elTurmas) elTurmas.style.display = "none";
    if (elTurmasMobile) elTurmasMobile.style.display = "none";
    if (elPlanos) elPlanos.style.display = "";
    reordenarPlanosAntesDoRadar();
    aplicarSessao({ logado: false, mestre: false, admin: false });
  }
}

// Submenu "Turmas": lista as turmas já criadas pelo Mestre, com link direto
// pra cada uma dentro de /turmas.
async function carregarSubmenuTurmas() {
  const elSubmenu = document.getElementById("nav-turmas-submenu");
  const elPainelMobile = document.getElementById("painel-nav-turmas");
  if (!elSubmenu && !elPainelMobile) return;

  // "+ Nova turma" sempre aparece, mesmo se a lista de turmas não vier —
  // sem isso, um erro na API (ex: 402 de Mestre no plano Free, que ainda
  // não tem assinatura) deixava o submenu inteiro vazio, parecendo que o
  // clique em "Turmas" simplesmente não fazia nada.
  const itemNova = `<a href="/turmas?nova=1"><strong>+ Nova turma</strong></a>`;
  let html = itemNova;
  try {
    const resp = await fetch("/api/turmas");
    if (resp.ok) {
      const turmas = await resp.json();
      if (turmas.length) {
        html += turmas.map(t => `<a href="/turmas?turma=${t.id}">${t.nome ? t.nome + " — " : ""}${t.categoria}</a>`).join("");
      }
    }
  } catch {
    // sem conexão etc — mantém pelo menos o "+ Nova turma" já montado acima
  }
  if (elSubmenu) elSubmenu.innerHTML = html;
  if (elPainelMobile) elPainelMobile.innerHTML = html;
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

    // left "clampado" pra nunca vazar pra fora da tela — essencial no
    // celular, onde o toggle (Admin/Turmas) costuma estar perto do fim da
    // faixa rolável, então r.left sozinho jogaria o submenu pra fora da
    // largura da tela. Só funciona chamado DEPOIS do submenu virar
    // display:flex (senão a largura medida é 0), por isso a ordem no
    // listener de clique abaixo importa: primeiro adiciona "aberto",
    // depois posiciona.
    const calcularLeftClampado = (r) => {
      const largura = elSubmenu.offsetWidth || 220;
      return Math.max(8, Math.min(r.left, window.innerWidth - largura - 8));
    };
    // No rodapé abre pra cima (ancorado por "bottom", não "top" — assim não
    // precisa saber a altura do submenu antes dele estar visível pra medir).
    const posicionarParaCima = () => {
      const r = elToggle.getBoundingClientRect();
      elSubmenu.style.top = "auto";
      elSubmenu.style.bottom = `${window.innerHeight - r.top}px`;
      elSubmenu.style.left = `${calcularLeftClampado(r)}px`;
    };
    const posicionarNormal = () => {
      const r = elToggle.getBoundingClientRect();
      elSubmenu.style.bottom = "auto";
      elSubmenu.style.top = `${r.bottom}px`;
      elSubmenu.style.left = `${calcularLeftClampado(r)}px`;
    };
    // Desktop (menu lateral esquerdo, ver style.css): abre AO LADO (à
    // direita do item), não embaixo — embaixo ficaria espremido contra a
    // borda estreita do menu (220px) e cortado. top clampado igual ao
    // left de posicionarNormal, só que no eixo vertical.
    const posicionarAoLado = () => {
      const r = elToggle.getBoundingClientRect();
      const altura = elSubmenu.offsetHeight || 0;
      elSubmenu.style.bottom = "auto";
      elSubmenu.style.top = `${Math.max(8, Math.min(r.top, window.innerHeight - altura - 8))}px`;
      elSubmenu.style.left = `${r.right}px`;
    };
    const ehRodape = elDropdown.closest(".menu-lateral-rodape") !== null;
    // Só o menu lateral (nav vertical) abre AO LADO — a barrinha do topo
    // (.barra-topo-desktop) é horizontal, então o dropdown de conta ali
    // abre EMBAIXO, como sempre foi (senão passava da borda direita da
    // tela, já que o toggle fica bem no canto).
    const ehMenuLateral = elDropdown.closest("nav.menu-lateral:not(.menu-lateral-rodape)") !== null;
    const posicionar = () => {
      if (ehRodape) return posicionarParaCima();
      if (ehMenuLateral && window.matchMedia("(min-width: 901px)").matches) return posicionarAoLado();
      return posicionarNormal();
    };

    elDropdown.addEventListener("mouseenter", posicionar);

    // "Admin" não tem destino próprio (href="#") — sempre só abre/fecha o
    // submenu. "Turmas" tem destino de verdade (href="/turmas"): no
    // desktop o hover já deixa espiar o submenu antes de clicar (clicar
    // navega direto, como sempre foi); no celular não existe hover, então
    // sem essa checagem o primeiro toque navegava direto pra página sem
    // nunca abrir o submenu — agora o primeiro toque só abre, e um
    // segundo toque (ou tocar num item já visível dentro dele) navega.
    // Sempre marca "aberto" ANTES de posicionar (não depois) — o cálculo
    // do left clampado (acima) precisa medir a largura real do submenu já
    // visível, senão mede 0.
    elToggle.addEventListener("click", (ev) => {
      const semDestinoProprio = elToggle.getAttribute("href") === "#";
      const noMobile = window.matchMedia("(max-width: 900px)").matches;
      if (semDestinoProprio) {
        ev.preventDefault();
        elDropdown.classList.toggle("aberto");
        if (elDropdown.classList.contains("aberto")) posicionar();
        return;
      }
      if (noMobile && !elDropdown.classList.contains("aberto")) {
        ev.preventDefault();
        elDropdown.classList.add("aberto");
        posicionar();
      }
    });

    document.addEventListener("click", (ev) => {
      if (!elDropdown.contains(ev.target)) elDropdown.classList.remove("aberto");
    });
  });
}
configurarDropdowns(document);

// No menu lateral do desktop (ver style.css), o fundo azul vira degradê a
// partir de --menu-fade-inicio — recalculada aqui pra começar logo depois
// do ÚLTIMO item VISÍVEL (a lista muda: Admin só aparece pra admin, Turmas
// só pra mestre etc, então um valor fixo no CSS sobrava vazio abaixo do
// último botão real ou cortava antes da hora). Chamada de novo sempre que
// a sessão muda (aplicarSessao, acima) e no resize (pode cruzar o
// breakpoint de 900px pra o menu horizontal do mobile, onde isso não
// importa — o guard de innerWidth abaixo pula o cálculo nesse caso).
function ajustarDegradeMenu() {
  const elMenu = document.querySelector("nav.menu-lateral:not(.menu-lateral-rodape)");
  if (!elMenu || window.innerWidth < 901) return;

  const itens = Array.from(elMenu.children).filter((el) => el.offsetHeight > 0 && el.offsetWidth > 0);
  if (!itens.length) return;
  const ultimo = itens[itens.length - 1];

  const rMenu = elMenu.getBoundingClientRect();
  const rUltimo = ultimo.getBoundingClientRect();
  const fimUltimoItem = rUltimo.bottom - rMenu.top + elMenu.scrollTop;
  elMenu.style.setProperty("--menu-fade-inicio", `${Math.round(fimUltimoItem + 12)}px`);
}
ajustarDegradeMenu();
window.addEventListener("resize", ajustarDegradeMenu);

// Botões "Menu Atleta" / "Turmas" / "Admin" (mobile) — painéis fora do menu,
// posicionados só via CSS (position:sticky, ver style.css), sem cálculo de
// posição em JS (o cálculo via getBoundingClientRect no clique, usado pelos
// dropdowns clássicos — configurarDropdowns acima — segue funcionando no
// desktop, mas se mostrou pouco confiável em celular real). Um listener
// delegado no document cobre tanto os toggles do topo quanto os clones do
// rodapé (mesma classe), fecha os outros painéis ao abrir um novo, e fecha
// tudo ao clicar fora.
const MAPA_TOGGLE_PAINEL_MOBILE = [
  [".menu-atleta-toggle", "painel-menu-atleta"],
  [".turmas-toggle-mobile", "painel-nav-turmas"],
  [".admin-toggle-mobile", "painel-nav-admin"],
];
document.addEventListener("click", (ev) => {
  for (const [seletorToggle, idPainel] of MAPA_TOGGLE_PAINEL_MOBILE) {
    const elToggle = ev.target.closest(seletorToggle);
    if (!elToggle) continue;
    ev.preventDefault();
    const elPainel = document.getElementById(idPainel);
    if (!elPainel) return;
    const jaAberto = elPainel.classList.contains("aberto");
    MAPA_TOGGLE_PAINEL_MOBILE.forEach(([, id]) => {
      const p = document.getElementById(id);
      if (p) p.classList.remove("aberto");
    });
    if (!jaAberto) {
      // Tocado a partir do clone do rodapé: o painel é um elemento único
      // (não clonado) — sem isso ele abriria grudado no topo da tela
      // (sticky, pensado pro toggle do topo), longe de onde o dedo tocou.
      // Ver .painel-menu-atleta.aberto-rodape em style.css.
      const ehRodape = elToggle.closest(".menu-lateral-rodape") !== null;
      elPainel.classList.toggle("aberto-rodape", ehRodape);
      if (ehRodape) {
        const r = elToggle.getBoundingClientRect();
        elPainel.style.bottom = `${window.innerHeight - r.top}px`;
      }
      elPainel.classList.add("aberto");
    }
    return;
  }
  MAPA_TOGGLE_PAINEL_MOBILE.forEach(([, idPainel]) => {
    const elPainel = document.getElementById(idPainel);
    if (elPainel && elPainel.classList.contains("aberto") && !elPainel.contains(ev.target)) {
      elPainel.classList.remove("aberto");
    }
  });
});

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
    '<div class="rodape-legal">© Radar BJJ · CNPJ 68.684.119/0001-64 · <a href="/termos">Termos de Uso</a> · <a href="/privacidade">Política de Privacidade</a></div>'
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
