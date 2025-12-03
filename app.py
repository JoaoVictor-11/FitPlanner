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
    Gera uma lista de dicionários representando exercícios.
    Não salva no DB — só retorna os itens.
    Cada item: {'dia': dia_idx, 'grupo': ..., 'exercicio': ..., 'series': n, 'repeticoes': n}
    """
    # lista de exercícios (sintética)
    EXS = [
        ("Supino reto", "Peito", ["Ombro","Tríceps"], "barra/halteres", 3),
        ("Supino inclinado", "Peito", ["Ombro","Tríceps"], "barra/halteres", 3),
        ("Crucifixo", "Peito", [], "halteres", 2),
        ("Flexão de braço", "Peito", ["Tríceps"], "peso_corpo", 1),

        ("Puxada alta", "Costas", ["Bíceps"], "máquina", 2),
        ("Remada curvada", "Costas", ["Bíceps"], "barra/halteres", 3),
        ("Remada baixa", "Costas", ["Bíceps"], "máquina", 2),
        ("Barra fixa", "Costas", ["Bíceps"], "peso_corpo", 3),

        ("Agachamento livre", "Pernas", ["Glúteo"], "barra", 3),
        ("Leg press", "Pernas", ["Glúteo"], "máquina", 2),
        ("Cadeira extensora", "Pernas", [], "máquina", 1),
        ("Cadeira flexora", "Pernas", [], "máquina", 1),
        ("Panturilha em pé", "Pernas", [], "máquina", 1),

        ("Desenvolvimento", "Ombro", ["Tríceps"], "barra/halteres", 3),
        ("Elevação lateral", "Ombro", [], "halteres", 1),
        ("Elevação frontal", "Ombro", [], "halteres", 1),

        ("Rosca direta", "Bíceps", [], "barra", 2),
        ("Rosca alternada", "Bíceps", [], "halteres", 1),

        ("Tríceps corda", "Tríceps", [], "polia", 1),
        ("Paralelas", "Tríceps", [], "peso_corpo", 3),

        ("Prancha", "Core", [], "peso_corpo", 1),
        ("Elevação de pernas", "Core", [], "peso_corpo", 1),
    ]

    grupos = {}
    for nome, prim, secs, equip, dif in EXS:
        grupos.setdefault(prim, []).append({"nome": nome, "dif": dif})

    if objetivo == "emagrecimento":
        series_base = 3
        reps_base = 15
    elif objetivo == "forca":
        series_base = 5
        reps_base = 5
    else:
        series_base = 4
        reps_base = 10

    mult_nivel = {"iniciante": 0.7, "intermediario": 1.0, "avancado": 1.25}.get(nivel, 1.0)

    if altura > 0:
        try:
            imc = peso / (altura ** 2)
        except:
            imc = None
    else:
        imc = None

    if imc and imc > 30:
        for g in list(grupos.keys()):
            grupos[g] = [e for e in grupos[g] if e["dif"] <= 2]
    if idade and idade > 50:
        mult_nivel *= 0.9
        reps_base += 2

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

    dias_lista = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]
    mapa_dias = [dias_lista.index(d) for d in dias] if dias else []

    grupos_disponiveis = [g for g in ["Peito","Costas","Pernas","Ombro","Bíceps","Tríceps","Core"] if g in grupos]
    used_exercises = set()
    plan = []

    # quantidade de exercícios por dia base
    num_dias = len(mapa_dias) or 1
    if num_dias <= 2:
        ex_por_dia_base = 6
    elif num_dias == 3:
        ex_por_dia_base = 5
    elif num_dias == 4:
        ex_por_dia_base = 4
    else:
        ex_por_dia_base = 3

    def selecionar_exercicios(lista, n, prefer_dif_max=3):
        candidatos = [e for e in lista if e["nome"] not in used_exercises and e["dif"] <= prefer_dif_max]
        if len(candidatos) < n:
            candidatos = [e for e in lista if e["nome"] not in used_exercises]
        if len(candidatos) < n:
            candidatos = lista[:]
        selecionados = random.sample(candidatos, k=min(n, len(candidatos)))
        return selecionados

    def processar_dia(dia_id, grupos_para_dia):
        nonlocal plan
        grupos_para_dia = expand_groups(grupos_para_dia)
        per_group = max(1, ex_por_dia_base // max(1, len(grupos_para_dia)))
        extras = ex_por_dia_base - per_group * len(grupos_para_dia)
        for gi, g in enumerate(grupos_para_dia):
            cnt = per_group + (1 if gi < extras else 0)
            lista = grupos.get(g, [])
            if not lista:
                continue
            selecionados = selecionar_exercicios(lista, cnt, prefer_dif_max=3 if nivel=="avancado" else (2 if nivel=="intermediario" else 1))
            for ex in selecionados:
                series = max(1, int(series_base * mult_nivel))
                reps = max(4, int(reps_base * mult_nivel))
                plan.append({
                    "dia": dia_id,
                    "grupo": g,
                    "exercicio": ex["nome"],
                    "series": series,
                    "repeticoes": reps
                })
                used_exercises.add(ex["nome"])

    if divisao == "livre" or DIVISAO_MAP.get(divisao) is None:
        for i, dia in enumerate(mapa_dias if mapa_dias else [0]):
            grupo = grupos_disponiveis[i % len(grupos_disponiveis)]
            processar_dia(dia, [grupo])
    else:
        pattern = DIVISAO_MAP.get(divisao, DIVISAO_MAP["livre"])
        for idx_d, dia in enumerate(mapa_dias):
            padrao_dia = pattern[idx_d % len(pattern)]
            processar_dia(dia, padrao_dia)

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