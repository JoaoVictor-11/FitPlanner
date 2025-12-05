from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import random
import math

# -------------------------
# Config
# -------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FITPLANNER_SECRET', 'troque_esta_chave_para_producao')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fitplanner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Uploads
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# -------------------------
# Models
# -------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    foto = db.Column(db.String(200), default=None)
    theme = db.Column(db.String(20), default="dark")  # default dark

class Treino(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    dias_semana_id = db.Column(db.Integer)
    grupo_muscular = db.Column(db.String(120))
    exercicio = db.Column(db.String(120))
    series = db.Column(db.Integer)
    repeticoes = db.Column(db.Integer)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -------------------------
# Helpers
# -------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def build_plan(nivel, objetivo, divisao, dias, peso, altura, idade):
    """
    Gera um plano semanal (lista de dicts) com treinos mais realistas:
    - retorna dia como string: "Seg","Ter",...
    - suporta divisões: livre, abc, abcd, abcde, ppl, upperlower, ppl_ul
    - alterna Perna A / Perna B quando aplicável
    Saída: lista de itens {'dia': 'Seg'|'Ter'|..., 'grupo': str, 'exercicio': str, 'series': int, 'repeticoes': int, 'tipo': str, 'progressao': str}
    """
    # catálogo de exercícios com tipo, equipamento e dificuldade (1-5)
    EXS = [
        # Peito
        ("Supino reto", "Peito", "composto", "barra/halteres", 4),
        ("Supino inclinado", "Peito", "composto", "barra/halteres", 4),
        ("Crucifixo", "Peito", "isolamento", "halteres", 2),
        ("Flexão de braço", "Peito", "composto", "peso_corpo", 3),
        ("Fly máquina", "Peito", "isolamento", "máquina", 2),

        # Costas
        ("Levantamento terra", "Costas", "composto", "barra", 5),
        ("Puxada alta", "Costas", "composto", "máquina", 4),
        ("Remada curvada", "Costas", "composto", "barra/halteres", 4),
        ("Remada baixa", "Costas", "composto", "máquina", 3),
        ("Barra fixa", "Costas", "composto", "peso_corpo", 4),
        ("Remada T-bar", "Costas", "composto", "barra", 4),
        ("Puxada neutra", "Costas", "composto", "máquina", 3),
        ("Remada unilateral halter", "Costas", "composto", "halteres", 3),

        # Pernas (variedade expandida)
        ("Agachamento livre", "Pernas", "composto", "barra", 5),
        ("Agachamento frontal", "Pernas", "composto", "barra", 5),
        ("Agachamento no Smith", "Pernas", "composto", "smith", 4),
        ("Leg press 45°", "Pernas", "composto", "máquina", 4),
        ("Leg press horizontal", "Pernas", "composto", "máquina", 4),
        ("Hack machine", "Pernas", "composto", "máquina", 4),
        ("Stiff", "Pernas", "composto", "barra", 4),
        ("Stiff romeno", "Pernas", "composto", "barra", 4),
        ("Avanço / Afundo", "Pernas", "composto", "halteres", 3),
        ("Passada com halteres", "Pernas", "composto", "halteres", 3),
        ("Agachamento búlgaro", "Pernas", "composto", "halteres", 3),
        ("Cadeira extensora", "Pernas", "isolamento", "máquina", 2),
        ("Cadeira flexora", "Pernas", "isolamento", "máquina", 2),
        ("Mesa flexora", "Pernas", "isolamento", "máquina", 2),
        ("Panturrilha em pé", "Pernas", "isolamento", "máquina", 2),
        ("Panturrilha sentado", "Pernas", "isolamento", "máquina", 2),
        ("Panturrilha no leg press", "Pernas", "isolamento", "máquina", 2),
        ("Hip thrust", "Pernas", "composto", "barra", 4),
        ("Elevação pélvica", "Pernas", "isolamento", "banco", 2),
        ("Glúteo 4 apoios máquina", "Pernas", "isolamento", "máquina", 2),
        ("Glúteo na polia", "Pernas", "isolamento", "polia", 2),
        ("Levantamento terra sumô", "Pernas", "composto", "barra", 4),
        ("Step-up no banco", "Pernas", "composto", "halteres", 3),
        ("Cadeira adutora", "Pernas", "isolamento", "máquina", 2),
        ("Cadeira abdutora", "Pernas", "isolamento", "máquina", 2),
        ("Agachamento hack", "Pernas", "composto", "máquina", 4),
        ("Avanço no Smith", "Pernas", "composto", "smith", 3),

        # Ombro
        ("Desenvolvimento militar", "Ombro", "composto", "barra/halteres", 4),
        ("Elevação lateral", "Ombro", "isolamento", "halteres", 2),
        ("Elevação frontal", "Ombro", "isolamento", "halteres", 2),
        ("Remada alta", "Ombro", "composto", "barra", 3),

        # Braços / Bíceps
        ("Rosca direta", "Bíceps", "isolamento", "barra", 3),
        ("Rosca alternada", "Bíceps", "isolamento", "halteres", 2),
        ("Rosca martelo", "Bíceps", "isolamento", "halteres", 2),
        ("Rosca scott", "Bíceps", "isolamento", "máquina", 2),
        ("Rosca concentrada", "Bíceps", "isolamento", "halteres", 2),

        # Tríceps
        ("Tríceps corda", "Tríceps", "isolamento", "polia", 2),
        ("Paralelas", "Tríceps", "composto", "peso_corpo", 3),
        ("Tríceps testa", "Tríceps", "isolamento", "barra/halteres", 3),

        # Core / condicionamento
        ("Prancha", "Core", "isolamento", "peso_corpo", 1),
        ("Elevação de pernas", "Core", "isolamento", "peso_corpo", 1),
        ("Farmer's walk (caminhada)", "Core", "composto", "halteres", 2),
    ]

    # PERNA A e PERNA B blocos (usados para alternar) - nomes coerentes com EXS
    PERNA_A = [
        {"grupo":"Pernas","nome":"Agachamento livre","tipo":"composto"},
        {"grupo":"Pernas","nome":"Leg press 45°","tipo":"composto"},
        {"grupo":"Pernas","nome":"Hack machine","tipo":"composto"},
        {"grupo":"Pernas","nome":"Cadeira extensora","tipo":"isolamento"},
        {"grupo":"Pernas","nome":"Passada com halteres","tipo":"composto"},
        {"grupo":"Pernas","nome":"Agachamento búlgaro","tipo":"composto"},
        {"grupo":"Pernas","nome":"Hip thrust","tipo":"composto"},
        {"grupo":"Pernas","nome":"Step-up no banco","tipo":"composto"},
    ]

    PERNA_B = [
        {"grupo":"Pernas","nome":"Stiff romeno","tipo":"composto"},
        {"grupo":"Pernas","nome":"Stiff","tipo":"composto"},
        {"grupo":"Pernas","nome":"Mesa flexora","tipo":"isolamento"},
        {"grupo":"Pernas","nome":"Glúteo 4 apoios máquina","tipo":"isolamento"},
        {"grupo":"Pernas","nome":"Elevação pélvica","tipo":"isolamento"},
        {"grupo":"Pernas","nome":"Levantamento terra sumô","tipo":"composto"},
        {"grupo":"Pernas","nome":"Panturrilha em pé","tipo":"isolamento"},
        {"grupo":"Pernas","nome":"Panturrilha sentado","tipo":"isolamento"},
    ]

    # montar dicionário por grupo (do catálogo EXS)
    grupos = {}
    for nome, prim, tipo, equip, dif in EXS:
        grupos.setdefault(prim, []).append({"nome": nome, "tipo": tipo, "dif": dif})

    # garantir que "Pernas" possua entrada mesmo que só nos blocos
    grupos.setdefault("Pernas", [])

    # parâmetros por objetivo
    objetivo = (objetivo or "hipertrofia").lower()
    if objetivo == "forca":
        reps_compound = (3, 6)
        reps_iso = (4, 8)
        sets_compound = (4, 6)
        sets_iso = (2, 4)
    elif objetivo == "emagrecimento":
        reps_compound = (8, 15)
        reps_iso = (12, 20)
        sets_compound = (3, 4)
        sets_iso = (2, 3)
    else:  # hipertrofia / padrão
        reps_compound = (6, 12)
        reps_iso = (8, 15)
        sets_compound = (3, 5)
        sets_iso = (2, 4)

    # multiplicadores por nível
    nivel = (nivel or "iniciante").lower()
    mult_por_nivel = {"iniciante": 0.8, "intermediario": 1.0, "avancado": 1.2}.get(nivel, 1.0)

    # ajustar por idade/IMC (reduzir intensidade se necessário)
    try:
        imc = peso / (altura ** 2) if altura and altura > 0 else None
    except:
        imc = None
    if imc and imc > 32:
        mult_por_nivel *= 0.9
    if idade and idade > 55:
        mult_por_nivel *= 0.9

    # ----------------------------
    # DIVISAO_MAP (inclui ppl_ul)
    # ----------------------------
    DIVISAO_MAP = {
        "livre": None,

        "abc": [
            ["Peito","Tríceps"],
            ["Costas","Bíceps"],
            ["Pernas","Ombro"]
        ],

        "abcd": [
            ["Peito"],
            ["Costas"],
            ["Pernas"],
            ["Ombro","Braços"]
        ],

        "abcde": [
            ["Peito"],
            ["Costas"],
            ["Pernas"],
            ["Ombro"],
            ["Braços"]
        ],

        "ppl": [
            ["Peito","Ombro","Tríceps"],
            ["Costas","Bíceps"],
            ["Pernas","Core"]
        ],

        # PPL + Upper/Lower (5 dias)
        "ppl_ul": [
            ["Peito","Ombro","Tríceps"],                     # Push
            ["Costas","Bíceps"],                             # Pull
            ["Pernas","Core"],                               # Legs (A)
            ["Peito","Costas","Ombro","Bíceps","Tríceps"],   # Upper
            ["Pernas","Core"]                                # Lower (B)
        ],

        "upperlower": [
            ["Peito","Costas","Ombro","Bíceps","Tríceps"],   # Upper
            ["Pernas","Core"]                                # Lower
        ]
    }

    def expand_groups(glist):
        out = []
        for g in glist:
            if g == "Braços":
                out += ["Bíceps", "Tríceps"]
            else:
                out.append(g)
        return out

    # dias de interesse (strings "Seg","Ter",...)
    dias_lista = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]
    mapa_dias = [dias_lista.index(d) for d in dias] if dias else [0,2,4]  # padrão Seg/Qua/Sex se não informado

    # volume alvo semanal por grupo (séries totais)
    volume_alvo = {
        "Peito": (8, 14),
        "Costas": (8, 14),
        "Pernas": (10, 18),  # já aumentado
        "Ombro": (6, 12),
        "Bíceps": (6, 10),
        "Tríceps": (6, 10),
        "Core": (4, 8)
    }

    # utilitários
    used = set()
    plan = []

    def rand_range(r):
        return random.randint(r[0], r[1])

    # mínimo de exercícios por treino de perna para aumentar variedade (opção A)
    MIN_EXS_PER_PERNA = 5

    def choose_exercises_for_group(group, needed_series, prefer_dif_max=5):
        """Retorna lista de exercícios para o grupo com contagem de séries por exercício."""
        pool = grupos.get(group, [])[:]
        if not pool:
            return []
        # priorizar compostos
        compounds = [e for e in pool if e["tipo"] == "composto" and e["nome"] not in used and e["dif"] <= prefer_dif_max]
        isolations = [e for e in pool if e["tipo"] == "isolamento" and e["nome"] not in used and e["dif"] <= prefer_dif_max]
        chosen = []
        remaining = needed_series
        # tentar alocar compostos primeiro
        for e in compounds:
            if remaining <= 0:
                break
            s = rand_range(sets_compound)
            s = max(1, int(math.ceil(s * mult_por_nivel)))
            chosen.append({"nome": e["nome"], "tipo": "composto", "series": s})
            remaining -= s
        # preencher com isolations
        for e in isolations:
            if remaining <= 0:
                break
            s = rand_range(sets_iso)
            s = max(1, int(math.ceil(s * mult_por_nivel)))
            chosen.append({"nome": e["nome"], "tipo": "isolamento", "series": s})
            remaining -= s
        # fallback se ainda faltar volume
        if remaining > 0:
            fallback = [e for e in pool if e["nome"] not in [c["nome"] for c in chosen]]
            i = 0
            while remaining > 0 and (i < len(fallback)):
                e = fallback[i]
                s = 1
                chosen.append({"nome": e["nome"], "tipo": e.get("tipo", "isolamento"), "series": s})
                remaining -= s
                i += 1
        return chosen

    # escolha específica para Pernas (usa PERNA_A / PERNA_B alternando)
    def choose_perna_for_block(needed_series, use_a=True):
        """Retorna lista de {nome,tipo,series} escolhidos do bloco A ou B garantindo variedade mínima."""
        block = PERNA_A if use_a else PERNA_B
        chosen = []
        remaining = needed_series

        # priorizar compostos do bloco (mas limitar séries por composto para aumentar nº de exercícios)
        comps = [e for e in block if e["tipo"] == "composto"]
        isos = [e for e in block if e["tipo"] == "isolamento"]

        # primeiro: compostos do bloco (com cap em séries por exercício composto)
        for e in comps:
            if remaining <= 0:
                break
            s = max(1, int(math.ceil(rand_range(sets_compound) * mult_por_nivel)))
            # cap para pernas: não deixe compostos terem muitas séries individuais,
            # assim abrimos espaço para mais exercícios (opção A)
            s = min(s, 3)
            chosen.append({"nome": e["nome"], "tipo": "composto", "series": s})
            remaining -= s

        # depois isolations do bloco
        for e in isos:
            if remaining <= 0:
                break
            s = max(1, int(math.ceil(rand_range(sets_iso) * mult_por_nivel)))
            chosen.append({"nome": e["nome"], "tipo": "isolamento", "series": s})
            remaining -= s

        # se ainda faltar volume, pegar do block (únicos não escolhidos) com 1 série
        i = 0
        while remaining > 0 and i < len(block):
            e = block[i]
            if e["nome"] not in [c["nome"] for c in chosen]:
                chosen.append({"nome": e["nome"], "tipo": e["tipo"], "series": 1})
                remaining -= 1
            i += 1

        # garantir variedade mínima de exercícios -> se escolhido < MIN_EXS_PER_PERNA, adicionar extras do catálogo
        if len(chosen) < MIN_EXS_PER_PERNA:
            extras_needed = MIN_EXS_PER_PERNA - len(chosen)
            # busca por exercícios de pernas no catálogo que ainda não foram usados nem escolhidos
            pool = [e for e in grupos.get("Pernas", []) if e["nome"] not in [c["nome"] for c in chosen] and e["nome"] not in used]
            # ordenar para preferir compostos
            pool = sorted(pool, key=lambda x: 0 if x["tipo"] == "composto" else 1)
            j = 0
            while extras_needed > 0 and j < len(pool):
                e = pool[j]
                s = 1  # acrescenta 1 série por exercício extra para variedade
                chosen.append({"nome": e["nome"], "tipo": e["tipo"], "series": s})
                extras_needed -= 1
                j += 1
            # se ainda falta, pegar repetidos do block (pode repetir se necessario)
            k = 0
            while extras_needed > 0 and k < len(block):
                e = block[k]
                if e["nome"] not in [c["nome"] for c in chosen]:
                    chosen.append({"nome": e["nome"], "tipo": e["tipo"], "series": 1})
                    extras_needed -= 1
                k += 1

        return chosen

    # função que formata objetivo de reps por tipo de exercício
    def reps_for(tipo):
        if tipo == "composto":
            r = rand_range(reps_compound)
        else:
            r = rand_range(reps_iso)
        # ajustar por nível: iniciantes usam o lado superior do range para aprender técnica
        if nivel == "iniciante":
            r = int(min(r * 1.1, (reps_compound[1] if tipo == "composto" else reps_iso[1])))
        # garantir ao menos 3 reps e no máximo 20
        return max(3, min(20, int(r)))

    # mapear dias para padrões (se DIVISAO_MAP definido)
    if DIVISAO_MAP.get(divisao):
        pattern = DIVISAO_MAP.get(divisao)
        pattern_len = len(pattern)
        day_patterns = []
        for i, dia in enumerate(mapa_dias):
            day_patterns.append(pattern[i % pattern_len])
    else:
        # fallback: 2 grupos por dia
        all_groups = [g for g in ["Peito","Costas","Pernas","Ombro","Bíceps","Tríceps","Core"] if g in grupos]
        day_patterns = []
        for i in range(len(mapa_dias)):
            g1 = all_groups[i % len(all_groups)]
            g2 = all_groups[(i+1) % len(all_groups)]
            day_patterns.append([g1, g2])

    # calcular aparições por grupo
    aparicoes = {}
    for pattern in day_patterns:
        for g in pattern:
            aparicoes[g] = aparicoes.get(g, 0) + 1

    # decidir séries por aparição
    series_por_aparicao = {}
    for g, freq in aparicoes.items():
        alvo = volume_alvo.get(g, (6, 10))
        alvo_media = int(round((alvo[0] + alvo[1]) / 2.0))
        per_day = max(2, int(round((alvo_media / max(1, freq)) * mult_por_nivel)))
        series_por_aparicao[g] = per_day

    # montar plano dia a dia
    perna_toggle = 0
    for dia_idx, grupos_para_dia in zip(mapa_dias, day_patterns):
        expanded = []
        for g in grupos_para_dia:
            if g == "Braços":
                expanded += ["Bíceps", "Tríceps"]
            else:
                expanded.append(g)

        for g in expanded:
            needed_series = series_por_aparicao.get(g, 3)

            # se for Pernas e divisão pede alternância, use bloco A/B
            if g == "Pernas" and divisao in ("ppl", "upperlower", "ppl_ul"):
                use_a = (perna_toggle % 2 == 0)
                perna_choices = choose_perna_for_block(needed_series, use_a=use_a)
                perna_toggle += 1
                ex_list = perna_choices
            else:
                ex_list = choose_exercises_for_group(g, needed_series)

            if not ex_list:
                continue

            # ordenar por tipo: compostos primeiro
            ex_list = sorted(ex_list, key=lambda x: 0 if x.get("tipo") == "composto" else 1)
            for ex in ex_list:
                # evitar repetir o mesmo exercício na mesma semana
                if ex["nome"] in used:
                    continue
                used.add(ex["nome"])
                tipo = ex.get("tipo", "isolamento")
                series = ex.get("series", 1)
                repeticoes = reps_for(tipo)

                # criar sugestão de progressão
                if objetivo == "forca":
                    progressao = f"Foco força: {series}x{repeticoes}. Aumentar carga gradualmente mantendo rep range."
                elif objetivo == "emagrecimento":
                    progressao = f"Foco condicionamento: {series}x{repeticoes}. Descansos curtos (~30-60s)."
                else:
                    upper = min(reps_compound[1], 15) if tipo == "composto" else min(reps_iso[1], 20)
                    progressao = f"Hipertrofia: {series}x{repeticoes}. Aumente 1 rep/semana até {upper}, depois aumente carga."

                plan.append({
                    "dia": dias_lista[dia_idx],  # STRING: "Seg", "Ter", ...
                    "grupo": g,
                    "exercicio": ex["nome"],
                    "series": int(series),
                    "repeticoes": int(repeticoes),
                    "tipo": tipo,
                    "progressao": progressao
                })

    # ordenar por dia (usando a ordem em dias_lista) e priorizar compostos
    def day_sort_key(x):
        try:
            return (dias_lista.index(x["dia"]), 0 if x.get("tipo") == "composto" else 1)
        except:
            return (0, 1)

    plan = sorted(plan, key=day_sort_key)

    return plan


