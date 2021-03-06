# -*- coding: utf-8 -*-
from flask import render_template, send_file
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, Response, redirect, request, abort, url_for, flash
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from flask_socketio import SocketIO, send, emit
import boto3
import uuid
import os


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
db = SQLAlchemy(app)
socketio = SocketIO(app)


app.config.update(
    DEBUG=True,
    SECRET_KEY='secret_xxx'
)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, id):
        self.id = id
        self.name = id
        self.password = id


@app.route("/login", methods=["GET", "POST"])
def login():
	if request.method == 'POST':
		username = request.form['username']
		password = request.form['password']
		if Usuario.query.filter_by(username=username, password=password).first() != None:
			id = username
			user = User(id)
			login_user(user)
			return redirect(request.args.get("next") or url_for("index"))
		else:
			return abort(401)
	else:
		return Response(render_template('login.html'))


@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash('usuario deslogado')
    return redirect(url_for('index'))


@app.errorhandler(401)
def page_not_found(e):
    flash('usuario ou senha incorretos')
    return Response(render_template('login.html'))


@login_manager.user_loader
def load_user(userid):
    return User(userid)


@app.route('/')
def index():
    if hasattr(current_user, 'name'):
        return render_template('index.html', usuario=current_user.name)
    else:
        return render_template('index.html', usuario=None)


@app.route('/admin')
@login_required
def admin():
    imagens = [x.imagelink for x in FileContent.query.filter_by(name=current_user.name).all()]
    return render_template('admin.html', usuario=current_user.name, imagens=imagens)


@app.route('/set_cookie', methods=["POST"])
def cookie_insertion():
    name = request.form['name']
    value = request.form['value']

    redirect_to_index = redirect('admin')
    response = app.make_response(redirect_to_index )
    response.set_cookie(name, value=value)
    return response


@app.route('/cadastrar', methods=["POST","GET"])
def cadastrar():
    if request.method == "POST":
        try:
            username = request.form['username']
            password = request.form['password']

            if len(list(Usuario.query.filter_by(username=username))) == 0:
                new_user = Usuario(username, password)

                db.session.add(new_user)
                db.session.commit()
                flash('Usuário registrado no banco de dados!')
                return redirect(url_for('index'))
            else:
                flash('Já existe um usuário com esse nome registrado :(')
                return redirect(url_for('cadastrar'))
        except Exception as e:
            flash('ocorreu o seguinte erro: ', e)
    else:
        return render_template('cadastrar.html')


@app.route('/upload', methods=["POST"])
@login_required
def upload():
    try:
        image = request.files['image']

        imagelink = saveImage(image)

        newfile = FileContent(current_user.name, imagelink)
        db.session.add(newfile)
        db.session.commit()

        flash('Imagem salva com sucesso!')
    except Exception as e:
        flash('ocorreu o seguinte erro: ', e)
    return redirect(url_for('admin'))


@app.route('/chat')
@login_required
def chat():
    flash('Bem-vido ao chat!')
    return render_template('chat.html', usuario=current_user.name)


@socketio.on('message', namespace='/chat')
def handleMessage(msg):
    emit('message', {'user': current_user.name, 'msg': msg}, broadcast=True)


def saveImage(file):
    extension = os.path.splitext(file.filename)[1]
    if extension == '':
        return None

    filename = "YANO" + str(uuid.uuid4()) + extension
    s3 = boto3.resource('s3')
    S3_BUCKET = os.environ.get('S3_BUCKET')
    s3.Bucket(S3_BUCKET).put_object(Key=filename, Body=file, CacheControl='max-age:2592000')
    path = 'https://%s.s3.amazonaws.com/%s' % (S3_BUCKET, filename)

    return path


class FileContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(), nullable=False)
    imagelink = db.Column(db.Unicode(), nullable=False)

    def __init__(self, name, imagelink):
        self.name = name
        self.imagelink = imagelink


class Usuario(db.Model):
    __tablename__ = 'usuario'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(2000), unique=True, nullable=False)

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def __repr__(self):
        return '<username %r, password %r>' % (self.username, self.password)


if __name__ == '__main__':
    socketio.run(app)
