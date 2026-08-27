const elNoticia = document.getElementById("noticia-detalhe");
const elStatus = document.getElementById("status");

async function carregarNoticia() {
  const partes = location.pathname.split("/").filter(Boolean);
  const id = partes[partes.length - 1];
  try {
    const resp = await fetch(`/api/noticias/${id}`);
    if (!resp.ok) {
      elStatus.textContent = "Notícia não encontrada.";
      return;
    }
    const n = await resp.json();
    document.title = `Radar BJJ — ${n.manchete}`;
    elNoticia.innerHTML = `
      <img src="${n.imagem_url}" alt="" class="noticia-detalhe-imagem">
      <h1 class="noticia-detalhe-manchete"></h1>
      <div class="noticia-detalhe-texto"></div>
    `;
    elNoticia.querySelector(".noticia-detalhe-imagem").alt = n.manchete;
    elNoticia.querySelector(".noticia-detalhe-manchete").textContent = n.manchete;
    elNoticia.querySelector(".noticia-detalhe-texto").textContent = n.texto || "";
  } catch (err) {
    elStatus.textContent = `Erro ao carregar notícia: ${err.message}`;
    elStatus.className = "erro";
  }
}

carregarNoticia();
