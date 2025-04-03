import os
import sys
import threading
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from flask import Flask, request, jsonify
from datetime import datetime, date
import csv

# Verificar se o Python está rodando no ambiente correto
if sys.version_info < (3, 6):
    raise RuntimeError("Python 3.6+ é necessário para rodar este programa.")

def check_dependencies():
    try:
        import flask
    except ImportError:
        print("Flask não está instalado. Instalando...")
        os.system("pip install flask")

check_dependencies()

app = Flask(__name__)

LISTA_ITENS_TXT = "itens.txt"
LISTA_USUARIOS_TXT = "usuarios.txt"
RESERVAS_CSV = "reservas.csv"
EXCLUIDAS_CSV = "reservas_excluidas.csv"

reservas_salvas = set()
lista_usuarios = []
opcoes_itens = {}

def salvar_csv(arquivo, dados, cabecalho):
    existe = os.path.exists(arquivo)
    with open(arquivo, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(cabecalho)
        writer.writerow(dados)

def exibir_tabela_reservas(frame):
    for widget in frame.winfo_children():
        widget.destroy()
    tree = ttk.Treeview(frame, columns=("ID", "Item", "Usuário", "Início", "Fim"), show='headings', height=15)
    for col in ("ID", "Item", "Usuário", "Início", "Fim"):
        tree.heading(col, text=col)
        tree.column(col, width=100)
    tree.pack(fill="both", expand=True)
    with sqlite3.connect("reservas.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT reservas.id, itens.nome, reservas.usuario, reservas.inicio, reservas.fim FROM reservas JOIN itens ON reservas.item_id = itens.id")
        for row in cursor.fetchall():
            tree.insert('', 'end', values=row)

def fazer_reserva():
    selecao_indices = listbox_itens.curselection()
    usuario = cb_usuario.get()
    inicio = entry_inicio.get()
    fim = entry_fim.get()

    if not selecao_indices or not usuario or not inicio or not fim:
        messagebox.showerror("Erro", "Todos os campos são obrigatórios")
        return

    try:
        data_inicio = datetime.strptime(inicio, "%d/%m/%Y").strftime("%Y-%m-%d")
        data_fim = datetime.strptime(fim, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        messagebox.showerror("Erro", "Formato de data inválido. Use DD/MM/AAAA")
        return

    conflitos = []
    reservas_feitas = 0

    with sqlite3.connect("reservas.db") as conn:
        cursor = conn.cursor()
        for i in selecao_indices:
            item_nome = listbox_itens.get(i)
            cursor.execute("SELECT id FROM itens WHERE nome = ?", (item_nome,))
            item = cursor.fetchone()
            if item:
                item_id = item[0]
                cursor.execute("""
                    SELECT COUNT(*) FROM reservas
                    WHERE item_id = ? AND (
                        (? BETWEEN inicio AND fim) OR
                        (? BETWEEN inicio AND fim) OR
                        (inicio BETWEEN ? AND ?) OR
                        (fim BETWEEN ? AND ?)
                    )
                """, (item_id, data_inicio, data_fim, data_inicio, data_fim, data_inicio, data_fim))
                conflito = cursor.fetchone()[0]
                if conflito > 0:
                    conflitos.append(item_nome)
                    continue

                cursor.execute("INSERT INTO reservas (item_id, usuario, inicio, fim) VALUES (?, ?, ?, ?)",
                               (item_id, usuario, data_inicio, data_fim))
                reserva_id = cursor.lastrowid
                salvar_csv(RESERVAS_CSV, [reserva_id, item_nome, usuario, data_inicio, data_fim], ["ID", "Item", "Usuário", "Início", "Fim"])
                reservas_feitas += 1
        conn.commit()

    if reservas_feitas:
        messagebox.showinfo("Sucesso", f"{reservas_feitas} reserva(s) realizadas com sucesso")
    if conflitos:
        messagebox.showwarning("Conflitos", f"Itens já reservados nesse período: {', '.join(conflitos)}")

    exibir_tabela_reservas(frm_tabela)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Sistema de Reservas")

    frame_top = tk.Frame(root)
    frame_top.pack(padx=10, pady=10)

    tk.Label(frame_top, text="Itens disponíveis:").grid(row=0, column=0, sticky='w')
    listbox_itens = tk.Listbox(frame_top, selectmode=tk.MULTIPLE, width=40, height=6)
    listbox_itens.grid(row=1, column=0, columnspan=2)

    tk.Label(frame_top, text="Usuário:").grid(row=2, column=0, sticky='w')
    cb_usuario = ttk.Combobox(frame_top, width=30)
    cb_usuario.grid(row=2, column=1)

    tk.Label(frame_top, text="Data de Início (DD/MM/AAAA):").grid(row=3, column=0, sticky='w')
    entry_inicio = tk.Entry(frame_top)
    entry_inicio.grid(row=3, column=1)

    tk.Label(frame_top, text="Data de Fim (DD/MM/AAAA):").grid(row=4, column=0, sticky='w')
    entry_fim = tk.Entry(frame_top)
    entry_fim.grid(row=4, column=1)

    tk.Button(frame_top, text="Fazer Reserva", command=fazer_reserva).grid(row=5, column=0, columnspan=2, pady=10)

    frm_tabela = tk.Frame(root)
    frm_tabela.pack(fill="both", expand=True, padx=10, pady=10)

    exibir_tabela_reservas(frm_tabela)

    with sqlite3.connect("reservas.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nome FROM itens")
        itens = [row[0] for row in cursor.fetchall()]
        listbox_itens.delete(0, tk.END)
        for item in itens:
            listbox_itens.insert(tk.END, item)

    if os.path.exists(LISTA_USUARIOS_TXT):
        with open(LISTA_USUARIOS_TXT, "r", encoding="utf-8") as f:
            usuarios = [linha.strip() for linha in f if linha.strip()]
            cb_usuario['values'] = usuarios
            if usuarios:
                cb_usuario.set(usuarios[0])

    tk.Button(root, text="Sair do Programa", command=root.destroy).pack(pady=5)

    root.mainloop()
