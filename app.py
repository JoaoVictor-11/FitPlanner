from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import get_flashed_messages
import os
import random

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
    foto = db.Column(db.String(200), default=None)        # nome do arquivo salvo
    theme = db.Column(db.String(20), default="light")     # 'light' ou 'dark'

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


# -------------------------
# Routes
# -------------------------

@app.route("/")
def index():
    get_flashed_messages()  # limpa mensagens antigas
    return render_template("index.html")


# ----- Register -----
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

        novo = User(
            nome=nome,
            email=email,
            senha=generate_password_hash(senha)
        )
        db.session.add(novo)
        db.session.commit()

        flash("Conta criada com sucesso! Faça login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# ----- Login -----
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


# ----- Logout -----
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("index"))


# ----- Perfil (editar) -----
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
            # checar se email já é usado por outro
            other = User.query.filter(User.email == email, User.id != current_user.id).first()
            if other:
                flash("Email já está em uso por outra conta.", "error")
                return redirect(url_for('perfil'))
            current_user.email = email

        if senha and senha.strip() != "":
            current_user.senha = generate_password_hash(senha)

        # upload foto
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


# ----- Serve uploads (opcional, static already serves it but this is explicit) -----
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ----- Dashboard -----
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    # salvar treino manual
    if request.method == "POST":
        if request.form.get("action") == "salvar_treino":
            try:
                t = Treino(
                    user_id=current_user.id,
                    dias_semana_id=int(request.form["dias_semana_id"]),
                    grupo_muscular=request.form["grupo_muscular"],
                    exercicio=request.form["exercicio"],
                    series=int(request.form["series"]),
                    repeticoes=int(request.form["repeticoes"])
                )
                db.session.add(t)
                db.session.commit()
                flash("Treino salvo!", "success")
            except Exception as e:
                db.session.rollback()
                flash("Erro ao salvar treino.", "error")
            return redirect(url_for("dashboard"))

    treinos = Treino.query.filter_by(user_id=current_user.id).order_by(Treino.dias_semana_id).all()
    return render_template("dashboard.html", treinos=treinos)


# ----- Configurações (mostra tema atual salvo no usuário) -----
@app.route("/configuracoes")
@login_required
def configuracoes():
    return render_template("config.html")


# ----- Trocar tema (atualiza preferência do usuário) -----
@app.route("/trocar_tema", methods=["POST"])
@login_required
def trocar_tema():
    novo = "dark" if current_user.theme != "dark" else "light"
    current_user.theme = novo
    db.session.commit()
    return {"status": "ok", "theme": novo}


# ----- Gerador de planos (seu código original, colado e adaptado) -----
@app.route("/gerar_plano", methods=["POST"])
@login_required
def gerar_plano():
    # (mantive seu gerador original, com pequenas proteções)
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

    if not dias:
        flash("Selecione pelo menos um dia!", "error")
        return redirect(url_for("dashboard"))

    imc = None
    if altura > 0:
        try:
            imc = peso / (altura ** 2)
        except:
            imc = None

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
        grupos.setdefault(prim, []).append({
            "nome": nome,
            "sec": secs,
            "equip": equip,
            "dif": dif
        })

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
    mapa_dias = [dias_lista.index(d) for d in dias]

    grupos_disponiveis = [g for g in ["Peito","Costas","Pernas","Ombro","Bíceps","Tríceps","Core"] if g in grupos]
    used_exercises = set()

    Treino.query.filter_by(user_id=current_user.id).delete()
    total_inseridos = 0

    def selecionar_exercicios(lista, n, prefer_dif_max=3):
        candidatos = [e for e in lista if e["nome"] not in used_exercises and e["dif"] <= prefer_dif_max]
        if len(candidatos) < n:
            candidatos = [e for e in lista if e["nome"] not in used_exercises]
        if len(candidatos) < n:
            candidatos = lista[:]
        selecionados = random.sample(candidatos, k=min(n, len(candidatos)))
        return selecionados

    num_dias = len(mapa_dias)
    if num_dias <= 2:
        ex_por_dia_base = 6
    elif num_dias == 3:
        ex_por_dia_base = 5
    elif num_dias == 4:
        ex_por_dia_base = 4
    else:
        ex_por_dia_base = 3

    def processar_dia(dia_id, grupos_para_dia):
        nonlocal total_inseridos
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
                novo = Treino(
                    user_id=current_user.id,
                    dias_semana_id=dia_id,
                    grupo_muscular=g,
                    exercicio=ex["nome"],
                    series=series,
                    repeticoes=reps
                )
                db.session.add(novo)
                used_exercises.add(ex["nome"])
                total_inseridos += 1

    if divisao == "livre" or DIVISAO_MAP.get(divisao) is None:
        for i, dia in enumerate(mapa_dias):
            grupo = grupos_disponiveis[i % len(grupos_disponiveis)]
            processar_dia(dia, [grupo])
    else:
        pattern = DIVISAO_MAP.get(divisao, DIVISAO_MAP["livre"])
        for idx_d, dia in enumerate(mapa_dias):
            padrao_dia = pattern[idx_d % len(pattern)]
            processar_dia(dia, padrao_dia)

    db.session.commit()
    flash(f"Plano inteligente ({divisao.upper()}) gerado com sucesso! {total_inseridos} exercícios adicionados.", "success")
    return redirect(url_for("dashboard"))


# -------------------------
# Init DB
# -------------------------
with app.app_context():
    db.create_all()
    # Se você está alterando o modelo (adicionou 'foto' ou 'theme') e já tem um fitplanner.db antigo,
    # remova o arquivo 'fitplanner.db' antes de rodar para recriar com as novas colunas:
    # os.remove('fitplanner.db')  # <-- só use se souber o que está fazendo


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)