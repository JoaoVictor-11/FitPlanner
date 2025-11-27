from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'segredo_super_secreto'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fitplanner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login = LoginManager(app)
login.login_view = "login"

# ============================
# MODELOS DO BANCO
# ============================

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    senha = db.Column(db.String(120))

class Treino(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    dias_semana_id = db.Column(db.Integer)
    grupo_muscular = db.Column(db.String(120))
    exercicio = db.Column(db.String(120))
    series = db.Column(db.Integer)
    repeticoes = db.Column(db.Integer)

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============================
# ROTAS
# ============================

@app.route("/")
def index():
    return render_template("index.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        user = User.query.filter_by(email=email).first()

        if user and user.senha == senha:
            login_user(user)
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Email ou senha incorretos!", "error")

    return render_template("login.html")

# ---------- LOGOUT ----------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("index"))

# ---------- REGISTRO ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]

        user = User.query.filter_by(email=email).first()
        if user:
            flash("Este email já está cadastrado!", "error")
            return redirect(url_for("register"))

        novo = User(nome=nome, email=email, senha=senha)
        db.session.add(novo)
        db.session.commit()

        flash("Conta criada com sucesso!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# ---------- DASHBOARD ----------
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():

    # Salvando treino manualmente
    if request.method == "POST":
        if request.form.get("action") == "salvar_treino":

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
            return redirect(url_for("dashboard"))

    treinos = Treino.query.filter_by(user_id=current_user.id).all()

    return render_template("dashboard.html", treinos=treinos)

# ---------- GERADOR DE TREINO AUTOMÁTICO ----------
@app.route("/gerar_plano", methods=["POST"])
@login_required
def gerar_plano():

    nivel = request.form["nivel"]
    objetivo = request.form["objetivo"]
    dias = request.form.getlist("dias")
    peso = request.form["peso"]
    altura = request.form["altura"]
    idade = request.form["idade"]

    if not dias:
        flash("Selecione pelo menos um dia!", "error")
        return redirect(url_for("dashboard"))

    # Dados simples de exemplo — depois posso melhorar com tabelas e IA
    plano_base = {
        "Peito": ["Supino reto", "Supino inclinado", "Crucifixo"],
        "Costas": ["Puxada alta", "Remada baixa", "Barra fixa"],
        "Pernas": ["Agachamento", "Leg press", "Cadeira extensora"],
        "Ombro": ["Desenvolvimento", "Elevação lateral"],
        "Bíceps": ["Rosca direta", "Rosca alternada"],
        "Tríceps": ["Tríceps corda", "Paralelas"]
    }

    # Limpando plano anterior
    Treino.query.filter_by(user_id=current_user.id).delete()

    # Distribuição
    dias_lista = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    mapa = [dias_lista.index(d) for d in dias]

    grupos = list(plano_base.keys())
    idx = 0

    for dia in mapa:
        grupo = grupos[idx % len(grupos)]
        exercicios = plano_base[grupo]

        for ex in exercicios:
            novo = Treino(
                user_id=current_user.id,
                dias_semana_id=dia,
                grupo_muscular=grupo,
                exercicio=ex,
                series=3,
                repeticoes=12
            )
            db.session.add(novo)

        idx += 1

    db.session.commit()

    flash("Plano gerado com sucesso!", "success")
    return redirect(url_for("dashboard"))

# ============================
# INICIALIZAR BANCO
# ============================
if not os.path.exists("instance"):
    os.makedirs("instance")

with app.app_context():
    db.create_all()

# ============================
# EXECUTAR APP
# ============================
if __name__ == "__main__":
    app.run(debug=True)