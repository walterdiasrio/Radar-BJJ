const elDestaques = document.getElementById("destaques");
const elStatus = document.getElementById("status");

async function carregarNoticias() {
  try {
    const resp = await fetch("/api/noticias");
    const lista = await resp.json();
    if (!lista.length) {
      elStatus.textContent = "Nenhuma notícia publicada ainda.";
      return;
    }
    elStatus.textContent = "";
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
    elStatus.textContent = `Erro ao carregar notícias: ${err.message}`;
    elStatus.className = "erro";
  }
}

carregarNoticias();