# -------------------------
# Routes
# -------------------------
@app.route("/")
def index():
    get_flashed_messages()
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        if not nome or not email or not senha:
            flash("Preencha todos os campos.", "error")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Este email já está cadastrado!", "error")
            return redirect(url_for("register"))

        novo = User(nome=nome, email=email, senha=generate_password_hash(senha))
        db.session.add(novo)
        db.session.commit()
        flash("Conta criada com sucesso! Faça login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.senha, senha):
            login_user(user, remember=True)
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("dashboard"))
        flash("Email ou senha incorretos!", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("index"))


@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    if request.method == "POST":
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        if nome:
            current_user.nome = nome
        if email:
            other = User.query.filter(User.email == email, User.id != current_user.id).first()
            if other:
                flash("Email já está em uso por outra conta.", "error")
                return redirect(url_for('perfil'))
            current_user.email = email
        if senha and senha.strip() != "":
            current_user.senha = generate_password_hash(senha)
        if 'foto' in request.files:
            foto = request.files['foto']
            if foto and foto.filename != '' and allowed_file(foto.filename):
                filename = secure_filename(f"{current_user.id}_{random.randint(1000,9999)}_{foto.filename}")
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                foto.save(filepath)
                current_user.foto = filename
        db.session.commit()
        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for('perfil'))
    return render_template("perfil.html")


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/configuracoes")
@login_required
def configuracoes():
    return render_template("config.html")


