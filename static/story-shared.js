// Helpers compartilhados pelos templates de imagem pra Stories (Minha
// Carreira → Compartilhar e Minha Agenda → Compartilhar) — mesmo fundo,
// cards, ícones e bloco de QR code nos dois, pra manter a identidade visual
// consistente em qualquer imagem gerada pelo site.

function carregarImagem(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function cartaoComGlow(ctx, x, y, w, h, r, corBorda) {
  ctx.save();
  ctx.fillStyle = "rgba(255, 255, 255, 0.04)";
  roundRect(ctx, x, y, w, h, r);
  ctx.fill();
  ctx.strokeStyle = corBorda;
  ctx.lineWidth = 1.5;
  roundRect(ctx, x, y, w, h, r);
  ctx.stroke();
  ctx.restore();
}

function truncarTexto(ctx, texto, larguraMax) {
  if (ctx.measureText(texto).width <= larguraMax) return texto;
  let cortado = texto;
  while (cortado.length > 1 && ctx.measureText(cortado + "…").width > larguraMax) {
    cortado = cortado.slice(0, -1);
  }
  return cortado + "…";
}

// Ícones vetoriais no mesmo estilo "line art" (traço fino, pontas
// arredondadas) já usado nos ícones de menu do site inteiro — em vez de
// emoji, que renderiza diferente (e às vezes bem feio) em cada aparelho.
// Desenhados num viewBox 24x24, escalados/centralizados em (cx, cy).
const ICONES_STORY = {
  // Mesmo path do ícone "Competições" do menu.
  trofeu: ["M8 21h8", "M12 17v4", "M7 4h10v5a5 5 0 0 1-10 0V4Z", "M7 5H4v1a4 4 0 0 0 4 4", "M17 5h3v1a4 4 0 0 1-4 4"],
  // Mesmo path do ícone "Minha Carreira" do menu (medalha/fita).
  medalha: ["M12 8m-5 0a5 5 0 1 0 10 0a5 5 0 1 0 -10 0", "M8.5 12.5 7 22l5-3 5 3-1.5-9.5"],
  // Mesmo path do ícone "Minha Agenda"/"Turmas" do menu (calendário).
  calendario: ["M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z", "M16 2v4", "M8 2v4", "M3 10h18"],
  // Mesmo path do ícone "Meus Alertas" do menu (sino).
  sino: ["M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9", "M13.73 21a2 2 0 0 1-3.46 0"],
};

function desenharIconePath(ctx, nome, cx, cy, tamanho, cor, largura = 1.8) {
  const escala = tamanho / 24;
  ctx.save();
  ctx.translate(cx - tamanho / 2, cy - tamanho / 2);
  ctx.scale(escala, escala);
  ctx.strokeStyle = cor;
  ctx.lineWidth = largura / escala;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  (ICONES_STORY[nome] || []).forEach(d => ctx.stroke(new Path2D(d)));
  ctx.restore();
}

// Ícones geométricos simples, desenhados na mão (sem path SVG externo) —
// mesma linguagem visual (traço fino arredondado), pros conceitos que não
// têm um ícone equivalente já usado no menu do site.
function desenharIconeGeometrico(ctx, nome, cx, cy, tamanho, cor, largura = 3) {
  ctx.save();
  ctx.strokeStyle = cor;
  ctx.fillStyle = cor;
  ctx.lineWidth = largura;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  const r = tamanho / 2;

  if (nome === "alvo") {
    [r, r * 0.62, r * 0.24].forEach((raio, i) => {
      ctx.beginPath();
      ctx.arc(cx, cy, raio, 0, Math.PI * 2);
      if (i === 2) ctx.fill(); else ctx.stroke();
    });
  } else if (nome === "tendencia") {
    ctx.beginPath();
    ctx.moveTo(cx - r, cy + r * 0.5);
    ctx.lineTo(cx - r * 0.25, cy - r * 0.1);
    ctx.lineTo(cx + r * 0.25, cy + r * 0.35);
    ctx.lineTo(cx + r, cy - r * 0.6);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx + r * 0.35, cy - r * 0.6);
    ctx.lineTo(cx + r, cy - r * 0.6);
    ctx.lineTo(cx + r, cy - r * 0.6 + r * 0.55);
    ctx.stroke();
  } else if (nome === "raio") {
    ctx.beginPath();
    ctx.moveTo(cx + r * 0.15, cy - r);
    ctx.lineTo(cx - r * 0.55, cy + r * 0.15);
    ctx.lineTo(cx - r * 0.05, cy + r * 0.15);
    ctx.lineTo(cx - r * 0.15, cy + r);
    ctx.lineTo(cx + r * 0.55, cy - r * 0.15);
    ctx.lineTo(cx + r * 0.05, cy - r * 0.15);
    ctx.closePath();
    ctx.fill();
  } else if (nome === "bandeira") {
    ctx.beginPath();
    ctx.moveTo(cx - r * 0.5, cy - r);
    ctx.lineTo(cx - r * 0.5, cy + r);
    ctx.stroke();
    roundRect(ctx, cx - r * 0.5, cy - r, r * 1.4, r * 0.9, 2);
    ctx.stroke();
  } else if (nome === "pin") {
    ctx.beginPath();
    ctx.arc(cx, cy - r * 0.25, r * 0.62, Math.PI * 0.15, Math.PI * 0.85, true);
    ctx.lineTo(cx, cy + r);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx, cy - r * 0.25, r * 0.22, 0, Math.PI * 2);
    ctx.stroke();
  } else if (nome === "luta") {
    // Dois "bastões" cruzados com uma pontinha marcada em cada extremidade
    // — representa embate/luta, sem ícone equivalente já usado no menu.
    const pontas = [
      [cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7],
      [cx - r * 0.7, cy + r * 0.7, cx + r * 0.7, cy - r * 0.7],
    ];
    pontas.forEach(([x1, y1, x2, y2]) => {
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(x1, y1, r * 0.14, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(x2, y2, r * 0.14, 0, Math.PI * 2);
      ctx.fill();
    });
  } else if (nome === "globo") {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(cx, cy, r * 0.42, r, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx - r, cy);
    ctx.lineTo(cx + r, cy);
    ctx.stroke();
  }
  ctx.restore();
}

