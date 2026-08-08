import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_secreta_aniversario_familia")

ADMIN_USER = "thais"
ADMIN_PASS = "1234"

# Verifica se há URL de banco PostgreSQL fornecida pelo Render
DB_URL = os.environ.get("DATABASE_URL")
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)


def get_db_connection():
    if DB_URL:
        # Conexão PostgreSQL (Servidor / Render)
        conn = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.DictCursor)
        return conn
    else:
        # Conexão SQLite (Desenvolvimento Local)
        conn = sqlite3.connect("aniversario.db")
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    if DB_URL:
        # Schemas para PostgreSQL
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS convidados (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) NOT NULL,
                referencia VARCHAR(255) DEFAULT '',
                status VARCHAR(50) DEFAULT 'Pendente'
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS itens (
                id SERIAL PRIMARY KEY,
                categoria VARCHAR(100) NOT NULL,
                subcategoria VARCHAR(100) NOT NULL,
                nome_item VARCHAR(255) NOT NULL,
                responsavel VARCHAR(255) DEFAULT NULL
            );
        ''')

        cursor.execute("SELECT COUNT(*) FROM itens;")
        count = cursor.fetchone()[0]

        if count == 0:
            itens_iniciais = [
                ('comida_bebida', 'Bebidas Não Alcoólicas', 'Refrigerante Guaraná 2L'),
                ('comida_bebida', 'Bebidas Não Alcoólicas', 'Refrigerante Coca-Cola 2L'),
                ('comida_bebida', 'Bebidas Alcoólicas', 'Fardo De Cerveja (Lata)'),
                ('comida_bebida', 'Salgados & Petiscos', 'Cento De Coxinha/Rissoles'),
                ('comida_bebida', 'Doces & Sobremesas', 'Cento De Brigadeiro'),
                ('insumo', 'Descartáveis', 'Pacote De Copos Descartáveis (50Un)'),
                ('insumo', 'Descartáveis', 'Pacote De Guardanapos'),
                ('insumo', 'Estrutura & Logística', 'Saco De Gelo 10Kg')
            ]
            for it in itens_iniciais:
                cursor.execute(
                    "INSERT INTO itens (categoria, subcategoria, nome_item) VALUES (%s, %s, %s)",
                    it
                )
    else:
        # Schemas para SQLite
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS convidados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                referencia TEXT DEFAULT '',
                status TEXT DEFAULT 'Pendente'
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT NOT NULL,
                subcategoria TEXT NOT NULL,
                nome_item TEXT NOT NULL,
                responsavel TEXT DEFAULT NULL
            )
        ''')

        cursor.execute("SELECT COUNT(*) FROM itens")
        if cursor.fetchone()[0] == 0:
            itens_iniciais = [
                ('comida_bebida', 'Bebidas Não Alcoólicas', 'Refrigerante Guaraná 2L'),
                ('comida_bebida', 'Bebidas Não Alcoólicas', 'Refrigerante Coca-Cola 2L'),
                ('comida_bebida', 'Bebidas Alcoólicas', 'Fardo De Cerveja (Lata)'),
                ('comida_bebida', 'Salgados & Petiscos', 'Cento De Coxinha/Rissoles'),
                ('comida_bebida', 'Doces & Sobremesas', 'Cento De Brigadeiro'),
                ('insumo', 'Descartáveis', 'Pacote De Copos Descartáveis (50Un)'),
                ('insumo', 'Descartáveis', 'Pacote De Guardanapos'),
                ('insumo', 'Estrutura & Logística', 'Saco De Gelo 10Kg')
            ]
            cursor.executemany(
                "INSERT INTO itens (categoria, subcategoria, nome_item) VALUES (?, ?, ?)",
                itens_iniciais
            )

    conn.commit()
    cursor.close()
    conn.close()


