"""Minha Carreira — cada atleta assinante registra o próprio histórico de
competições (perfil, competições com as lutas de cada uma, e estatísticas
calculadas em cima disso). Inspirado no app pessoal que o admin já usa pra
acompanhar a carreira do Vini Bulbasauro, mas multiusuário e com banco de
verdade em vez de localStorage + Google Sheets.
"""
import os
import sqlite3
import uuid
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "carreira.db"
DIR_FOTOS = DATA_DIR / "perfil_fotos"

RESULTADOS = ("vitoria", "derrota", "empate")
METODOS = ("pontos", "finalizacao", "wo", "desclassificacao", "medica")
MEDALHAS = ("ouro", "prata", "bronze")

EXTENSOES_FOTO_PERMITIDAS = {"jpg", "jpeg", "png", "webp"}
TAMANHO_FOTO_PERFIL = 300  # px — foto quadrada; o recorte redondo é feito via CSS onde ela aparece.

PERFIL_PADRAO = {
    "avatar": "🥋", "nome": "", "faixa": "Branca", "grau": "0",
    "categoria": "", "academia": "", "inicio": "", "foto_arquivo": None,
}


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS perfis_atleta (
                usuario_id INTEGER PRIMARY KEY,
                avatar TEXT NOT NULL DEFAULT '🥋',
                nome TEXT NOT NULL DEFAULT '',
                faixa TEXT NOT NULL DEFAULT 'Branca',
                grau TEXT NOT NULL DEFAULT '0',
                categoria TEXT NOT NULL DEFAULT '',
                academia TEXT NOT NULL DEFAULT '',
                inicio TEXT
            )
        """)
        # foto_arquivo entrou depois que a tabela já existia em produção.
        colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(perfis_atleta)")}
        if "foto_arquivo" not in colunas:
            conn.execute("ALTER TABLE perfis_atleta ADD COLUMN foto_arquivo TEXT")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS competicoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                campeonato TEXT NOT NULL DEFAULT '',
                data TEXT NOT NULL,
                categoria TEXT NOT NULL DEFAULT '',
                pais TEXT NOT NULL DEFAULT 'Brasil',
                medalha TEXT,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lutas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competicao_id INTEGER NOT NULL REFERENCES competicoes(id) ON DELETE CASCADE,
                adversario TEXT NOT NULL DEFAULT '',
                resultado TEXT NOT NULL,
                metodo TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_competicoes_usuario ON competicoes(usuario_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lutas_competicao ON lutas(competicao_id)")

        # Vínculo Mestre-Atleta pra "Meus Alunos": criado quando qualquer um
        # dos dois lados adiciona o nome de usuário do outro (ver app.py) —
        # não exige confirmação da outra parte, é informal por design.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vinculos (
                mestre_id INTEGER NOT NULL,
                aluno_id INTEGER NOT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (mestre_id, aluno_id)
            )
        """)


def obter_perfil(usuario_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT * FROM perfis_atleta WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
    if not linha:
        return {**PERFIL_PADRAO, "usuario_id": usuario_id}
    return dict(linha)


def criar_vinculo(mestre_id, aluno_id):
    if mestre_id == aluno_id:
        return False, "não dá pra se adicionar como próprio aluno"
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO vinculos (mestre_id, aluno_id) VALUES (?, ?)",
            (mestre_id, aluno_id),
        )
    return True, None


def remover_vinculo(mestre_id, aluno_id):
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM vinculos WHERE mestre_id = ? AND aluno_id = ?", (mestre_id, aluno_id)
        )
        return cursor.rowcount > 0


def vinculo_existe(mestre_id, aluno_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT 1 FROM vinculos WHERE mestre_id = ? AND aluno_id = ?", (mestre_id, aluno_id)
        ).fetchone()
    return linha is not None


def listar_ids_alunos_do_mestre(mestre_id):
    """Só os IDs — não exige que o aluno já tenha preenchido Minha Carreira,
    senão um vínculo recém-criado "sumiria" até a outra parte preencher algo.
    Quem chama enriquece com nome/e-mail (perfil pode nem existir ainda)."""
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT aluno_id FROM vinculos WHERE mestre_id = ? ORDER BY criado_em", (mestre_id,)
        ).fetchall()
    return [linha["aluno_id"] for linha in linhas]


