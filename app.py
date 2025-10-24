from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FITPLANNER_SECRET', 'troque_esta_chave_para_producao')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fitplanner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(150), nullable=False)

    def set_password(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_password(self, senha):
        return check_password_hash(self.senha_hash, senha)

class Treino(db.Model):
    __tablename__ = 'treinos'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    dias_semana_id = db.Column(db.Integer, nullable=False)
    grupo_muscular = db.Column(db.String(100), nullable=False)
    exercicio = db.Column(db.String(200), nullable=False)
    series = db.Column(db.Integer, nullable=False)
    repeticoes = db.Column(db.Integer, nullable=False)
    usuario = db.relationship('User', backref=db.backref('treinos', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def gerar_recomendacao(perfil):
    planos = []
    nivel = perfil.get('nivel', 'iniciante')
    objetivo = perfil.get('objetivo', 'manter')
    dias = int(perfil.get('dias_por_semana', 3))
    base_exercicios = {
        'peito': ['Supino reto', 'Supino inclinado', 'Flexão de braço'],
        'costas': ['Puxada frente', 'Remada curvada', 'Levantamento terra (leve)'],
        'perna': ['Agachamento', 'Leg press', 'Avanço'],
        'ombro': ['Desenvolvimento', 'Elevação lateral'],
        'braco': ['Rosca direta', 'Tríceps pulley']
    }
    grupos = list(base_exercicios.keys())
    for d in range(dias):
        grupo = grupos[d % len(grupos)]
        for ex in base_exercicios[grupo][:2]:
            series = 3 if nivel == 'intermediario' else (2 if nivel == 'iniciante' else 4)
            repeticoes = 12 if objetivo == 'hipertrofia' else (15 if objetivo == 'resistencia' else 10)
            planos.append({
                'dias_semana_id': d, 'grupo_muscular': grupo, 'exercicio': ex,
                'series': series, 'repeticoes': repeticoes
            })
    return planos

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        if User.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'warning')
            return redirect(url_for('register'))
        user = User(nome=nome, email=email)
        user.set_password(senha)
        db.session.add(user)
        db.session.commit()
        flash('Conta criada com sucesso. Faça login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(senha):
            flash('Credenciais inválidas.', 'danger')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Desconectado com sucesso.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET','POST'])
@login_required
def dashboard():
    if request.method == 'POST' and request.form.get('action') == 'salvar_treino':
        treino = Treino(
            user_id=current_user.id,
            dias_semana_id=int(request.form['dias_semana_id']),
            grupo_muscular=request.form['grupo_muscular'],
            exercicio=request.form['exercicio'],
            series=int(request.form['series']),
            repeticoes=int(request.form['repeticoes'])
        )
        db.session.add(treino)
        db.session.commit()
        flash('Treino salvo!', 'success')
        return redirect(url_for('dashboard'))
    treinos = Treino.query.filter_by(user_id=current_user.id).order_by(Treino.dias_semana_id).all()
    return render_template('dashboard.html', treinos=treinos)

@app.route('/gerar_plano', methods=['POST'])
@login_required
def gerar_plano():
    perfil = {
        'nivel': request.form.get('nivel', 'iniciante'),
        'objetivo': request.form.get('objetivo', 'manter'),
        'dias_por_semana': request.form.get('dias_por_semana', 3)
    }
    sugestoes = gerar_recomendacao(perfil)
    for s in sugestoes:
        treino = Treino(user_id=current_user.id, **s)
        db.session.add(treino)
    db.session.commit()
    flash(f'{len(sugestoes)} exercícios gerados e salvos no seu perfil.', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