// Desenha um ícone por nome, seja ele vetorial (reaproveitado do menu) ou
// geométrico (desenhado na mão) — quem chama não precisa saber qual dos
// dois é.
function desenharIcone(ctx, nome, cx, cy, tamanho, cor, largura) {
  if (ICONES_STORY[nome]) {
    desenharIconePath(ctx, nome, cx, cy, tamanho, cor, largura);
  } else {
    desenharIconeGeometrico(ctx, nome, cx, cy, tamanho, cor, largura);
  }
}

// Medalha "cheia" (disco + fita) pro pódio de Minha Carreira — usa a
// mesma silhueta do ícone de menu "Minha Carreira", só que preenchida em
// vez de contorno, colorida por posição (ouro/prata/bronze).
function desenharMedalhaColorida(ctx, cx, cy, raio, cor) {
  ctx.save();
  ctx.fillStyle = cor;
  ctx.beginPath();
  ctx.moveTo(cx - raio * 0.35, cy - raio * 0.85);
  ctx.lineTo(cx - raio * 0.8, cy - raio * 1.9);
  ctx.lineTo(cx - raio * 0.15, cy - raio * 1.9);
  ctx.lineTo(cx + raio * 0.1, cy - raio * 0.85);
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(cx + raio * 0.35, cy - raio * 0.85);
  ctx.lineTo(cx + raio * 0.8, cy - raio * 1.9);
  ctx.lineTo(cx + raio * 0.15, cy - raio * 1.9);
  ctx.lineTo(cx - raio * 0.1, cy - raio * 0.85);
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  ctx.arc(cx, cy, raio, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.6)";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();
}

// Altura fixa do bloco de QR code — não depende do conteúdo, então quem
// monta o layout pode somar isso na conta de "quanto de altura o rodapé
// inteiro vai ocupar" antes mesmo de desenhar (ver ALTURA_BLOCO_QR).
const LADO_QR = 190;
const PADDING_BLOCO_QR = 22;
const ALTURA_BLOCO_QR = LADO_QR + PADDING_BLOCO_QR * 2;

