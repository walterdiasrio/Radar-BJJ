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

async function gerarImagemAgendaStory() {
  const canvas = document.getElementById("canvas-agenda-story");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const CIANO = "#7fd4ff";
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

  let yLogoFim = 90;
  try {
    const logo = await carregarImagem("img/radar-bjj-logo-3d.png");
    const larguraLogo = 460;
    const alturaLogo = larguraLogo * (logo.height / logo.width);
    ctx.drawImage(logo, W / 2 - larguraLogo / 2, 50, larguraLogo, alturaLogo);
    yLogoFim = 50 + alturaLogo;
  } catch (err) {
    // segue sem o logo se não conseguir carregar
  }

  // Cabeçalho "MINHA AGENDA": linha — círculo com a foto do perfil (ou o
  // ícone de calendário, sem foto cadastrada) — título — linha. Mesmo
  // ícone de calendário usado no menu do site (ver ICONES_STORY).
  const yTitulo = yLogoFim + 80;
  const raioCirculo = 60;
  ctx.font = "bold 46px -apple-system, Arial, sans-serif";
  ctx.letterSpacing = "1px";
  const titulo = "MINHA AGENDA";
  const larguraTitulo = ctx.measureText(titulo).width;
  const xCirculo = W / 2 - larguraTitulo / 2 - raioCirculo - 24;

  ctx.fillStyle = "#0d1d33";
  ctx.beginPath();
  ctx.arc(xCirculo, yTitulo, raioCirculo, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = CIANO;
  ctx.lineWidth = 2.5;
  ctx.stroke();
  let fotoCarregada = null;
  if (fotoUrl) {
    try {
      fotoCarregada = await carregarImagem(fotoUrl);
    } catch (err) {
      // segue com o ícone padrão se a foto não carregar
    }
  }
  if (fotoCarregada) {
    desenharImagemCircular(ctx, fotoCarregada, xCirculo, yTitulo, raioCirculo - 5);
  } else {
    desenharIcone(ctx, "calendario", xCirculo, yTitulo, 56, CIANO, 2);
  }

  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "left";
  ctx.fillText(titulo, xCirculo + raioCirculo + 24, yTitulo + 16);
  ctx.letterSpacing = "0px";

  ctx.strokeStyle = "rgba(127, 212, 255, 0.6)";
  ctx.lineWidth = 2;
  const xLinhaEsq = xCirculo - raioCirculo - 20;
  const xLinhaDir = xCirculo + raioCirculo + 24 + larguraTitulo + 20;
  ctx.beginPath();
  ctx.moveTo(60, yTitulo);
  ctx.lineTo(xLinhaEsq, yTitulo);
  ctx.moveTo(xLinhaDir, yTitulo);
  ctx.lineTo(W - 60, yTitulo);
  ctx.stroke();

  // "PRÓXIMAS COMPETIÇÕES", alinhado à esquerda com uma linha se
  // estendendo até a margem direita — mesmo padrão do template de
  // referência.
  const margem = 54;
  const larguraCartao = W - margem * 2;
  const yRotulo = yTitulo + 90;
  ctx.font = "bold 24px -apple-system, Arial, sans-serif";
  ctx.letterSpacing = "1.5px";
  ctx.fillStyle = CIANO;
  const rotulo = "PRÓXIMAS COMPETIÇÕES";
  ctx.fillText(rotulo, margem, yRotulo);
  const larguraRotulo = ctx.measureText(rotulo).width;
  ctx.letterSpacing = "0px";
  ctx.strokeStyle = "rgba(127, 212, 255, 0.35)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(margem + larguraRotulo + 24, yRotulo - 8);
  ctx.lineTo(margem + larguraCartao, yRotulo - 8);
  ctx.stroke();

  let yTopo = yRotulo + 30;

  // Lista de competições — um cartão por item, com bloco de data (dia
  // grande / mês / ano), evento e o badge de status (Inscrição Confirmada
  // / Tenho Interesse). Cabe um número limitado de cartões no Stories; o
  // resto vira um resumo "+N outras". Teto fixo de 5 mesmo quando sobraria
  // espaço pra mais — com muitas competições, cartão pequeno/lotado fica
  // ilegível no Stories, então preferimos mostrar só as próximas 5 (bem
  // destacadas) e resumir o restante no "+N outras".
  const MAX_CARTOES = 5;
  const alturaCartaoBase = 230;
  const alturaCartaoMax = 280;
  const gap = 24;
  const alturaRodape = 40 + 64; // gap + linha do site (sem QR — mais espaço pra competições)
  const margemInferior = 70;
  const alturaDisponivelParaLista = H - yTopo - alturaRodape - margemInferior;
  const maxCartoes = Math.min(
    MAX_CARTOES,
    Math.max(1, Math.floor((alturaDisponivelParaLista + gap) / (alturaCartaoBase + gap))),
  );
  const visiveis = itens.slice(0, maxCartoes);
  const restantes = itens.length - visiveis.length;

  let alturaCartao = alturaCartaoBase;
  if (visiveis.length > 0) {
    const alturaTotalPadrao = visiveis.length * alturaCartaoBase + (visiveis.length - 1) * gap;
    if (alturaTotalPadrao < alturaDisponivelParaLista) {
      alturaCartao = Math.min(
        alturaCartaoMax,
        alturaCartaoBase + (alturaDisponivelParaLista - alturaTotalPadrao) / visiveis.length,
      );
    }
  }

  const alturaListaReal = visiveis.length * (alturaCartao + gap) - gap + (restantes > 0 ? 60 : 0);
  const alturaConteudoReal = alturaListaReal + alturaRodape;
  const espacoLivre = Math.max(0, H - yTopo - alturaConteudoReal - margemInferior);
  const yListaTopo = yTopo + espacoLivre / 2;

  // Os cartões crescem além da altura-base quando sobra espaço (poucos
  // itens na agenda) — sem isso o texto ficava sempre no tamanho mínimo
  // mesmo com o cartão bem maior, desperdiçando o espaço extra. Escala
  // linear: 1x na altura-base, até ~1.24x na altura máxima.
  const escalaTexto = alturaCartao / alturaCartaoBase;
  const fonteDia = Math.round(64 * escalaTexto);
  const fonteMes = Math.round(28 * escalaTexto);
  const fonteAno = Math.round(23 * escalaTexto);
  const fonteDataBruta = Math.round(24 * escalaTexto);
  const fonteNome = Math.round(36 * escalaTexto);
  const fonteLocal = Math.round(30 * escalaTexto);
  const fonteBadge = Math.round(20 * escalaTexto);
  const alturaLinhaNome = Math.round(46 * escalaTexto);
  const alturaLinhaLocal = Math.round(40 * escalaTexto);

  visiveis.forEach((item, i) => {
    const y = yListaTopo + i * (alturaCartao + gap);
    const cy = y + alturaCartao / 2;
    cartaoComGlow(ctx, margem, y, larguraCartao, alturaCartao, 20, "rgba(127, 212, 255, 0.3)");

    // Bloco de data (dia / mês / ano), à esquerda, centralizado na altura
    // do card — usa data_iso (já vem parseada do back, ver agenda.listar);
    // sem data reconhecível, cai pro texto bruto centralizado no lugar.
    const xData = margem + 30;
    if (item.data_iso) {
      const [ano, mes, dia] = item.data_iso.split("-");
      ctx.textAlign = "left";
      ctx.font = `bold ${fonteDia}px -apple-system, Arial, sans-serif`;
      ctx.fillStyle = "#ffffff";
      ctx.fillText(String(Number(dia)), xData, cy - 16 * escalaTexto);
      ctx.font = `bold ${fonteMes}px -apple-system, Arial, sans-serif`;
      ctx.fillStyle = CIANO;
      ctx.fillText(MESES_ABREV[Number(mes) - 1] || "", xData, cy + 19 * escalaTexto);
      ctx.font = `${fonteAno}px -apple-system, Arial, sans-serif`;
      ctx.fillStyle = CINZA_AZULADO;
      ctx.fillText(ano, xData, cy + 48 * escalaTexto);
    } else {
      ctx.textAlign = "left";
      ctx.font = `bold ${fonteDataBruta}px -apple-system, Arial, sans-serif`;
      ctx.fillStyle = CIANO;
      truncarTexto(ctx, item.data || "", 130).split(" ").slice(0, 3).forEach((linha, li) => {
        ctx.fillText(linha, xData, cy - 10 + li * 26 * escalaTexto);
      });
    }

    // Divisória vertical entre a data e o conteúdo.
    const xDivisor = margem + 145;
    ctx.strokeStyle = "rgba(127, 212, 255, 0.3)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(xDivisor, y + 24);
    ctx.lineTo(xDivisor, y + alturaCartao - 24);
    ctx.stroke();

    // Badge + sino, à direita, centralizados na altura do card.
    const textoBadge = item.status === "inscrito" ? "INSCRITO" : "INTERESSE";
    const corBadge = item.status === "inscrito" ? "#3fd17e" : "#7fd4ff";
    ctx.font = `bold ${fonteBadge}px -apple-system, Arial, sans-serif`;
    ctx.letterSpacing = "1px";
    const larguraBadge = ctx.measureText(textoBadge).width + 36;
    const alturaBadge = Math.round(42 * escalaTexto);
    const xSino = margem + larguraCartao - 30 - 18;
    const xBadge = xSino - 30 - larguraBadge;
    const yBadge = cy - alturaBadge / 2;
    ctx.strokeStyle = corBadge;
    ctx.lineWidth = 2;
    roundRect(ctx, xBadge, yBadge, larguraBadge, alturaBadge, alturaBadge / 2);
    ctx.stroke();
    ctx.fillStyle = corBadge;
    ctx.textAlign = "center";
    ctx.fillText(textoBadge, xBadge + larguraBadge / 2, yBadge + alturaBadge * 0.64);
    ctx.letterSpacing = "0px";
    desenharIcone(ctx, "sino", xSino, cy, Math.round(30 * escalaTexto), CIANO, 1.8);

    // Conteúdo: bolinha + federação — nome (até 2 linhas) + local (linha
    // extra, com pin e negrito pra dar destaque à cidade/estado) — bloco
    // inteiro centralizado verticalmente no card.
    const xTexto = xDivisor + 30;
    const larguraTexto = xBadge - 24 - xTexto;
    ctx.textAlign = "left";

    ctx.font = `bold ${fonteNome}px -apple-system, Arial, sans-serif`;
    const larguraFed = ctx.measureText(item.federacao + " —").width;
    const linhasNome = quebrarLinhas(ctx, item.nome, larguraTexto);
    ctx.font = `${fonteNome}px -apple-system, Arial, sans-serif`;
    const primeiraLinha = truncarTexto(ctx, linhasNome[0] || "", larguraTexto - larguraFed - 10);

    const totalLinhas = 1 + (linhasNome[1] ? 1 : 0);
    const alturaBlocoTexto = totalLinhas * alturaLinhaNome + (item.local ? alturaLinhaLocal : 0);
    let yCursor = cy - alturaBlocoTexto / 2 + alturaLinhaNome * 0.72;

    ctx.fillStyle = CIANO;
    ctx.beginPath();
    ctx.arc(xDivisor + 12, yCursor - 10, 6, 0, Math.PI * 2);
    ctx.fill();

    ctx.font = `bold ${fonteNome}px -apple-system, Arial, sans-serif`;
    ctx.fillStyle = CIANO;
    ctx.fillText(item.federacao + " —", xTexto, yCursor);
    ctx.font = `${fonteNome}px -apple-system, Arial, sans-serif`;
    ctx.fillStyle = "#ffffff";
    ctx.fillText(primeiraLinha, xTexto + larguraFed + 10, yCursor);
    yCursor += alturaLinhaNome;

    if (linhasNome[1]) {
      ctx.fillText(truncarTexto(ctx, linhasNome[1], larguraTexto), xTexto, yCursor);
      yCursor += alturaLinhaNome;
    }

    if (item.local) {
      const ladoPin = Math.round(22 * escalaTexto);
      desenharIcone(ctx, "pin", xTexto + ladoPin / 2, yCursor - Math.round(fonteLocal * 0.32), ladoPin, CIANO, 2);
      ctx.font = `bold ${fonteLocal}px -apple-system, Arial, sans-serif`;
      ctx.fillStyle = CINZA_CLARO;
      ctx.fillText(truncarTexto(ctx, item.local, larguraTexto - ladoPin - 8), xTexto + ladoPin + 8, yCursor);
    }
  });
  ctx.textAlign = "center";

  let yFimLista = yListaTopo + visiveis.length * (alturaCartao + gap) - gap;
  if (restantes > 0) {
    ctx.font = "28px -apple-system, Arial, sans-serif";
    ctx.fillStyle = CINZA_CLARO;
    ctx.fillText(`+ ${restantes} outra(s) competição(ões)`, W / 2, yFimLista + 44);
    yFimLista += 60;
  }

  // Rodapé — link em destaque, mesmo padrão do template de referência
  // (linha — globo — url — linha). Sem QR code aqui (removido pra sobrar
  // espaço pra mais um cartão de competição na lista).
  const urlSite = "www.radarbjj.com";
  const yUrl = Math.min(yFimLista + 60, H - 90);
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
