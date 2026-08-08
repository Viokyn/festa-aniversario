import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = "chave_secreta_aniversario_familia"

ADMIN_USER = "thais"
ADMIN_PASS = "1234"

DB_NAME = "aniversario.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

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
    conn.close()


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
    conn = get_db_connection()

    convidados = conn.execute("SELECT nome, referencia, status FROM convidados ORDER BY nome ASC").fetchall()

    todos_itens = conn.execute(
        "SELECT * FROM itens ORDER BY subcategoria, nome_item"
    ).fetchall()

    itens_por_subcategoria = {}
    for item in todos_itens:
        sub = item["subcategoria"]
        if sub not in itens_por_subcategoria:
            itens_por_subcategoria[sub] = []
        itens_por_subcategoria[sub].append(item)

    conn.close()
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
        conn = get_db_connection()
        conn.execute(
            "UPDATE itens SET responsavel = ? WHERE id = ? AND responsavel IS NULL",
            (responsavel_formatado, item_id)
        )
        conn.commit()
        conn.close()

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
    conn = get_db_connection()

    convidados = conn.execute("SELECT * FROM convidados ORDER BY nome ASC").fetchall()

    total_geral = conn.execute("SELECT COUNT(*) FROM convidados").fetchone()[0]
    total_confirmados = conn.execute("SELECT COUNT(*) FROM convidados WHERE status = 'Confirmado'").fetchone()[0]
    total_pendentes = conn.execute("SELECT COUNT(*) FROM convidados WHERE status = 'Pendente'").fetchone()[0]
    total_recusados = conn.execute("SELECT COUNT(*) FROM convidados WHERE status = 'Recusado'").fetchone()[0]

    itens = conn.execute("SELECT * FROM itens ORDER BY categoria, subcategoria, nome_item").fetchall()
    conn.close()

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
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO convidados (nome, referencia, status) VALUES (?, ?, ?)",
            (nome_fmt, ref_fmt, status)
        )
        conn.commit()
        conn.close()
        flash(f"Convidado '{nome_fmt}' adicionado!", "success")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/convidado/update-status", methods=["POST"])
@admin_required
def admin_update_convidado_status():
    convidado_id = request.form.get("convidado_id")
    status = request.form.get("status")

    if convidado_id and status:
        conn = get_db_connection()
        conn.execute("UPDATE convidados SET status = ? WHERE id = ?", (status, convidado_id))
        conn.commit()
        conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/convidado/delete", methods=["POST"])
@admin_required
def admin_delete_convidado():
    convidado_id = request.form.get("convidado_id")
    if convidado_id:
        conn = get_db_connection()
        conn.execute("DELETE FROM convidados WHERE id = ?", (convidado_id,))
        conn.commit()
        conn.close()

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
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO itens (categoria, subcategoria, nome_item) VALUES (?, ?, ?)",
            (categoria, sub_fmt, nome_fmt)
        )
        conn.commit()
        conn.close()
        flash("Item adicionado com sucesso!", "success")

    return redirect(url_for("admin_dashboard"))


# --- NOVA ROTA PARA EDITAR O ITEM/CATEGORIA ---
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
        conn = get_db_connection()
        conn.execute(
            "UPDATE itens SET categoria = ?, subcategoria = ?, nome_item = ? WHERE id = ?",
            (categoria, sub_fmt, nome_fmt, item_id)
        )
        conn.commit()
        conn.close()
        flash("Item atualizado com sucesso!", "success")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/item/liberar", methods=["POST"])
@admin_required
def admin_liberar_item():
    item_id = request.form.get("item_id")
    if item_id:
        conn = get_db_connection()
        conn.execute("UPDATE itens SET responsavel = NULL WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/item/delete", methods=["POST"])
@admin_required
def admin_delete_item():
    item_id = request.form.get("item_id")
    if item_id:
        conn = get_db_connection()
        conn.execute("DELETE FROM itens WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        flash("Item excluído.", "info")

    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)