// Bloco "escaneie" — QR code (biblioteca vendorizada em qrcode.min.js, 100%
// client-side, sem chamada de rede: um QR carregado de uma API externa
// "contaminaria" o canvas e quebraria o toBlob()/compartilhamento) dentro
// de um cartão branco (contraste alto = leitura confiável pela câmera),
// com um título curto ao lado explicando a ação. Retorna a altura total
// ocupada, pra quem chama poder calcular o que vem depois.
function desenharBlocoQrCode(ctx, { x, y, largura, url, titulo, subtitulo }) {
  const ladoQr = LADO_QR;
  const padding = PADDING_BLOCO_QR;
  const alturaBloco = ALTURA_BLOCO_QR;

  cartaoComGlow(ctx, x, y, largura, alturaBloco, 24, "rgba(127, 212, 255, 0.35)");

  const xQr = x + padding;
  const yQr = y + padding;
  ctx.fillStyle = "#ffffff";
  roundRect(ctx, xQr, yQr, ladoQr, ladoQr, 12);
  ctx.fill();

  const qr = qrcode(0, "M");
  qr.addData(url);
  qr.make();
  const modulos = qr.getModuleCount();
  const quietZone = 2;
  const tamanhoModulo = ladoQr / (modulos + quietZone * 2);
  ctx.fillStyle = "#0b1d2e";
  for (let linha = 0; linha < modulos; linha++) {
    for (let coluna = 0; coluna < modulos; coluna++) {
      if (qr.isDark(linha, coluna)) {
        ctx.fillRect(
          xQr + (coluna + quietZone) * tamanhoModulo,
          yQr + (linha + quietZone) * tamanhoModulo,
          tamanhoModulo + 0.5,
          tamanhoModulo + 0.5,
        );
      }
    }
  }

  const xTexto = xQr + ladoQr + 32;
  const larguraTexto = x + largura - xTexto - 24;
  ctx.textAlign = "left";
  ctx.font = "bold 34px -apple-system, Arial, sans-serif";
  ctx.fillStyle = "#ffffff";
  quebrarLinhas(ctx, titulo, larguraTexto).forEach((linha, i) => {
    ctx.fillText(linha, xTexto, y + padding + 42 + i * 42);
  });
  if (subtitulo) {
    ctx.font = "24px -apple-system, Arial, sans-serif";
    ctx.fillStyle = "#b7cbdc";
    const yBase = y + padding + 42 + quebrarLinhas(ctx, titulo, larguraTexto).length * 42 + 14;
    quebrarLinhas(ctx, subtitulo, larguraTexto).forEach((linha, i) => {
      ctx.fillText(linha, xTexto, yBase + i * 32);
    });
  }
  ctx.textAlign = "center";

  return alturaBloco;
}

// Desenha uma imagem já carregada (ver carregarImagem) recortada num
// círculo de raio `raio` centrado em (cx, cy) — cobre o círculo inteiro
// (crop, sem distorcer), igual a um avatar de perfil.
function desenharImagemCircular(ctx, img, cx, cy, raio) {
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, raio, 0, Math.PI * 2);
  ctx.closePath();
  ctx.clip();
  const lado = Math.min(img.width, img.height);
  const sx = (img.width - lado) / 2;
  const sy = (img.height - lado) / 2;
  ctx.drawImage(img, sx, sy, lado, lado, cx - raio, cy - raio, raio * 2, raio * 2);
  ctx.restore();
}

// Tarjas diagonais decorativas nos dois cantos inferiores — mesmo detalhe
// visual do template de referência (Minha Agenda), reaproveitável em
// qualquer Story pra fechar o visual sem deixar canto vazio.
function desenharTarjasCanto(ctx, W, H, cor = "rgba(127, 212, 255, 0.35)") {
  const desenhaTarja = (x0, direcao) => {
    ctx.save();
    ctx.strokeStyle = cor;
    ctx.lineWidth = 14;
    for (let i = 0; i < 4; i++) {
      const offset = i * 22;
      ctx.beginPath();
      ctx.moveTo(x0 + direcao * offset, H);
      ctx.lineTo(x0 + direcao * (offset + 50), H - 60);
      ctx.stroke();
    }
    ctx.restore();
  };
  desenhaTarja(0, 1);
  desenhaTarja(W, -1);
}

function quebrarLinhas(ctx, texto, larguraMax) {
  const palavras = texto.split(" ");
  const linhas = [];
  let atual = "";
  palavras.forEach(palavra => {
    const tentativa = atual ? `${atual} ${palavra}` : palavra;
    if (ctx.measureText(tentativa).width > larguraMax && atual) {
      linhas.push(atual);
      atual = palavra;
    } else {
      atual = tentativa;
    }
  });
  if (atual) linhas.push(atual);
  return linhas;
}