def listar_ids_mestres_do_aluno(aluno_id):
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT mestre_id FROM vinculos WHERE aluno_id = ? ORDER BY criado_em", (aluno_id,)
        ).fetchall()
    return [linha["mestre_id"] for linha in linhas]


def buscar_atletas_por_academia(academia, excluir_ids=()):
    """Atletas cujo perfil (Minha Carreira) tem a academia igual à
    informada (comparação sem diferenciar maiúsculas/minúsculas) — usado
    pelo Mestre em Meus Alunos pra achar/adicionar alunos da própria
    academia sem precisar saber o nome de usuário de cada um."""
    academia = (academia or "").strip()
    if not academia:
        return []
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT * FROM perfis_atleta WHERE LOWER(academia) = LOWER(?) ORDER BY nome", (academia,)
        ).fetchall()
    return [dict(linha) for linha in linhas if linha["usuario_id"] not in excluir_ids]


def salvar_perfil(usuario_id, dados):
    perfil = {
        "avatar": (dados.get("avatar") or "🥋").strip() or "🥋",
        "nome": (dados.get("nome") or "").strip(),
        "faixa": (dados.get("faixa") or "Branca").strip() or "Branca",
        "grau": str(dados.get("grau") or "0"),
        "categoria": (dados.get("categoria") or "").strip(),
        "academia": (dados.get("academia") or "").strip(),
        "inicio": (dados.get("inicio") or "").strip() or None,
    }
    with _conn() as conn:
        existe = conn.execute(
            "SELECT usuario_id FROM perfis_atleta WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
        if existe:
            conn.execute(
                """UPDATE perfis_atleta SET avatar=?, nome=?, faixa=?, grau=?,
                   categoria=?, academia=?, inicio=? WHERE usuario_id=?""",
                (*perfil.values(), usuario_id),
            )
        else:
            conn.execute(
                """INSERT INTO perfis_atleta
                   (usuario_id, avatar, nome, faixa, grau, categoria, academia, inicio)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (usuario_id, *perfil.values()),
            )
        # Devolve a linha inteira (não só os campos que esse formulário
        # manda) pra incluir foto_arquivo, que é editado num formulário
        # separado (ver salvar_foto_perfil) e não pode ser perdido aqui.
        linha = conn.execute(
            "SELECT * FROM perfis_atleta WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
    return dict(linha)


def _extensao(nome_arquivo):
    return (nome_arquivo or "").rsplit(".", 1)[-1].lower() if "." in (nome_arquivo or "") else ""


def salvar_foto_perfil(usuario_id, arquivo_imagem, nome_original):
    """arquivo_imagem é o FileStorage do Flask (request.files[...]). Recorta
    pro quadrado central e redimensiona pra TAMANHO_FOTO_PERFIL — o formato
    redondo em si é aplicado via CSS (border-radius) onde a foto aparece, não
    no arquivo salvo. Retorna (nome_arquivo, erro)."""
    ext = _extensao(nome_original)
    if ext not in EXTENSOES_FOTO_PERMITIDAS:
        return None, "imagem inválida (use jpg, png ou webp)"

    from PIL import Image, ImageOps

    try:
        imagem = Image.open(arquivo_imagem.stream)
        imagem = ImageOps.exif_transpose(imagem)  # corrige rotação de fotos tiradas com celular
        imagem = imagem.convert("RGB")
    except Exception:
        return None, "não consegui ler essa imagem"

    lado = min(imagem.size)
    esquerda = (imagem.width - lado) // 2
    topo = (imagem.height - lado) // 2
    imagem = imagem.crop((esquerda, topo, esquerda + lado, topo + lado))
    imagem = imagem.resize((TAMANHO_FOTO_PERFIL, TAMANHO_FOTO_PERFIL), Image.LANCZOS)

    DIR_FOTOS.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"{usuario_id}-{uuid.uuid4().hex}.jpg"
    imagem.save(DIR_FOTOS / nome_arquivo, "JPEG", quality=88, optimize=True)

    with _conn() as conn:
        antiga = conn.execute(
            "SELECT foto_arquivo FROM perfis_atleta WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
        if antiga:
            conn.execute(
                "UPDATE perfis_atleta SET foto_arquivo = ? WHERE usuario_id = ?", (nome_arquivo, usuario_id)
            )
        else:
            conn.execute(
                """INSERT INTO perfis_atleta (usuario_id, avatar, nome, faixa, grau, categoria, academia, foto_arquivo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (usuario_id, PERFIL_PADRAO["avatar"], "", "Branca", "0", "", "", nome_arquivo),
            )
        if antiga and antiga["foto_arquivo"]:
            caminho_antigo = DIR_FOTOS / antiga["foto_arquivo"]
            if caminho_antigo.exists():
                caminho_antigo.unlink()

    return nome_arquivo, None


def remover_foto_perfil(usuario_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT foto_arquivo FROM perfis_atleta WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
        if not linha or not linha["foto_arquivo"]:
            return False
        caminho = DIR_FOTOS / linha["foto_arquivo"]
        if caminho.exists():
            caminho.unlink()
        conn.execute("UPDATE perfis_atleta SET foto_arquivo = NULL WHERE usuario_id = ?", (usuario_id,))
    return True


def _validar_lutas(lutas_brutas):
    lutas = []
    for l in lutas_brutas or []:
        resultado = l.get("resultado")
        metodo = l.get("metodo")
        if resultado not in RESULTADOS or metodo not in METODOS:
            return None, "resultado ou método de luta inválido"
        lutas.append({
            "adversario": (l.get("adversario") or "").strip(),
            "resultado": resultado,
            "metodo": metodo,
        })
    return lutas, None


def criar_competicao(usuario_id, dados):
    """Retorna (competicao_id, erro)."""
    data = (dados.get("data") or "").strip()
    if not data:
        return None, "informe a data"

    medalha = dados.get("medalha") or None
    if medalha and medalha not in MEDALHAS:
        return None, "medalha inválida"

    lutas, erro = _validar_lutas(dados.get("lutas"))
    if erro:
        return None, erro

    with _conn() as conn:
        cursor = conn.execute(
            """INSERT INTO competicoes (usuario_id, campeonato, data, categoria, pais, medalha)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                usuario_id,
                (dados.get("campeonato") or "").strip(),
                data,
                (dados.get("categoria") or "").strip(),
                (dados.get("pais") or "Brasil").strip() or "Brasil",
                medalha,
            ),
        )
        competicao_id = cursor.lastrowid
        for l in lutas:
            conn.execute(
                "INSERT INTO lutas (competicao_id, adversario, resultado, metodo) VALUES (?, ?, ?, ?)",
                (competicao_id, l["adversario"], l["resultado"], l["metodo"]),
            )
    return competicao_id, None


def atualizar_competicao(usuario_id, competicao_id, dados):
    """Retorna (ok, erro)."""
    data = (dados.get("data") or "").strip()
    if not data:
        return False, "informe a data"

    medalha = dados.get("medalha") or None
    if medalha and medalha not in MEDALHAS:
        return False, "medalha inválida"

    lutas, erro = _validar_lutas(dados.get("lutas"))
    if erro:
        return False, erro

    with _conn() as conn:
        dona = conn.execute(
            "SELECT id FROM competicoes WHERE id = ? AND usuario_id = ?", (competicao_id, usuario_id)
        ).fetchone()
        if not dona:
            return False, "competição não encontrada"

        conn.execute(
            """UPDATE competicoes SET campeonato=?, data=?, categoria=?, pais=?, medalha=?
               WHERE id = ?""",
            (
                (dados.get("campeonato") or "").strip(),
                data,
                (dados.get("categoria") or "").strip(),
                (dados.get("pais") or "Brasil").strip() or "Brasil",
                medalha,
                competicao_id,
            ),
        )
        conn.execute("DELETE FROM lutas WHERE competicao_id = ?", (competicao_id,))
        for l in lutas:
            conn.execute(
                "INSERT INTO lutas (competicao_id, adversario, resultado, metodo) VALUES (?, ?, ?, ?)",
                (competicao_id, l["adversario"], l["resultado"], l["metodo"]),
            )
    return True, None


def remover_competicao(usuario_id, competicao_id):
    with _conn() as conn:
        dona = conn.execute(
            "SELECT id FROM competicoes WHERE id = ? AND usuario_id = ?", (competicao_id, usuario_id)
        ).fetchone()
        if not dona:
            return False
        conn.execute("DELETE FROM competicoes WHERE id = ?", (competicao_id,))
    return True


def _competicoes_com_lutas(conn, usuario_id, filtros=None):
    filtros = filtros or {}
    query = "SELECT * FROM competicoes WHERE usuario_id = ?"
    params = [usuario_id]

    if filtros.get("campeonato"):
        query += " AND campeonato LIKE ?"
        params.append(f"%{filtros['campeonato']}%")
    if filtros.get("de"):
        query += " AND data >= ?"
        params.append(filtros["de"])
    if filtros.get("ate"):
        query += " AND data <= ?"
        params.append(filtros["ate"])

    query += " ORDER BY data DESC, id DESC"
    competicoes = [dict(linha) for linha in conn.execute(query, params).fetchall()]

    adversario_filtro = (filtros.get("adversario") or "").lower()
    resultado = []
    for c in competicoes:
        lutas = [
            dict(linha) for linha in conn.execute(
                "SELECT * FROM lutas WHERE competicao_id = ? ORDER BY id", (c["id"],)
            ).fetchall()
        ]
        if adversario_filtro and not any(adversario_filtro in (l["adversario"] or "").lower() for l in lutas):
            continue
        c["lutas"] = lutas
        resultado.append(c)
    return resultado


def listar_competicoes(usuario_id, filtros=None):
    with _conn() as conn:
        return _competicoes_com_lutas(conn, usuario_id, filtros)


def calcular_estatisticas(usuario_id):
    with _conn() as conn:
        competicoes = _competicoes_com_lutas(conn, usuario_id)

    lutas = []
    for c in competicoes:
        for l in c["lutas"]:
            lutas.append({**l, "data": c["data"]})
    lutas.sort(key=lambda l: l["data"] or "")

    vitorias = [l for l in lutas if l["resultado"] == "vitoria"]
    derrotas = [l for l in lutas if l["resultado"] == "derrota"]
    empates = [l for l in lutas if l["resultado"] == "empate"]
    total_lutas = len(lutas)
    taxa_vitoria = round(len(vitorias) / total_lutas * 100) if total_lutas else 0

    melhor_sequencia = 0
    sequencia_atual = 0
    corrente = 0
    for l in lutas:
        if l["resultado"] == "vitoria":
            corrente += 1
            melhor_sequencia = max(melhor_sequencia, corrente)
        else:
            corrente = 0
    sequencia_atual = corrente

    ouros = sum(1 for c in competicoes if c["medalha"] == "ouro")
    pratas = sum(1 for c in competicoes if c["medalha"] == "prata")
    bronzes = sum(1 for c in competicoes if c["medalha"] == "bronze")

    finalizacoes = sum(1 for l in vitorias if l["metodo"] == "finalizacao")
    vitorias_pontos = sum(1 for l in vitorias if l["metodo"] == "pontos")
    campeonatos_diferentes = len({c["campeonato"] for c in competicoes if c["campeonato"]})
    paises_diferentes = len({c["pais"] for c in competicoes if c["pais"]})

    cumulativo = 0
    grafico = []
    for l in lutas:
        if l["resultado"] == "vitoria":
            cumulativo += 1
        grafico.append({"data": l["data"], "resultado": l["resultado"], "vitorias_acumuladas": cumulativo})

    return {
        "competicoes": len(competicoes),
        "lutas": total_lutas,
        "vitorias": len(vitorias),
        "derrotas": len(derrotas),
        "empates": len(empates),
        "taxa_vitoria": taxa_vitoria,
        "sequencia_atual": sequencia_atual,
        "melhor_sequencia": melhor_sequencia,
        "ouros": ouros,
        "pratas": pratas,
        "bronzes": bronzes,
        "finalizacoes": finalizacoes,
        "vitorias_pontos": vitorias_pontos,
        "campeonatos_diferentes": campeonatos_diferentes,
        "paises_diferentes": paises_diferentes,
        "grafico": grafico,
    }
