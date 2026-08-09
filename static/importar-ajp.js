const elArquivoEvento = document.getElementById("arquivo-evento");
const elArquivoAtletas = document.getElementById("arquivo-atletas");
const elStatusEvento = document.getElementById("status-evento");
const elStatusAtletas = document.getElementById("status-atletas");

let eventoAtual = null;

function lerArquivoComoTexto(arquivo) {
  return new Promise((resolve, reject) => {
    const leitor = new FileReader();
    leitor.onload = () => resolve(leitor.result);
    leitor.onerror = () => reject(new Error("não consegui ler o arquivo"));
    leitor.readAsText(arquivo, "utf-8");
  });
}

function mostrarStatus(el, texto, ehErro = false) {
  el.textContent = texto;
  el.className = "status-importacao" + (ehErro ? " erro" : "");
}

elArquivoEvento.addEventListener("change", async () => {
  const arquivo = elArquivoEvento.files[0];
  if (!arquivo) return;

  mostrarStatus(elStatusEvento, "Lendo e importando...");
  elArquivoAtletas.disabled = true;

  try {
    const html = await lerArquivoComoTexto(arquivo);
    const resp = await fetchAutenticado("/api/ajp/importar-evento", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ html }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao importar evento");

    eventoAtual = dados.evento;
    mostrarStatus(
      elStatusEvento,
      `"${eventoAtual.nome}" — ${eventoAtual.data || "data não encontrada"} — ${eventoAtual.local || "local não encontrado"}`
    );
    elArquivoAtletas.disabled = false;
  } catch (err) {
    mostrarStatus(elStatusEvento, `Erro: ${err.message}`, true);
    eventoAtual = null;
  }
});

elArquivoAtletas.addEventListener("change", async () => {
  const arquivo = elArquivoAtletas.files[0];
  if (!arquivo || !eventoAtual) return;

  mostrarStatus(elStatusAtletas, "Lendo e importando (pode levar alguns segundos)...");

  try {
    const html = await lerArquivoComoTexto(arquivo);
    const resp = await fetchAutenticado("/api/ajp/importar-atletas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ evento_id: eventoAtual.id, html }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao importar atletas");

    mostrarStatus(elStatusAtletas, `${dados.total} atleta(s) importado(s) com sucesso.`);
  } catch (err) {
    mostrarStatus(elStatusAtletas, `Erro: ${err.message}`, true);
  }
});
