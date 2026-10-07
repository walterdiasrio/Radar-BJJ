const elStatus = document.getElementById("status");
const elLista = document.getElementById("lista-agenda");

let itensAtuais = [];

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function badgeStatus(status) {
  return status === "inscrito"
    ? '<span class="badge-inscricao badge-aberta">Inscrição Confirmada</span>'
    : '<span class="badge-inscricao badge-desconhecida">Tenho Interesse</span>';
}

function renderizar(itens) {
  itensAtuais = itens;

  if (!itens.length) {
    elLista.innerHTML = "";
    mostrarStatus('Nenhuma competição marcada ainda. Vá em Competições e marque as que te interessam com "Tenho Interesse" ou "Inscrito".');
    return;
  }
  mostrarStatus("");

  const blocos = [];
  let atual = null;
  for (const item of itens) {
    if (!atual || atual.mes !== item.mes) {
      atual = { mes: item.mes, itens: [] };
      blocos.push(atual);
    }
    atual.itens.push(item);
  }

  elLista.innerHTML = blocos.map(bloco => `
    <section class="secao-mes">
      <div class="bloco-mes">${bloco.mes} <span class="contagem">(${bloco.itens.length})</span></div>
      ${bloco.itens.map(item => `
        <div class="cartao-alerta">
          <div class="cartao-alerta-topo">
            <div>
              <div class="cartao-alerta-federacao">${item.federacao} — ${item.nome}</div>
              <div class="cartao-alerta-filtros">${item.data}${item.local ? " · " + item.local : ""}</div>
            </div>
            <button type="button" class="btn-remover" data-id="${item.id}">Remover</button>
          </div>
          <div style="margin-top:8px;">${badgeStatus(item.status)}</div>
        </div>
      `).join("")}
    </section>
  `).join("");

  elLista.querySelectorAll(".btn-remover").forEach(btn => {
    btn.addEventListener("click", () => remover(Number(btn.dataset.id)));
  });
}

