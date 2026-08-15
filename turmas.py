"""Turmas — cada Mestre organiza suas aulas em turmas (Baby, Kids,
Adolescente, Adulto) com horário de início/fim, e opcionalmente coloca
alunos dela dentro. Só aceita alunos já vinculados ao Mestre em Meus
Alunos (ver app.py) — turmas não criam vínculo novo, só organizam quem
já é aluno."""
import calendar
import json
import os
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "turmas.db"

CATEGORIAS = ("Baby", "Kids", "Adolescente", "Adulto")
DIAS_SEMANA = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")

# Posições/técnicas disponíveis pro Plano de Aula, agrupadas pra exibição —
# lista fixa (não cadastrada pelo usuário) pra manter o registro consistente
# entre turmas e ao longo do tempo.
POSICOES = {
    "Guardas": [
        "Guarda Fechada", "Guarda Aberta", "Meia Guarda", "Guarda Borboleta",
        "De La Riva", "Guarda Aranha", "50/50",
    ],
    "Passagens de Guarda": [
        "Passagem por Pressão", "Passagem Torreando", "Passagem Leg Drag", "Passagem de Joelho",
    ],
    "Posições Dominantes": [
        "Montada", "100kg (Side Control)", "Joelho na Barriga", "Costas", "Norte-Sul",
    ],
    "Raspagens": [
        "Raspagem de Guarda Fechada", "Raspagem Flower Sweep", "Raspagem Scissor",
        "Raspagem Hip Bump", "Raspagem De La Riva",
    ],
    "Quedas": [
        "Double Leg", "Single Leg", "Queda de Judô",
    ],
    "Finalizações — Chaves de Braço": [
        "Armlock", "Kimura", "Americana", "Omoplata",
    ],
    "Finalizações — Estrangulamentos": [
        "Mata-Leão", "Triângulo", "Guilhotina", "Ezekiel",
    ],
    "Finalizações — Chaves de Perna": [
        "Chave de Pé Reta", "Chave de Calcanhar", "Toe Hold",
    ],
    "Fundamentos / Escapes": [
        "Fuga de Quadril", "Escape de Montada", "Escape de 100kg", "Pontes (Bridge)",
    ],
}
_TODAS_POSICOES = {posicao for lista in POSICOES.values() for posicao in lista}

# Chaves de calcanhar e toe hold machucam articulação em desenvolvimento —
# IBJJF e a maioria das federações só liberam a partir de Adolescente/Adulto.
# Chave de pé reta fica de fora dessa lista (já é liberada mais cedo).
POSICOES_ADULTO_APENAS = {"Chave de Calcanhar", "Toe Hold"}