@app.route("/dashboard")
@login_required
def dashboard():
    # dados para cards resumidos
    total = Treino.query.filter_by(user_id=current_user.id).count()
    stats = Treino.query.filter_by(user_id=current_user.id).order_by(Treino.dias_semana_id).limit(6).all()
    return render_template("dashboard.html", total=total, treinos=stats)


@app.route("/gerador")
@login_required
def gerador():
    # página exclusivamente do gerador (AJAX preview + salvar)
    return render_template("gerador.html")


@app.route("/gerar_plano", methods=["POST"])
@login_required
def gerar_plano():
    # os dados podem vir via form normal (submit) ou fetch (AJAX)
    nivel = request.form.get("nivel", "iniciante")
    objetivo = request.form.get("objetivo", "hipertrofia")
    divisao = request.form.get("divisao", "livre")
    dias = request.form.getlist("dias")
    try:
        peso = float(request.form.get("peso") or 0)
    except:
        peso = 0.0
    try:
        altura = float(request.form.get("altura") or 0)
    except:
        altura = 0.0
    try:
        idade = int(request.form.get("idade") or 0)
    except:
        idade = 0

    # gera plano (lista de dicts)
    plan = build_plan(nivel, objetivo, divisao, dias, peso, altura, idade)

    # se for preview (AJAX), retorna JSON sem salvar
    if request.args.get('preview') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"status":"ok", "plan": plan})

    # caso contrário, salva no DB substituindo treinos antigos
    try:
        Treino.query.filter_by(user_id=current_user.id).delete()
        # mapeador de dias (string -> índice)
        dias_lista = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]
        for item in plan:
            dia_val = item.get('dia')
            # converte dia string ("Seg") para índice integer (0..6)
            dia_idx = None
            if isinstance(dia_val, str):
                try:
                    dia_idx = dias_lista.index(dia_val)
                except ValueError:
                    # tenta extrair número se for "0", "1", etc.
                    try:
                        dia_idx = int(dia_val) % 7
                    except:
                        dia_idx = 0
            else:
                try:
                    dia_idx = int(dia_val) % 7
                except:
                    dia_idx = 0

            novo = Treino(
                user_id=current_user.id,
                dias_semana_id=int(dia_idx),
                grupo_muscular=item.get('grupo'),
                exercicio=item.get('exercicio'),
                series=int(item.get('series', 0)),
                repeticoes=int(item.get('repeticoes', 0))
            )
            db.session.add(novo)
        db.session.commit()
        flash(f"Plano gerado com sucesso! {len(plan)} exercícios adicionados.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Erro ao salvar plano.", "error")
    return redirect(url_for("dashboard"))


@app.route("/trocar_tema", methods=["POST"])
@login_required
def trocar_tema():
    user = current_user
    novo = "light" if user.theme == "dark" else "dark"
    user.theme = novo
    db.session.commit()
    return {"status": "ok", "theme": novo}


# API endpoints
@app.route("/api/treinos_stats")
@login_required
def api_treinos_stats():
    counts = [0] * 7
    treinos = Treino.query.filter_by(user_id=current_user.id).all()
    for t in treinos:
        try:
            idx = int(t.dias_semana_id) % 7
            counts[idx] += 1
        except:
            pass
    labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    return jsonify({"labels": labels, "data": counts, "total": sum(counts)})


@app.route("/api/treinos")
@login_required
def api_treinos():
    treinos = Treino.query.filter_by(user_id=current_user.id).order_by(Treino.dias_semana_id).all()
    out = []
    for t in treinos:
        out.append({
            "id": t.id,
            "dia": t.dias_semana_id,
            "grupo": t.grupo_muscular,
            "exercicio": t.exercicio,
            "series": t.series,
            "repeticoes": t.repeticoes
        })
    return jsonify(out)


# Init DB
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)