async function carregar() {
  mostrarStatus("Carregando...");
  try {
    const resp = await fetchAutenticado("/api/agenda");
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao carregar agenda");
    renderizar(dados);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function remover(id) {
  const item = itensAtuais.find(i => i.id === id);
  if (!item) return;
  if (!confirm(`Remover "${item.nome}" da sua agenda?`)) return;

  try {
    const resp = await fetchAutenticado("/api/agenda", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ federacao: item.federacao, nome: item.nome, data: item.data }),
    });
    if (!resp.ok) throw new Error("não consegui remover");
    itensAtuais = itensAtuais.filter(i => i.id !== id);
    renderizar(itensAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

carregar();

// ---------- Exportar pro Instagram (Stories) ----------
let ultimoBlobAgendaStory = null;

const MESES_ABREV = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"];

const logosFederacaoCache = {};
async function carregarLogoFederacao(federacao) {
  const chave = (federacao || "").toLowerCase();
  if (!chave) return null;
  if (chave in logosFederacaoCache) return logosFederacaoCache[chave];
  try {
    logosFederacaoCache[chave] = await carregarImagem(`img/federacoes/${chave}.png`);
  } catch (err) {
    logosFederacaoCache[chave] = null;
  }
  return logosFederacaoCache[chave];
}

async function gerarImagemAgendaStory() {
  const canvas = document.getElementById("canvas-agenda-story");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const CIANO = "#7fd4ff";
  const VERDE = "#3fd17e";
  const CINZA_AZULADO = "#8a9bb0";
  const CINZA_CLARO = "#b7cbdc";

  mostrarStatusStory("Gerando imagem...");

  const filtro = document.getElementById("agenda_export_filtro").value;
  const itens = filtro === "inscrito"
    ? itensAtuais.filter(i => i.status === "inscrito")
    : itensAtuais;

  if (!itens.length) {
    mostrarStatusStory(
      filtro === "inscrito"
        ? "Você ainda não tem nenhuma inscrição confirmada na agenda."
        : "Sua agenda está vazia — marque competições em Competições primeiro.",
      true,
    );
    return;
  }

  let fotoUrl = null;
  try {
    const respPerfil = await fetchAutenticado("/api/carreira/perfil");
    const perfil = await respPerfil.json();
    fotoUrl = perfil.foto_url || null;
  } catch (err) {
    // segue sem foto — não é essencial pra imagem
  }

  // Fundo escuro azulado, no estilo do template de referência (não o
  // gradiente azul-claro do template antigo).
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, "#0d1d33");
  grad.addColorStop(1, "#050b16");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  const brilho = ctx.createRadialGradient(W / 2, 200, 40, W / 2, 200, 480);
  brilho.addColorStop(0, "rgba(127, 212, 255, 0.14)");
  brilho.addColorStop(1, "rgba(127, 212, 255, 0)");
  ctx.fillStyle = brilho;
  ctx.fillRect(0, 0, W, H);

  desenharTarjasCanto(ctx, W, H);

  ctx.textAlign = "center";

  let yLogoFim = 70;
  try {
    const logo = await carregarImagem("img/radar-bjj-logo-3d.png");
    const larguraLogo = 360;
    const alturaLogo = larguraLogo * (logo.height / logo.width);
    ctx.drawImage(logo, W / 2 - larguraLogo / 2, 40, larguraLogo, alturaLogo);
    yLogoFim = 40 + alturaLogo;
  } catch (err) {
    // segue sem o logo se não conseguir carregar
  }

  let fotoCarregada = null;
  if (fotoUrl) {
    try {
      fotoCarregada = await carregarImagem(fotoUrl);
    } catch (err) {
      // segue com o ícone padrão se a foto não carregar
    }
  }

  // ---------- Moldura de celular ----------
  // Pedido do usuário (07/10/2026), a partir de uma arte de referência
  // que ele mandou: em vez da lista "crua" de antes, a Story agora simula
  // um print do app (moldura de celular com barra de status/cabeçalho)
  // seguido de um cartão em destaque pra PRÓXIMA competição (a lista
  // vira coisa secundária, compacta, embaixo) — dá muito mais hierarquia
  // visual que 4-5 cartões idênticos brigando por atenção.
  const xFrame = 80;
  const larguraFrame = W - xFrame * 2;
  const yFrame = yLogoFim + 30;
  const raioFrame = 56;
  const padFrame = 34;
  const alturaFrame = 326;
  const yFrameFim = yFrame + alturaFrame;

  ctx.save();
  ctx.shadowColor = "rgba(127, 212, 255, 0.55)";
  ctx.shadowBlur = 36;
  ctx.fillStyle = "#0a1830";
  roundRect(ctx, xFrame, yFrame, larguraFrame, alturaFrame, raioFrame);
  ctx.fill();
  ctx.restore();
  ctx.strokeStyle = CIANO;
  ctx.lineWidth = 3;
  roundRect(ctx, xFrame, yFrame, larguraFrame, alturaFrame, raioFrame);
  ctx.stroke();
  // "Notch" decorativo no topo da moldura — reforça a leitura de "print
  // de celular" mesmo sem existir um app nativo de verdade.
  ctx.fillStyle = "#050b16";
  roundRect(ctx, W / 2 - 70, yFrame - 4, 140, 26, 13);
  ctx.fill();

  // Barra de status: hora real (o momento em que a imagem foi gerada) +
  // ícone de bateria — só decoração, mas com hora de verdade fica menos
  // "chapa/estático" que um 9:41 fixo igual ao mockup original.
  let yCursorFrame = yFrame + padFrame + 6;
  const agora = new Date();
  const horaAtual = `${String(agora.getHours()).padStart(2, "0")}:${String(agora.getMinutes()).padStart(2, "0")}`;
  ctx.textAlign = "left";
  ctx.font = "bold 26px -apple-system, Arial, sans-serif";
  ctx.fillStyle = "#ffffff";
  ctx.fillText(horaAtual, xFrame + padFrame, yCursorFrame + 18);
  const xBateria = xFrame + larguraFrame - padFrame - 44;
  ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
  ctx.lineWidth = 2;
  roundRect(ctx, xBateria, yCursorFrame - 2, 38, 19, 4);
  ctx.stroke();
  ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
  ctx.fillRect(xBateria + 39, yCursorFrame + 4, 3, 7);
  ctx.fillRect(xBateria + 3, yCursorFrame + 1, 28, 13);

  yCursorFrame += 58;

  // Cabeçalho do app: hambúrguer à esquerda, sino à direita.
  desenharIcone(ctx, "menu", xFrame + padFrame + 15, yCursorFrame + 13, 28, "#ffffff", 2.2);
  desenharIcone(ctx, "sino", xFrame + larguraFrame - padFrame - 15, yCursorFrame + 13, 28, CIANO, 2);

  yCursorFrame += 68;

  // Avatar (foto de perfil ou ícone padrão) + "MINHA AGENDA" + sublinhado.
  const raioCirculo = 50;
  ctx.font = "bold 42px -apple-system, Arial, sans-serif";
  ctx.letterSpacing = "1px";
  const titulo = "MINHA AGENDA";
  const larguraTitulo = ctx.measureText(titulo).width;
  const xCirculo = W / 2 - larguraTitulo / 2 - raioCirculo - 20;
  const yAvatar = yCursorFrame + raioCirculo;

  ctx.fillStyle = "#0d1d33";
  ctx.beginPath();
  ctx.arc(xCirculo, yAvatar, raioCirculo, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = CIANO;
  ctx.lineWidth = 2.5;
  ctx.stroke();
  if (fotoCarregada) {
    desenharImagemCircular(ctx, fotoCarregada, xCirculo, yAvatar, raioCirculo - 5);
  } else {
    desenharIcone(ctx, "calendario", xCirculo, yAvatar, 46, CIANO, 2);
  }

  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "left";
  ctx.fillText(titulo, xCirculo + raioCirculo + 20, yAvatar + 14);
  ctx.letterSpacing = "0px";

  ctx.strokeStyle = "rgba(127, 212, 255, 0.5)";
  ctx.lineWidth = 2;
  const yLinhaTitulo = yAvatar + raioCirculo + 20;
  ctx.beginPath();
  ctx.moveTo(xCirculo - raioCirculo, yLinhaTitulo);
  ctx.lineTo(xCirculo + raioCirculo + 20 + larguraTitulo, yLinhaTitulo);
  ctx.stroke();

  // ---------- Cartão de destaque: PRÓXIMA COMPETIÇÃO ----------
  // "Estoura" por cima da borda inferior da moldura (de propósito — é o
  // mesmo efeito de profundidade da arte de referência) e é um pouco mais
  // largo que a moldura do celular, pra ficar claro que é o elemento
  // principal da imagem, não só mais um item de lista.
  const principal = itens[0];
  const restoItens = itens.slice(1);

  const xHero = xFrame - 24;
  const larguraHero = larguraFrame + 48;
  const padHero = 40;
  const yHero = yFrameFim - 46;

  const corBadgePrincipal = principal.status === "inscrito" ? VERDE : CIANO;
  const textoBadgePrincipal = principal.status === "inscrito" ? "INSCRITO" : "INTERESSE";

  // Pré-calcula a altura do nome do evento (1 ou 2 linhas) pra saber a
  // altura total do cartão antes de desenhar o fundo/borda.
  const xLogoFed = xHero + padHero;
  const ladoLogoFed = 60;
  const xNomeEvento = xLogoFed + ladoLogoFed + 20;
  const larguraNomeEvento = xHero + larguraHero - padHero - xNomeEvento;
  ctx.font = "bold 34px -apple-system, Arial, sans-serif";
  const linhasEvento = quebrarLinhas(ctx, principal.nome, larguraNomeEvento).slice(0, 2);
  const alturaBlocoEvento = Math.max(ladoLogoFed, linhasEvento.length * 40);

  const alturaHero = padHero + 46 + 22 + alturaBlocoEvento + 24 + 92 + 22 + 44 + padHero;

  // Fundo OPACO (não o "cartaoComGlow" padrão, que preenche quase
  // transparente) — o cartão "estoura" por cima da borda da moldura (ver
  // yHero acima), então precisa cobrir de verdade a linha da moldura por
  // trás dele; com fundo quase transparente, a borda da moldura vazava
  // através do cartão nos dois cantos de cima (bug visto num print real
  // gerado pelo usuário, 07/10/2026).
  ctx.save();
  ctx.shadowColor = "rgba(127, 212, 255, 0.45)";
  ctx.shadowBlur = 30;
  ctx.fillStyle = "#0a1830";
  roundRect(ctx, xHero, yHero, larguraHero, alturaHero, 28);
  ctx.fill();
  ctx.restore();
  ctx.strokeStyle = "rgba(127, 212, 255, 0.7)";
  ctx.lineWidth = 2.5;
  roundRect(ctx, xHero, yHero, larguraHero, alturaHero, 28);
  ctx.stroke();

  let yHeroCursor = yHero + padHero;

  // Linha 1: troféu + "PRÓXIMA COMPETIÇÃO" (esq.) e badge de status (dir.)
  ctx.textAlign = "left";
  desenharIcone(ctx, "trofeu", xHero + padHero + 14, yHeroCursor + 16, 30, CIANO, 2);
  ctx.font = "bold 24px -apple-system, Arial, sans-serif";
  ctx.letterSpacing = "1px";
  ctx.fillStyle = CIANO;
  ctx.fillText("PRÓXIMA COMPETIÇÃO", xHero + padHero + 40, yHeroCursor + 25);
  ctx.letterSpacing = "0px";

  ctx.font = "bold 22px -apple-system, Arial, sans-serif";
  ctx.letterSpacing = "1px";
  const larguraBadgePrincipal = ctx.measureText(textoBadgePrincipal).width + 40;
  const alturaBadgePrincipal = 44;
  const xBadgePrincipal = xHero + larguraHero - padHero - larguraBadgePrincipal;
  ctx.strokeStyle = corBadgePrincipal;
  ctx.lineWidth = 2;
  roundRect(ctx, xBadgePrincipal, yHeroCursor - 4, larguraBadgePrincipal, alturaBadgePrincipal, alturaBadgePrincipal / 2);
  ctx.stroke();
  ctx.fillStyle = corBadgePrincipal;
  ctx.textAlign = "center";
  ctx.fillText(textoBadgePrincipal, xBadgePrincipal + larguraBadgePrincipal / 2, yHeroCursor + 26);
  ctx.letterSpacing = "0px";

  yHeroCursor += 46 + 22;

  // Linha 2: logo da federação + nome do evento (até 2 linhas).
  const logoFed = await carregarLogoFederacao(principal.federacao);
  if (logoFed) {
    ctx.save();
    ctx.fillStyle = "#ffffff";
    roundRect(ctx, xLogoFed, yHeroCursor, ladoLogoFed, ladoLogoFed, 14);
    ctx.fill();
    ctx.clip();
    const escalaFed = Math.min(ladoLogoFed / logoFed.width, ladoLogoFed / logoFed.height);
    const wFed = logoFed.width * escalaFed, hFed = logoFed.height * escalaFed;
    ctx.drawImage(logoFed, xLogoFed + (ladoLogoFed - wFed) / 2, yHeroCursor + (ladoLogoFed - hFed) / 2, wFed, hFed);
    ctx.restore();
  } else {
    ctx.strokeStyle = "rgba(127, 212, 255, 0.5)";
    ctx.lineWidth = 2;
    roundRect(ctx, xLogoFed, yHeroCursor, ladoLogoFed, ladoLogoFed, 14);
    ctx.stroke();
    ctx.font = "bold 20px -apple-system, Arial, sans-serif";
    ctx.fillStyle = CIANO;
    ctx.textAlign = "center";
    ctx.fillText(principal.federacao.slice(0, 4), xLogoFed + ladoLogoFed / 2, yHeroCursor + ladoLogoFed / 2 + 7);
    ctx.textAlign = "left";
  }
  ctx.font = "bold 34px -apple-system, Arial, sans-serif";
  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "left";
  const yTextoEvento = yHeroCursor + (ladoLogoFed - linhasEvento.length * 40) / 2 + 30;
  linhasEvento.forEach((linha, i) => {
    ctx.fillText(linha, xNomeEvento, yTextoEvento + i * 40);
  });

  yHeroCursor += alturaBlocoEvento + 24;

  // Linha 3: data grande — mesma lógica de intervalo ("25-27") já usada
  // na Agenda normal (ver data_fim_iso em agenda.py::listar).
  desenharIcone(ctx, "calendario", xHero + padHero + 15, yHeroCursor + 30, 32, CIANO, 2);
  const xDataHero = xHero + padHero + 46;
  if (principal.data_iso) {
    const [ano, mes, dia] = principal.data_iso.split("-");
    const [anoFim, mesFim, diaFim] = (principal.data_fim_iso || principal.data_iso).split("-");
    const ehIntervalo = principal.data_fim_iso && principal.data_fim_iso !== principal.data_iso
      && anoFim === ano && mesFim === mes;
    const textoData = ehIntervalo
      ? `${Number(dia)} - ${Number(diaFim)}`
      : String(Number(dia));
    ctx.font = "bold 54px -apple-system, Arial, sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(textoData, xDataHero, yHeroCursor + 44);
    ctx.font = "bold 24px -apple-system, Arial, sans-serif";
    ctx.fillStyle = CIANO;
    ctx.fillText(`${MESES_ABREV[Number(mes) - 1] || ""} ${ano}`, xDataHero, yHeroCursor + 76);
  } else {
    ctx.font = "bold 28px -apple-system, Arial, sans-serif";
    ctx.fillStyle = CIANO;
    ctx.fillText(truncarTexto(ctx, principal.data || "", larguraHero - padHero * 2 - 46), xDataHero, yHeroCursor + 50);
  }

  yHeroCursor += 92 + 22;

  // Linha 4: local (pin + "Município, UF").
  if (principal.local) {
    desenharIcone(ctx, "pin", xHero + padHero + 12, yHeroCursor + 18, 26, CIANO, 2);
    ctx.font = "bold 28px -apple-system, Arial, sans-serif";
    ctx.fillStyle = CINZA_CLARO;
    ctx.fillText(
      truncarTexto(ctx, principal.local, larguraHero - padHero * 2 - 36),
      xHero + padHero + 34, yHeroCursor + 26,
    );
  }

  const yHeroFim = yHero + alturaHero;

  // ---------- Lista compacta: outras competições na agenda ----------
  let yCursorFinal = yHeroFim + 50;
  if (restoItens.length > 0) {
    ctx.font = "bold 22px -apple-system, Arial, sans-serif";
    ctx.letterSpacing = "1px";
    ctx.fillStyle = CINZA_CLARO;
    ctx.fillText("OUTRAS COMPETIÇÕES NA AGENDA", xFrame, yCursorFinal);
    ctx.letterSpacing = "0px";
    yCursorFinal += 34;

    const MAX_LINHAS = 3;
    const visiveis = restoItens.slice(0, MAX_LINHAS);
    const restantes = restoItens.length - visiveis.length;
    const alturaLinha = 104;
    const gapLinha = 16;
    const larguraLista = W - xFrame * 2;

    for (const item of visiveis) {
      const y = yCursorFinal;
      cartaoComGlow(ctx, xFrame, y, larguraLista, alturaLinha, 18, "rgba(127, 212, 255, 0.25)");
      const cy = y + alturaLinha / 2;

      const ladoLogoMini = 56;
      const xLogoMini = xFrame + 20;
      const logoMiniFed = await carregarLogoFederacao(item.federacao);
      if (logoMiniFed) {
        ctx.save();
        ctx.fillStyle = "#ffffff";
        roundRect(ctx, xLogoMini, cy - ladoLogoMini / 2, ladoLogoMini, ladoLogoMini, 12);
        ctx.fill();
        ctx.clip();
        const escalaMini = Math.min(ladoLogoMini / logoMiniFed.width, ladoLogoMini / logoMiniFed.height);
        const wMini = logoMiniFed.width * escalaMini, hMini = logoMiniFed.height * escalaMini;
        ctx.drawImage(
          logoMiniFed,
          xLogoMini + (ladoLogoMini - wMini) / 2, cy - ladoLogoMini / 2 + (ladoLogoMini - hMini) / 2,
          wMini, hMini,
        );
        ctx.restore();
      } else {
        ctx.strokeStyle = "rgba(127, 212, 255, 0.4)";
        ctx.lineWidth = 1.5;
        roundRect(ctx, xLogoMini, cy - ladoLogoMini / 2, ladoLogoMini, ladoLogoMini, 12);
        ctx.stroke();
      }

      const xTextoMini = xLogoMini + ladoLogoMini + 22;
      const xSeta = xFrame + larguraLista - 30;
      const larguraTextoMini = xSeta - 24 - xTextoMini;
      ctx.textAlign = "left";

      let textoDataMini;
      if (item.data_iso) {
        const [ano, mes, dia] = item.data_iso.split("-");
        const [anoFim, mesFim, diaFim] = (item.data_fim_iso || item.data_iso).split("-");
        const ehIntervaloMini = item.data_fim_iso && item.data_fim_iso !== item.data_iso
          && anoFim === ano && mesFim === mes;
        textoDataMini = ehIntervaloMini
          ? `${Number(dia)}-${Number(diaFim)} ${MESES_ABREV[Number(mes) - 1] || ""}`
          : `${Number(dia)} ${MESES_ABREV[Number(mes) - 1] || ""}`;
      } else {
        textoDataMini = truncarTexto(ctx, item.data || "", 100);
      }
      ctx.font = "bold 22px -apple-system, Arial, sans-serif";
      ctx.fillStyle = CIANO;
      ctx.fillText(textoDataMini, xTextoMini, cy - 14);

      ctx.font = "bold 26px -apple-system, Arial, sans-serif";
      ctx.fillStyle = "#ffffff";
      ctx.fillText(truncarTexto(ctx, item.nome, larguraTextoMini), xTextoMini, cy + 16);

      if (item.local) {
        ctx.font = "22px -apple-system, Arial, sans-serif";
        ctx.fillStyle = CINZA_AZULADO;
        ctx.fillText(truncarTexto(ctx, item.local, larguraTextoMini), xTextoMini, cy + 40);
      }

      desenharIcone(ctx, "seta", xSeta, cy, 24, "rgba(127, 212, 255, 0.6)", 2.5);

      yCursorFinal += alturaLinha + gapLinha;
    }

    if (restantes > 0) {
      ctx.textAlign = "center";
      ctx.font = "26px -apple-system, Arial, sans-serif";
      ctx.fillStyle = CINZA_CLARO;
      ctx.fillText(`+ ${restantes} outra(s) competição(ões)`, W / 2, yCursorFinal + 10);
      yCursorFinal += 46;
    }
  }

  // Rodapé — link em destaque, mesmo padrão já usado no resto do site
  // (linha — globo — url — linha).
  // Ancora o rodapé perto do fim do canvas quando sobra espaço (poucos
  // itens) — sem isso ele ficava "flutuando" no meio da imagem, com uma
  // sobra enorme de fundo vazio embaixo. Só sobe (acompanha o conteúdo)
  // quando a lista é longa o bastante pra quase encostar nele.
  const urlSite = "www.radarbjj.com";
  const yUrl = Math.min(Math.max(yCursorFinal + 50, H - 130), H - 70);
  ctx.textAlign = "center";
  ctx.font = "bold 32px -apple-system, Arial, sans-serif";
  const larguraTextoUrl = ctx.measureText(urlSite).width;
  const larguraBlocoUrl = larguraTextoUrl + 50;
  ctx.strokeStyle = "rgba(127, 212, 255, 0.5)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(60, yUrl);
  ctx.lineTo(W / 2 - larguraBlocoUrl / 2, yUrl);
  ctx.moveTo(W / 2 + larguraBlocoUrl / 2, yUrl);
  ctx.lineTo(W - 60, yUrl);
  ctx.stroke();
  desenharIcone(ctx, "globo", W / 2 - larguraTextoUrl / 2 - 26, yUrl, 26, CIANO, 2.2);
  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "left";
  ctx.fillText(urlSite, W / 2 - larguraTextoUrl / 2 + 4, yUrl + 10);
  ctx.textAlign = "center";

  canvas.toBlob(blob => {
    ultimoBlobAgendaStory = blob;
    canvas.style.display = "block";
    document.getElementById("btn-baixar-agenda-story").classList.remove("hidden");
    if (navigator.share && navigator.canShare && navigator.canShare({ files: [new File([blob], "x.png", { type: "image/png" })] })) {
      document.getElementById("btn-compartilhar-agenda-story").classList.remove("hidden");
    }
    mostrarStatusStory("Imagem gerada!");
  }, "image/png");
}

function mostrarStatusStory(texto, ehErro = false) {
  const el = document.getElementById("status-agenda-story");
  el.textContent = texto;
  el.className = "status-importacao" + (ehErro ? " erro" : "");
}

document.getElementById("btn-gerar-agenda-story").addEventListener("click", gerarImagemAgendaStory);

document.getElementById("btn-baixar-agenda-story").addEventListener("click", () => {
  if (!ultimoBlobAgendaStory) return;
  const url = URL.createObjectURL(ultimoBlobAgendaStory);
  const a = document.createElement("a");
  a.href = url;
  a.download = "radar-bjj-minha-agenda.png";
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("btn-compartilhar-agenda-story").addEventListener("click", async () => {
  if (!ultimoBlobAgendaStory) return;
  try {
    await navigator.share({
      files: [new File([ultimoBlobAgendaStory], "radar-bjj-minha-agenda.png", { type: "image/png" })],
      title: "Minhas próximas competições — Radar BJJ",
    });
  } catch (err) {
    // usuário cancelou o compartilhamento — sem problema
  }
});