_DIA_SEMANA_INDICE = {dia: i for i, dia in enumerate(DIAS_SEMANA)}


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS turmas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mestre_id INTEGER NOT NULL,
                nome TEXT NOT NULL DEFAULT '',
                categoria TEXT NOT NULL,
                horario_inicio TEXT NOT NULL,
                horario_fim TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # dias_semana entrou depois que a tabela já existia em produção —
        # ALTER TABLE em vez de recriar, pra não perder turmas já criadas.
        colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(turmas)")}
        if "dias_semana" not in colunas:
            conn.execute("ALTER TABLE turmas ADD COLUMN dias_semana TEXT NOT NULL DEFAULT '[]'")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS turma_alunos (
                turma_id INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
                aluno_id INTEGER NOT NULL,
                PRIMARY KEY (turma_id, aluno_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_turmas_mestre ON turmas(mestre_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS planos_aula (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turma_id INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
                data TEXT NOT NULL,
                posicoes TEXT NOT NULL DEFAULT '[]',
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_planos_aula_turma ON planos_aula(turma_id)")

        # Controla o limite de 1 geração de Plano de Aula IA por Mestre por
        # dia (a chamada à API da Claude é paga) — ver gerar_plano_ia.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plano_ia_uso (
                mestre_id INTEGER PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)


def _validar_dados(dados):
    categoria = (dados.get("categoria") or "").strip()
    if categoria not in CATEGORIAS:
        return None, f"categoria inválida (use: {', '.join(CATEGORIAS)})"
    horario_inicio = (dados.get("horario_inicio") or "").strip()
    horario_fim = (dados.get("horario_fim") or "").strip()
    if not horario_inicio or not horario_fim:
        return None, "informe horário de início e fim"
    dias_semana = [d for d in (dados.get("dias_semana") or []) if d in DIAS_SEMANA]
    nome = (dados.get("nome") or "").strip()
    return {
        "nome": nome,
        "categoria": categoria,
        "horario_inicio": horario_inicio,
        "horario_fim": horario_fim,
        "dias_semana": dias_semana,
    }, None


def criar_turma(mestre_id, dados):
    """Retorna (turma_id, erro)."""
    validado, erro = _validar_dados(dados)
    if erro:
        return None, erro
    with _conn() as conn:
        cursor = conn.execute(
            """INSERT INTO turmas (mestre_id, nome, categoria, horario_inicio, horario_fim, dias_semana)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                mestre_id, validado["nome"], validado["categoria"], validado["horario_inicio"],
                validado["horario_fim"], json.dumps(validado["dias_semana"], ensure_ascii=False),
            ),
        )
        return cursor.lastrowid, None


def atualizar_turma(mestre_id, turma_id, dados):
    """Retorna (ok, erro)."""
    validado, erro = _validar_dados(dados)
    if erro:
        return False, erro
    with _conn() as conn:
        dona = conn.execute(
            "SELECT id FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        ).fetchone()
        if not dona:
            return False, "turma não encontrada"
        conn.execute(
            "UPDATE turmas SET nome=?, categoria=?, horario_inicio=?, horario_fim=?, dias_semana=? WHERE id=?",
            (
                validado["nome"], validado["categoria"], validado["horario_inicio"],
                validado["horario_fim"], json.dumps(validado["dias_semana"], ensure_ascii=False), turma_id,
            ),
        )
    return True, None


def remover_turma(mestre_id, turma_id):
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        )
        return cursor.rowcount > 0


def listar_turmas(mestre_id):
    with _conn() as conn:
        turmas = [
            dict(linha) for linha in conn.execute(
                "SELECT * FROM turmas WHERE mestre_id = ? ORDER BY horario_inicio, id", (mestre_id,)
            ).fetchall()
        ]
        for t in turmas:
            t["dias_semana"] = json.loads(t["dias_semana"]) if t.get("dias_semana") else []
            alunos = conn.execute(
                "SELECT aluno_id FROM turma_alunos WHERE turma_id = ? ORDER BY aluno_id", (t["id"],)
            ).fetchall()
            t["aluno_ids"] = [linha["aluno_id"] for linha in alunos]
    return turmas


def turma_pertence_ao_mestre(mestre_id, turma_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT 1 FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        ).fetchone()
    return linha is not None


def adicionar_aluno(mestre_id, turma_id, aluno_id):
    """Retorna (ok, erro). Quem chama já deve ter checado que aluno_id é
    de fato aluno desse mestre (ver carreira.vinculo_existe)."""
    with _conn() as conn:
        dona = conn.execute(
            "SELECT id FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        ).fetchone()
        if not dona:
            return False, "turma não encontrada"
        conn.execute(
            "INSERT OR IGNORE INTO turma_alunos (turma_id, aluno_id) VALUES (?, ?)", (turma_id, aluno_id)
        )
    return True, None


def remover_aluno(mestre_id, turma_id, aluno_id):
    with _conn() as conn:
        dona = conn.execute(
            "SELECT id FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        ).fetchone()
        if not dona:
            return False
        conn.execute(
            "DELETE FROM turma_alunos WHERE turma_id = ? AND aluno_id = ?", (turma_id, aluno_id)
        )
    return True


def criar_plano_aula(mestre_id, turma_id, dados):
    """Retorna (plano_id, erro)."""
    if not turma_pertence_ao_mestre(mestre_id, turma_id):
        return None, "turma não encontrada"

    data = (dados.get("data") or "").strip()
    if not data:
        return None, "informe a data da aula"

    posicoes = [p for p in (dados.get("posicoes") or []) if p in _TODAS_POSICOES]
    if not posicoes:
        return None, "selecione pelo menos uma posição"

    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO planos_aula (turma_id, data, posicoes) VALUES (?, ?, ?)",
            (turma_id, data, json.dumps(posicoes, ensure_ascii=False)),
        )
        return cursor.lastrowid, None


def listar_planos_aula(mestre_id, turma_id):
    if not turma_pertence_ao_mestre(mestre_id, turma_id):
        return []
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT * FROM planos_aula WHERE turma_id = ? ORDER BY data DESC, id DESC", (turma_id,)
        ).fetchall()
    planos = []
    for linha in linhas:
        plano = dict(linha)
        plano["posicoes"] = json.loads(plano["posicoes"]) if plano["posicoes"] else []
        planos.append(plano)
    return planos


def remover_plano_aula(mestre_id, turma_id, plano_id):
    if not turma_pertence_ao_mestre(mestre_id, turma_id):
        return False
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM planos_aula WHERE id = ? AND turma_id = ?", (plano_id, turma_id)
        )
        return cursor.rowcount > 0


def _proximas_datas_do_mes(dias_semana, limite=8):
    """Datas do PRÓXIMO mês (a partir de hoje) que caem nos dias da semana
    da turma. Sem dias da semana cadastrados, cai pro mesmo dia da semana
    de hoje (só pra sempre devolver algo)."""
    hoje = date.today()
    if hoje.month == 12:
        ano, mes = hoje.year + 1, 1
    else:
        ano, mes = hoje.year, hoje.month + 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]

    indices = {_DIA_SEMANA_INDICE[d] for d in dias_semana if d in _DIA_SEMANA_INDICE}
    if not indices:
        indices = {hoje.weekday()}

    datas = [date(ano, mes, dia) for dia in range(1, ultimo_dia + 1) if date(ano, mes, dia).weekday() in indices]
    return datas[:limite] if limite else datas


def sugerir_plano_mensal(mestre_id, turma_id, foco, posicoes_por_aula=2):
    """Sugestão de plano de aula pro próximo mês (não salva nada — o
    Mestre revisa e decide o que registrar de fato). Cicla pelas posições
    do foco escolhido que essa turma MENOS treinou até agora (as nunca
    treinadas vêm primeiro), pulando posições de adulto quando a turma é
    Baby/Kids. Retorna (resultado, erro)."""
    if foco not in POSICOES:
        return None, f"foco inválido (use: {', '.join(POSICOES.keys())})"

    with _conn() as conn:
        turma = conn.execute(
            "SELECT * FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        ).fetchone()
        if not turma:
            return None, "turma não encontrada"
        turma = dict(turma)
        turma["dias_semana"] = json.loads(turma["dias_semana"]) if turma["dias_semana"] else []

        historico = conn.execute(
            "SELECT posicoes FROM planos_aula WHERE turma_id = ?", (turma_id,)
        ).fetchall()

    pool = list(POSICOES[foco])
    if turma["categoria"] in ("Baby", "Kids"):
        pool = [p for p in pool if p not in POSICOES_ADULTO_APENAS]
    if not pool:
        return None, "não há posições liberadas pra essa categoria dentro desse foco"

    contagem = Counter()
    for linha in historico:
        for posicao in json.loads(linha["posicoes"]):
            if posicao in pool:
                contagem[posicao] += 1
    for posicao in pool:
        contagem.setdefault(posicao, 0)

    ordenadas = sorted(pool, key=lambda p: (contagem[p], p))

    datas = _proximas_datas_do_mes(turma["dias_semana"])
    if not datas:
        return None, "não consegui calcular datas pro próximo mês"

    sugestao = []
    indice = 0
    n = len(ordenadas)
    for dia in datas:
        qtd = min(posicoes_por_aula, n)
        escolhidas = [ordenadas[(indice + i) % n] for i in range(qtd)]
        indice += qtd
        sugestao.append({"data": dia.isoformat(), "posicoes": escolhidas})

    return {"foco": foco, "categoria": turma["categoria"], "aulas": sugestao}, None


def _chamar_claude_plano(turma, foco, resumo, pool, datas):
    import anthropic

    with _conn() as conn:
        historico = conn.execute(
            "SELECT data, posicoes FROM planos_aula WHERE turma_id = ? ORDER BY data DESC LIMIT 30", (turma["id"],)
        ).fetchall()
    historico_texto = "\n".join(
        f"- {linha['data']}: {', '.join(json.loads(linha['posicoes']))}" for linha in historico
    ) or "(nenhuma aula registrada ainda)"

    prompt = f"""Você é um assistente de um professor (Mestre) de Jiu-Jitsu montando o plano de aulas do próximo mês para uma turma.

Dados da turma:
- Categoria: {turma['categoria']}
- Dias de aula na semana: {', '.join(turma['dias_semana']) or '(não definido)'}
- Datas das próximas aulas no mês: {', '.join(d.isoformat() for d in datas)}

Histórico de aulas já dadas (mais recentes primeiro, até 30):
{historico_texto}

Posições/técnicas permitidas para escolher (use exatamente esses nomes, não invente outros):
{', '.join(pool)}

{"Foco solicitado pelo Mestre: " + foco if foco else "Nenhum foco específico foi escolhido — distribua entre as posições permitidas."}
{("O que o Mestre quer para esse plano: " + resumo) if resumo else ""}

Monte uma sugestão de plano de aula, uma entrada para cada uma das datas acima, escolhendo 2 posições por aula
(sempre da lista permitida), priorizando o que essa turma menos treinou e o que o Mestre pediu no resumo. Se a
categoria for Baby ou Kids, nunca sugira Chave de Calcanhar nem Toe Hold.

Responda APENAS com um JSON válido, sem nenhum texto antes ou depois, exatamente neste formato:
{{"aulas": [{{"data": "YYYY-MM-DD", "posicoes": ["posição 1", "posição 2"], "observacao": "breve explicação de 1 frase do porquê dessa escolha"}}]}}"""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    texto = "".join(bloco.text for bloco in response.content if bloco.type == "text").strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.startswith("json"):
            texto = texto[4:]
    dados = json.loads(texto)

    validas = []
    for aula in dados.get("aulas") or []:
        data = aula.get("data")
        posicoes = [p for p in (aula.get("posicoes") or []) if p in pool]
        if turma["categoria"] in ("Baby", "Kids"):
            posicoes = [p for p in posicoes if p not in POSICOES_ADULTO_APENAS]
        if not data or not posicoes:
            continue
        validas.append({"data": data, "posicoes": posicoes, "observacao": aula.get("observacao", "")})

    if not validas:
        raise ValueError("resposta da IA sem aulas válidas")
    return {"foco": foco or "Geral", "categoria": turma["categoria"], "aulas": validas}


LIMITE_CARACTERES_RESUMO_IA = 200


def _pode_usar_plano_ia_hoje(mestre_id):
    hoje = date.today().isoformat()
    with _conn() as conn:
        linha = conn.execute(
            "SELECT data FROM plano_ia_uso WHERE mestre_id = ?", (mestre_id,)
        ).fetchone()
    return not linha or linha["data"] != hoje


def _registrar_uso_plano_ia(mestre_id):
    hoje = date.today().isoformat()
    with _conn() as conn:
        conn.execute(
            """INSERT INTO plano_ia_uso (mestre_id, data) VALUES (?, ?)
               ON CONFLICT(mestre_id) DO UPDATE SET data = excluded.data""",
            (mestre_id, hoje),
        )


def gerar_plano_ia(mestre_id, turma_id, foco, resumo, posicoes_por_aula=2):
    """Sugestão de plano de aula pro próximo mês usando IA (Claude), levando em
    conta o resumo em texto livre do Mestre (limitado a
    LIMITE_CARACTERES_RESUMO_IA caracteres). Cai pra sugestão determinística
    (sugerir_plano_mensal) — sem chamar a API, então sem custo — se: a API não
    estiver configurada (sem ANTHROPIC_API_KEY), o Mestre já tiver usado a IA
    hoje (1x/dia — a chamada é paga) ou a chamada falhar. Retorna
    (resultado, erro); resultado tem uma chave 'ia' indicando se veio da IA de
    fato ou do fallback, e 'aviso' quando o motivo do fallback é o limite
    diário (pra avisar o Mestre na tela)."""
    resumo = (resumo or "").strip()[:LIMITE_CARACTERES_RESUMO_IA]

    if foco and foco not in POSICOES:
        return None, f"foco inválido (use: {', '.join(POSICOES.keys())})"

    with _conn() as conn:
        turma = conn.execute(
            "SELECT * FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        ).fetchone()
        if not turma:
            return None, "turma não encontrada"
        turma = dict(turma)
        turma["dias_semana"] = json.loads(turma["dias_semana"]) if turma["dias_semana"] else []

    pool = list(POSICOES[foco]) if foco else list(_TODAS_POSICOES)
    if turma["categoria"] in ("Baby", "Kids"):
        pool = [p for p in pool if p not in POSICOES_ADULTO_APENAS]
    if not pool:
        return None, "não há posições liberadas pra essa categoria dentro desse foco"

    datas = _proximas_datas_do_mes(turma["dias_semana"])
    if not datas:
        return None, "não consegui calcular datas pro próximo mês"

    def _fallback():
        resultado, erro = sugerir_plano_mensal(
            mestre_id, turma_id, foco or next(iter(POSICOES)), posicoes_por_aula
        )
        if erro:
            return None, erro
        resultado["ia"] = False
        return resultado, None

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _fallback()

    if not _pode_usar_plano_ia_hoje(mestre_id):
        resultado, erro = _fallback()
        if resultado:
            resultado["aviso"] = (
                "Você já usou o Plano de Aula IA hoje (limite de 1x por dia) — "
                "essa sugestão foi gerada automaticamente, sem IA. Tente de novo amanhã."
            )
        return resultado, erro

    try:
        resultado = _chamar_claude_plano(turma, foco, resumo, pool, datas)
        resultado["ia"] = True
        _registrar_uso_plano_ia(mestre_id)
        return resultado, None
    except Exception:
        return _fallback()