def query_db(query, args=(), one=False, commit=False):
    """Função utilitária para executar queries abstraindo SQLite e PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ajusta o placeholder de parâmetros (%s para Postgres, ? para SQLite)
    if DB_URL:
        formatted_query = query.replace('?', '%s')
    else:
        formatted_query = query

    cursor.execute(formatted_query, args)

    if commit:
        conn.commit()
        rv = None
    else:
        rv = cursor.fetchall()
        
    cursor.close()
    conn.close()

    if rv:
        return (rv[0] if rv else None) if one else rv
    return None


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Faça login para acessar o painel administrativo.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ==========================================
# ROTAS PÚBLICAS
# ==========================================

@app.route("/")
def index():
    convidados = query_db("SELECT nome, referencia, status FROM convidados ORDER BY nome ASC") or []
    todos_itens = query_db("SELECT * FROM itens ORDER BY subcategoria, nome_item") or []

    itens_por_subcategoria = {}
    for item in todos_itens:
        sub = item["subcategoria"]
        if sub not in itens_por_subcategoria:
            itens_por_subcategoria[sub] = []
        itens_por_subcategoria[sub].append(item)

    return render_template(
        "index.html",
        convidados=convidados,
        itens_agrupados=itens_por_subcategoria
    )


@app.route("/assumir-item", methods=["POST"])
def assumir_item():
    item_id = request.form.get("item_id")
    responsavel = request.form.get("responsavel")

    if item_id and responsavel:
        responsavel_formatado = responsavel.strip().title()
        query_db(
            "UPDATE itens SET responsavel = ? WHERE id = ? AND responsavel IS NULL",
            (responsavel_formatado, item_id),
            commit=True
        )

    return redirect(url_for("index"))


# ==========================================
# ROTAS DE AUTENTICAÇÃO
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == ADMIN_USER and password == ADMIN_PASS:
            session["logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Usuário ou senha incorretos.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("index"))


# ==========================================
# ROTAS ADMINISTRATIVAS (CRUD)
# ==========================================

@app.route("/admin")
@admin_required
def admin_dashboard():
    convidados = query_db("SELECT * FROM convidados ORDER BY nome ASC") or []

    res_total = query_db("SELECT COUNT(*) FROM convidados", one=True)
    res_conf = query_db("SELECT COUNT(*) FROM convidados WHERE status = 'Confirmado'", one=True)
    res_pend = query_db("SELECT COUNT(*) FROM convidados WHERE status = 'Pendente'", one=True)
    res_rec = query_db("SELECT COUNT(*) FROM convidados WHERE status = 'Recusado'", one=True)

    total_geral = res_total[0] if res_total else 0
    total_confirmados = res_conf[0] if res_conf else 0
    total_pendentes = res_pend[0] if res_pend else 0
    total_recusados = res_rec[0] if res_rec else 0

    itens = query_db("SELECT * FROM itens ORDER BY categoria, subcategoria, nome_item") or []

    return render_template(
        "admin.html",
        convidados=convidados,
        total_geral=total_geral,
        total_confirmados=total_confirmados,
        total_pendentes=total_pendentes,
        total_recusados=total_recusados,
        itens=itens
    )


@app.route("/admin/convidado/add", methods=["POST"])
@admin_required
def admin_add_convidado():
    nome = request.form.get("nome")
    referencia = request.form.get("referencia", "")
    status = request.form.get("status", "Pendente")

    if nome:
        nome_fmt = nome.strip().title()
        ref_fmt = referencia.strip().title() if referencia else ""
        query_db(
            "INSERT INTO convidados (nome, referencia, status) VALUES (?, ?, ?)",
            (nome_fmt, ref_fmt, status),
            commit=True
        )
        flash(f"Convidado '{nome_fmt}' adicionado!", "success")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/convidado/edit", methods=["POST"])
@admin_required
def admin_edit_convidado():
    convidado_id = request.form.get("convidado_id")
    nome = request.form.get("nome")
    referencia = request.form.get("referencia", "")
    status = request.form.get("status", "Pendente")

    if convidado_id and nome:
        nome_fmt = nome.strip().title()
        ref_fmt = referencia.strip().title() if referencia else ""
        query_db(
            "UPDATE convidados SET nome = ?, referencia = ?, status = ? WHERE id = ?",
            (nome_fmt, ref_fmt, status, convidado_id),
            commit=True
        )
        flash("Convidado atualizado com sucesso!", "success")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/convidado/update-status", methods=["POST"])
@admin_required
def admin_update_convidado_status():
    convidado_id = request.form.get("convidado_id")
    status = request.form.get("status")

    if convidado_id and status:
        query_db(
            "UPDATE convidados SET status = ? WHERE id = ?",
            (status, convidado_id),
            commit=True
        )

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/convidado/delete", methods=["POST"])
@admin_required
def admin_delete_convidado():
    convidado_id = request.form.get("convidado_id")
    if convidado_id:
        query_db("DELETE FROM convidados WHERE id = ?", (convidado_id,), commit=True)

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/item/add", methods=["POST"])
@admin_required
def admin_add_item():
    categoria = request.form.get("categoria")
    subcategoria = request.form.get("subcategoria")
    nome_item = request.form.get("nome_item")

    if categoria and subcategoria and nome_item:
        sub_fmt = subcategoria.strip().title()
        nome_fmt = nome_item.strip().title()
        query_db(
            "INSERT INTO itens (categoria, subcategoria, nome_item) VALUES (?, ?, ?)",
            (categoria, sub_fmt, nome_fmt),
            commit=True
        )
        flash("Item adicionado com sucesso!", "success")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/item/edit", methods=["POST"])
@admin_required
def admin_edit_item():
    item_id = request.form.get("item_id")
    categoria = request.form.get("categoria")
    subcategoria = request.form.get("subcategoria")
    nome_item = request.form.get("nome_item")

    if item_id and categoria and subcategoria and nome_item:
        sub_fmt = subcategoria.strip().title()
        nome_fmt = nome_item.strip().title()
        query_db(
            "UPDATE itens SET categoria = ?, subcategoria = ?, nome_item = ? WHERE id = ?",
            (categoria, sub_fmt, nome_fmt, item_id),
            commit=True
        )
        flash("Item atualizado com sucesso!", "success")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/item/liberar", methods=["POST"])
@admin_required
def admin_liberar_item():
    item_id = request.form.get("item_id")
    if item_id:
        query_db("UPDATE itens SET responsavel = NULL WHERE id = ?", (item_id,), commit=True)

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/item/delete", methods=["POST"])
@admin_required
def admin_delete_item():
    item_id = request.form.get("item_id")
    if item_id:
        query_db("DELETE FROM itens WHERE id = ?", (item_id,), commit=True)
        flash("Item excluído.", "info")

    return redirect(url_for("admin_dashboard"))


# Inicialização automática do BD
with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)