from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os, random

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
    - Prioriza exercícios compostos,
    - Distribui volume por grupo conforme divisão (ABC),
    - Define séries/reps por objetivo e nível,
    - Adiciona campo 'tipo' (composto/isolamento) e 'progressao' (texto).
    Saída: lista de itens {'dia': int, 'grupo': str, 'exercicio': str, 'series': int, 'repeticoes': int, 'tipo': str, 'progressao': str}
    """
    import math

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

        # Pernas
        ("Agachamento livre", "Pernas", "composto", "barra", 5),
        ("Leg press", "Pernas", "composto", "máquina", 4),
        ("Stiff", "Pernas", "composto", "barra", 4),
        ("Avanço / Afundo", "Pernas", "composto", "halteres", 3),
        ("Cadeira extensora", "Pernas", "isolamento", "máquina", 2),
        ("Cadeira flexora", "Pernas", "isolamento", "máquina", 2),
        ("Panturrilha em pé", "Pernas", "isolamento", "máquina", 2),

        # Ombro
        ("Desenvolvimento militar", "Ombro", "composto", "barra/halteres", 4),
        ("Elevação lateral", "Ombro", "isolamento", "halteres", 2),
        ("Elevação frontal", "Ombro", "isolamento", "halteres", 2),
        ("Remada alta", "Ombro", "composto", "barra", 3),

        # Braços
        ("Rosca direta", "Bíceps", "isolamento", "barra", 3),
        ("Rosca alternada", "Bíceps", "isolamento", "halteres", 2),
        ("Rosca martelo", "Bíceps", "isolamento", "halteres", 2),
        ("Tríceps corda", "Tríceps", "isolamento", "polia", 2),
        ("Paralelas", "Tríceps", "composto", "peso_corpo", 3),
        ("Tríceps testa", "Tríceps", "isolamento", "barra/halteres", 3),

        # Core / condicionamento
        ("Prancha", "Core", "isolamento", "peso_corpo", 1),
        ("Elevação de pernas", "Core", "isolamento", "peso_corpo", 1),
        ("Farmer's walk (caminhada)", "Core", "composto", "halteres", 2),
    ]

    # montar dicionário por grupo
    grupos = {}
    for nome, prim, tipo, equip, dif in EXS:
        grupos.setdefault(prim, []).append({"nome": nome, "tipo": tipo, "dif": dif})

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

    # divisão ABC (forçar padrão ABC se pedido)
    if divisao == "abc":
        DIVISAO_MAP = [
            ["Peito", "Tríceps"],      # A
            ["Costas", "Bíceps"],      # B
            ["Pernas", "Ombro"]        # C
        ]
    else:
        DIVISAO_MAP = None

    # dias de interesse (índices 0..6)
    dias_lista = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]
    mapa_dias = [dias_lista.index(d) for d in dias] if dias else [0,2,4]  # padrão Seg/Qua/Sex se não informado

    # volume alvo semanal por grupo (séries totais)
    volume_alvo = {
        "Peito": (8, 14),
        "Costas": (8, 14),
        "Pernas": (10, 16),
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

    def choose_exercises_for_group(group, needed_series, prefer_compound_first=True):
        """Retorna lista de exercícios para o grupo com contagem de séries por exercício."""
        pool = grupos.get(group, [])[:]
        if not pool:
            return []
        # priorizar compostos
        compounds = [e for e in pool if e["tipo"] == "composto" and e["nome"] not in used]
        isolations = [e for e in pool if e["tipo"] == "isolamento" and e["nome"] not in used]
        chosen = []
        remaining = needed_series
        # tentar alocar compostos primeiro (cada composto pega 3-5 séries dependendo do objetivo)
        for e in compounds:
            if remaining <= 0:
                break
            # decide séries para esse exercício
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
        # se ainda resta volume, pegar exercícios mesmo repetidos (ou já usados), mas respeitar variedade
        if remaining > 0:
            fallback = [e for e in pool if e["nome"] not in [c["nome"] for c in chosen]]
            i = 0
            while remaining > 0 and (i < len(fallback)):
                e = fallback[i]
                s = 1
                chosen.append({"nome": e["nome"], "tipo": e["tipo"], "series": s})
                remaining -= s
                i += 1
        return chosen

    # função que formata objetivo de reps por tipo de exercício
    def reps_for(tipo):
        if tipo == "composto":
            r = rand_range(reps_compound)
        else:
            r = rand_range(reps_iso)
        # ajustar por nível: iniciantes usam o lado superior do range para aprender técnica
        if nivel == "iniciante":
            r = int(min(r * 1.1, reps_compound[1] if tipo=="composto" else reps_iso[1]))
        # garantir ao menos 3 reps e no máximo 20
        return max(3, min(20, int(r)))

    # mapear dias para padrões (se DIVISAO_MAP definido, replicar o padrão ABC na sequência dos dias escolhidos)
    if DIVISAO_MAP:
        pattern = DIVISAO_MAP
        pattern_len = len(pattern)
        # se houver mais dias que pattern_len, ciclo pelo padrão
        day_patterns = []
        for i, dia in enumerate(mapa_dias):
            day_patterns.append(pattern[i % pattern_len])
    else:
        # fallback: para cada dia pega 2 grupos balanceados
        all_groups = [g for g in ["Peito","Costas","Pernas","Ombro","Bíceps","Tríceps","Core"] if g in grupos]
        day_patterns = []
        for i in range(len(mapa_dias)):
            g1 = all_groups[i % len(all_groups)]
            g2 = all_groups[(i+1) % len(all_groups)]
            day_patterns.append([g1, g2])

    # calcular aparições por grupo na semana
    aparicoes = {}
    for pattern in day_patterns:
        for g in pattern:
            aparicoes[g] = aparicoes.get(g, 0) + 1

    # decidir séries por aparição (distribuir o volume alvo pela aparição)
    series_por_aparicao = {}
    for g, freq in aparicoes.items():
        alvo = volume_alvo.get(g, (6, 10))
        alvo_media = int(round((alvo[0] + alvo[1]) / 2.0))
        per_day = max(2, int(round((alvo_media / max(1, freq)) * mult_por_nivel)))
        series_por_aparicao[g] = per_day

    # montar plano dia a dia
    for dia_idx, grupos_para_dia in zip(mapa_dias, day_patterns):
        # expandir "Braços" caso exista (compatibilidade)
        expanded = []
        for g in grupos_para_dia:
            if g == "Braços":
                expanded += ["Bíceps", "Tríceps"]
            else:
                expanded.append(g)
        # para cada grupo escolher exercícios
        for g in expanded:
            needed_series = series_por_aparicao.get(g, 3)
            ex_list = choose_exercises_for_group(g, needed_series)
            if not ex_list:
                continue
            # ordenar por tipo: compostos primeiro
            ex_list = sorted(ex_list, key=lambda x: 0 if x["tipo"]=="composto" else 1)
            for ex in ex_list:
                # evitar repetir o mesmo exercício na mesma semana
                if ex["nome"] in used:
                    continue
                used.add(ex["nome"])
                tipo = ex["tipo"]
                series = ex["series"]
                repeticoes = reps_for(tipo)
                # criar sugestão de progressão
                if objetivo == "forca":
                    progressao = f"Foco força: {series}x{repeticoes}. Tente aumentar 1 carga a cada 1-2 semanas mantendo reps no range {repeticoes}."
                elif objetivo == "emagrecimento":
                    progressao = f"Foco condicionamento: {series}x{repeticoes}. Minimize descansos (~30-60s). Aumente reps ou adicione circuito."
                else:
                    upper = min(reps_compound[1], 15) if tipo=="composto" else min(reps_iso[1], 20)
                    progressao = f"Hipertrofia: {series}x{repeticoes}. Aumente 1 rep por semana até {upper}, depois aumente carga e volte ao lower range."

                plan.append({
                    "dia": int(dia_idx),
                    "grupo": g,
                    "exercicio": ex["nome"],
                    "series": int(series),
                    "repeticoes": int(repeticoes),
                    "tipo": tipo,
                    "progressao": progressao
                })

    # ordenar por dia e priorizar compostos
    plan = sorted(plan, key=lambda x: (x["dia"], 0 if x.get("tipo")=="composto" else 1))

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
        for item in plan:
            novo = Treino(
                user_id=current_user.id,
                dias_semana_id=int(item['dia']),
                grupo_muscular=item['grupo'],
                exercicio=item['exercicio'],
                series=int(item['series']),
                repeticoes=int(item['repeticoes'])
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