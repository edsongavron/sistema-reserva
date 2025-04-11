from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
import os
from datetime import datetime
import csv

app = Flask(__name__)
app.secret_key = 'segredo-reservas'

LISTA_ITENS_TXT = "itens.txt"
LISTA_USUARIOS_TXT = "usuarios.txt"
RESERVAS_CSV = "reservas.csv"
EXCLUIDAS_CSV = "reservas_excluidas.csv"
EXPORT_DIR = "exportacoes"
os.makedirs(EXPORT_DIR, exist_ok=True)

@app.route("/exportar_reservas")
def exportar_reservas():
    nome_arquivo = os.path.join(EXPORT_DIR, "reservas_exportadas.csv")
    with sqlite3.connect("reservas.db") as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT reservas.id, itens.nome, reservas.usuario, reservas.inicio, reservas.fim, COALESCE(reservas.exposicao, '')
            FROM reservas JOIN itens ON reservas.item_id = itens.id
        """)
        reservas = cur.fetchall()
        with open(nome_arquivo, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Item", "Usuário", "Início", "Fim", "Exposição"])
            for r in reservas:
                writer.writerow(r)
    return send_file(nome_arquivo, as_attachment=True)

@app.route("/exportar_reservados")
def exportar_reservados():
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    try:
        datetime.strptime(inicio, "%Y-%m-%d")
        datetime.strptime(fim, "%Y-%m-%d")
    except ValueError:
        flash("Datas inválidas.")
        return redirect(url_for("home"))

    nome_arquivo = os.path.join(EXPORT_DIR, f"reservados_{inicio}_a_{fim}.csv")
    with sqlite3.connect("reservas.db") as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT reservas.id, itens.nome, reservas.usuario, reservas.inicio, reservas.fim, COALESCE(reservas.exposicao, '')
            FROM reservas JOIN itens ON reservas.item_id = itens.id
            WHERE (inicio <= ? AND fim >= ?)
            ORDER BY inicio ASC
        """, (fim, inicio))
        dados = cur.fetchall()
        with open(nome_arquivo, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Item", "Usuário", "Início", "Fim", "Exposição"])
            for r in dados:
                writer.writerow(r)
    return send_file(nome_arquivo, as_attachment=True)



def carregar_usuarios():
    if os.path.exists(LISTA_USUARIOS_TXT):
        with open(LISTA_USUARIOS_TXT, encoding='utf-8') as f:
            return [linha.strip() for linha in f if linha.strip()]
    return []

@app.route("/reservar", methods=["POST"])
def reservar():
    usuario = request.form.get("usuario")
    itens_selecionados = request.form.getlist("itens")
    inicio = request.form.get("inicio")
    fim = request.form.get("fim")
    exposicao = request.form.get("exposicao", "")

    try:
        data_inicio_dt = datetime.strptime(inicio, "%Y-%m-%d")
        data_fim_dt = datetime.strptime(fim, "%Y-%m-%d")
        if data_inicio_dt > data_fim_dt:
            flash("A data de início deve ser anterior ou igual à data de fim.")
            return redirect(url_for("home"))
        data_inicio = data_inicio_dt.strftime("%Y-%m-%d")
        data_fim = data_fim_dt.strftime("%Y-%m-%d")
    except ValueError:
        flash("Data inválida. Use o formato correto.")
        return redirect(url_for("home"))

    reservas_feitas = 0
    conflitos = []
    with sqlite3.connect("reservas.db") as conn:
        cur = conn.cursor()
        for item_nome in itens_selecionados:
            cur.execute("SELECT id FROM itens WHERE nome = ?", (item_nome,))
            item = cur.fetchone()
            if item:
                item_id = item[0]
                cur.execute("""
                    SELECT COUNT(*) FROM reservas
                    WHERE item_id = ? AND (
                        (? BETWEEN inicio AND fim) OR
                        (? BETWEEN inicio AND fim) OR
                        (inicio BETWEEN ? AND ?) OR
                        (fim BETWEEN ? AND ?)
                    )
                """, (item_id, data_inicio, data_fim, data_inicio, data_fim, data_inicio, data_fim))
                conflito = cur.fetchone()[0]
                if conflito == 0:
                    cur.execute("INSERT INTO reservas (item_id, usuario, inicio, fim, exposicao) VALUES (?, ?, ?, ?, ?)",
                                (item_id, usuario, data_inicio, data_fim, exposicao))
                    
                    reservas_feitas += 1
                else:
                    conflitos.append(item_nome)
        conn.commit()

    if reservas_feitas:
        flash(f"{reservas_feitas} reserva(s) realizadas com sucesso.")
    if conflitos:
        flash(f"Itens com conflito de datas: {', '.join(conflitos)}")
    return redirect(url_for("home"))

@app.route("/excluir/<int:reserva_id>")
def excluir(reserva_id):
    with sqlite3.connect("reservas.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT reservas.id, itens.nome, reservas.usuario, reservas.inicio, reservas.fim FROM reservas JOIN itens ON reservas.item_id = itens.id WHERE reservas.id = ?", (reserva_id,))
        reserva = cur.fetchone()
        if reserva:
            with open(EXCLUIDAS_CSV, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if os.stat(EXCLUIDAS_CSV).st_size == 0:
                    writer.writerow(["ID", "Item", "Usuário", "Início", "Fim"])
                writer.writerow(reserva)
            cur.execute("DELETE FROM reservas WHERE id = ?", (reserva_id,))
            conn.commit()
            flash("Reserva excluída com sucesso.")
    return redirect(url_for("home"))

@app.route("/")
def home():
    hoje = datetime.today().strftime("%Y-%m-%d")
    with sqlite3.connect("reservas.db") as conn:
        cur = conn.cursor()

        # Excluir reservas expiradas
        cur.execute("""
            SELECT reservas.id, itens.nome, reservas.usuario, reservas.inicio, reservas.fim, COALESCE(reservas.exposicao, '')
            FROM reservas JOIN itens ON reservas.item_id = itens.id
            WHERE reservas.fim < ?
        """, (hoje,))
        expiradas = cur.fetchall()

        for reserva in expiradas:
            with open(EXCLUIDAS_CSV, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if os.stat(EXCLUIDAS_CSV).st_size == 0:
                    writer.writerow(["ID", "Item", "Usuário", "Início", "Fim", "Exposição"])
                writer.writerow(reserva)
            cur.execute("DELETE FROM reservas WHERE id = ?", (reserva[0],))
        conn.commit()

        # Buscar reservas ativas
        cur.execute("""
            SELECT reservas.id, itens.nome, reservas.usuario, reservas.inicio, reservas.fim, COALESCE(reservas.exposicao, '')
            FROM reservas JOIN itens ON reservas.item_id = itens.id
            ORDER BY reservas.inicio ASC
        """)
        reservas = cur.fetchall()

        cur.execute("SELECT nome FROM itens")
        itens = [row[0] for row in cur.fetchall()]

    usuarios = carregar_usuarios()
    return render_template("home.html", reservas=reservas, itens=itens, usuarios=usuarios)



@app.route("/exportar_disponiveis")
def exportar_disponiveis():
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    try:
        datetime.strptime(inicio, "%Y-%m-%d")
        datetime.strptime(fim, "%Y-%m-%d")
    except ValueError:
        flash("Datas inválidas.")
        return redirect(url_for("home"))

    nome_arquivo = os.path.join(EXPORT_DIR, f"disponiveis_{inicio}_a_{fim}.csv")
    with sqlite3.connect("reservas.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT nome FROM itens")
        todos_itens = {row[0] for row in cur.fetchall()}

        cur.execute("""
            SELECT DISTINCT itens.nome FROM reservas
            JOIN itens ON reservas.item_id = itens.id
            WHERE (
                (? BETWEEN reservas.inicio AND reservas.fim) OR
                (? BETWEEN reservas.inicio AND reservas.fim) OR
                (reservas.inicio BETWEEN ? AND ?) OR
                (reservas.fim BETWEEN ? AND ?)
            )
        """, (inicio, fim, inicio, fim, inicio, fim))
        reservados = {row[0] for row in cur.fetchall()}

        disponiveis = sorted(todos_itens - reservados)

        with open(nome_arquivo, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Itens disponíveis", "Período"])
            for item in disponiveis:
                writer.writerow([item, f"{inicio} a {fim}"])
    return send_file(nome_arquivo, as_attachment=True)

def init_db():
    with sqlite3.connect("reservas.db") as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS reservas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                usuario TEXT NOT NULL,
                inicio TEXT NOT NULL,
                fim TEXT NOT NULL,
                FOREIGN KEY(item_id) REFERENCES itens(id)
            )
        """)

        # ✅ ADICIONE ESTE BLOCO AQUI 👇
        # Verifica se a coluna 'exposicao' já existe na tabela 'reservas'
        c.execute("PRAGMA table_info(reservas)")
        colunas = [linha[1] for linha in c.fetchall()]
        if "exposicao" not in colunas:
            c.execute("ALTER TABLE reservas ADD COLUMN exposicao TEXT")

        conn.commit()

        if os.path.exists(LISTA_ITENS_TXT):
            with open(LISTA_ITENS_TXT, encoding='utf-8') as f:
                itens = [linha.strip() for linha in f if linha.strip()]
                for nome in itens:
                    c.execute("INSERT OR IGNORE INTO itens (nome) VALUES (?)", (nome,))
        conn.commit()


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
