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
      card.addEventListener("click", () => { location.href = `/noticias/${noticia.id}`; });
    });
  } catch (err) {
    elStatus.textContent = `Erro ao carregar notícias: ${err.message}`;
    elStatus.className = "erro";
  }
}

carregarNoticias();
