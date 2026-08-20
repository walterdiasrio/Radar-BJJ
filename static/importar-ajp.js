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

async function fetchImportacao(url, corpo) {
  let resp;
  try {
    resp = await fetchAutenticado(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
  } catch {
    // fetch() rejeitou antes de chegar resposta nenhuma (não é erro do
    // servidor) — normalmente conexão instável ou o servidor reiniciando
    // (ex: bem no meio de um deploy). Vale tentar de novo.
    throw new Error("erro de conexão com o servidor — verifique sua internet e tente de novo em alguns segundos");
  }
  const dados = await resp.json();
  if (!resp.ok) throw new Error(dados.erro || "erro ao importar");
  return dados;
}

elArquivoEvento.addEventListener("change", async () => {
  const arquivo = elArquivoEvento.files[0];
  if (!arquivo) return;

  mostrarStatus(elStatusEvento, "Lendo e importando...");
  elArquivoAtletas.disabled = true;

  try {
    const html = await lerArquivoComoTexto(arquivo);
    const dados = await fetchImportacao("/api/ajp/importar-evento", { html });

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
    const dados = await fetchImportacao("/api/ajp/importar-atletas", { evento_id: eventoAtual.id, html });

    mostrarStatus(elStatusAtletas, `${dados.total} atleta(s) importado(s) com sucesso.`);
  } catch (err) {
    mostrarStatus(elStatusAtletas, `Erro: ${err.message}`, true);
  }
});

const elBtnVerificarDrive = document.getElementById("btn-verificar-drive");
const elStatusDriveImport = document.getElementById("status-drive-import");

elBtnVerificarDrive.addEventListener("click", async () => {
  elBtnVerificarDrive.disabled = true;
  mostrarStatus(elStatusDriveImport, "Verificando pasta do Drive...");
  try {
    const resp = await fetchAutenticado("/api/drive-import/verificar-agora", { method: "POST" });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui verificar");
    mostrarStatus(elStatusDriveImport, (dados.log || []).join("\n"));
  } catch (err) {
    mostrarStatus(elStatusDriveImport, `Erro: ${err.message}`, true);
  } finally {
    elBtnVerificarDrive.disabled = false;
  }
});
