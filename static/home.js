async function carregarDestaques() {
  const elDestaques = document.getElementById("destaques");
  if (!elDestaques) return;
  try {
    const resp = await fetch("/api/noticias");
    const lista = await resp.json();
    if (!lista.length) {
      elDestaques.innerHTML = "";
      return;
    }
    elDestaques.innerHTML = `
      <h2 class="destaques-titulo">BJJ News</h2>
      <div class="destaques-grade">
        ${lista.map((n, i) => `
          <div class="destaque-card" data-indice="${i}">
            <img src="${n.imagem_url}" alt="${n.manchete}">
            <div class="destaque-manchete">${n.manchete}</div>
          </div>
        `).join("")}
      </div>
    `;
    elDestaques.querySelectorAll(".destaque-card").forEach(card => {
      const noticia = lista[Number(card.dataset.indice)];
      card.addEventListener("click", () => abrirNoticiaModal(noticia.imagem_url, noticia.manchete, noticia.texto));
    });
  } catch (err) {
    elDestaques.innerHTML = "";
  }
}

carregarDestaques();
