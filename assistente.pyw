# ==============================================================================
#  ASSISTENTE DE TAREFAS PESSOAL v3.5 - Correção Final de Bug (ValueError)
# ==============================================================================

# --- PARTE 1: IMPORTAÇÕES E CONFIGURAÇÃO INICIAL ---
import tkinter as tk
from tkinter import messagebox
import sqlite3
from datetime import datetime, timedelta
import threading
import schedule
import time
import os
import sys
import logging

from gtts import gTTS
from playsound import playsound
from PIL import Image
import pystray

# (O código de configuração inicial permanece o mesmo da v3.4)
def get_app_data_folder():
    app_data_path = os.getenv('APPDATA')
    if not app_data_path: app_data_path = os.path.abspath(".")
    assistente_path = os.path.join(app_data_path, 'AssistenteDeTarefas')
    os.makedirs(assistente_path, exist_ok=True)
    return assistente_path

APP_DATA_FOLDER = get_app_data_folder()
DB_PATH = os.path.join(APP_DATA_FOLDER, 'tarefas.db')
LOG_PATH = os.path.join(APP_DATA_FOLDER, 'assistente.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_PATH, encoding='utf-8'), logging.StreamHandler(sys.stdout)]
)

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def falar(texto):
    logging.info(f"IA tentando falar: {texto}")
    try:
        tts = gTTS(text=texto, lang='pt-br', slow=False)
        arquivo_audio_temporario = resource_path("temp_audio.mp3")
        tts.save(arquivo_audio_temporario)
        playsound(arquivo_audio_temporario)
        os.remove(arquivo_audio_temporario)
    except Exception as e:
        logging.error(f"ERRO ao tentar falar: {e}")

def falar_em_thread(texto):
    threading.Thread(target=falar, args=(texto,), daemon=True).start()

def iniciar_banco_de_dados():
    conexao = sqlite3.connect(DB_PATH)
    cursor = conexao.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            horario TEXT NOT NULL,
            data TEXT NOT NULL,
            concluida INTEGER NOT NULL DEFAULT 0,
            lembrete_inicial_dado INTEGER NOT NULL DEFAULT 0,
            proximo_lembrete_horario TEXT 
        )
    ''')
    try:
        cursor.execute("PRAGMA table_info(tarefas)")
        colunas = [coluna[1] for coluna in cursor.fetchall()]
        if 'proximo_lembrete_horario' not in colunas:
            cursor.execute("ALTER TABLE tarefas ADD COLUMN proximo_lembrete_horario TEXT")
    except Exception as e:
        logging.error(f"Erro ao verificar/atualizar banco de dados: {e}")
    conexao.commit()
    conexao.close()

# (Funções de DB e da Interface permanecem as mesmas da v3.4)
def adicionar_tarefa_db(descricao, horario):
    hoje_str = datetime.now().strftime('%d-%m-%Y')
    conexao = sqlite3.connect(DB_PATH)
    cursor = conexao.cursor()
    cursor.execute("INSERT INTO tarefas (descricao, horario, data) VALUES (?, ?, ?)", (descricao, horario, hoje_str))
    conexao.commit()
    conexao.close()
    logging.info(f"Tarefa '{descricao}' adicionada ao banco de dados.")

def carregar_tarefas_db():
    hoje_str = datetime.now().strftime('%d-%m-%Y')
    if not os.path.exists(DB_PATH): return []
    conexao = sqlite3.connect(DB_PATH)
    cursor = conexao.cursor()
    cursor.execute("SELECT * FROM tarefas WHERE data = ? AND concluida = 0 ORDER BY horario", (hoje_str,))
    tarefas = cursor.fetchall()
    conexao.close()
    return tarefas

def marcar_concluida_db(id_tarefa):
    conexao = sqlite3.connect(DB_PATH)
    cursor = conexao.cursor()
    cursor.execute("UPDATE tarefas SET concluida = 1 WHERE id = ?", (id_tarefa,))
    conexao.commit()
    conexao.close()
    logging.info(f"Tarefa ID {id_tarefa} marcada como concluída.")

def deletar_tarefa_db(id_tarefa):
    conexao = sqlite3.connect(DB_PATH)
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM tarefas WHERE id = ?", (id_tarefa,))
    conexao.commit()
    conexao.close()
    logging.info(f"Tarefa ID {id_tarefa} deletada.")

def atualizar_status_lembrete_db(id_tarefa, inicial_dado=None, proximo_horario=None):
    conexao = sqlite3.connect(DB_PATH)
    cursor = conexao.cursor()
    if inicial_dado is not None:
        cursor.execute("UPDATE tarefas SET lembrete_inicial_dado = ? WHERE id = ?", (inicial_dado, id_tarefa))
        logging.info(f"Lembrete inicial para tarefa ID {id_tarefa} marcado como enviado.")
    if proximo_horario is not None:
        cursor.execute("UPDATE tarefas SET proximo_lembrete_horario = ? WHERE id = ?", (proximo_horario, id_tarefa))
        logging.info(f"Próximo lembrete para tarefa ID {id_tarefa} agendado para {proximo_horario}.")
    conexao.commit()
    conexao.close()

lista_de_tarefas_carregadas = []

def atualizar_lista_tarefas():
    global lista_de_tarefas_carregadas
    listbox_tarefas.delete(0, tk.END)
    lista_de_tarefas_carregadas = carregar_tarefas_db()
    for tarefa in lista_de_tarefas_carregadas:
        _, descricao, horario, *_ = tarefa
        texto_exibicao = f"{horario} - {descricao}"
        listbox_tarefas.insert(tk.END, texto_exibicao)

def on_adicionar_tarefa():
    descricao = entry_descricao.get()
    horario = entry_horario.get()
    if not descricao or not horario:
        messagebox.showwarning("Aviso", "Por favor, preencha a descrição e o horário.")
        return
    adicionar_tarefa_db(descricao, horario)
    falar_em_thread(f"Tarefa '{descricao}' adicionada.")
    entry_descricao.delete(0, tk.END)
    entry_horario.delete(0, tk.END)
    atualizar_lista_tarefas()

def get_id_from_selection():
    try:
        indices_selecionados = listbox_tarefas.curselection()
        if not indices_selecionados: raise IndexError
        indice = indices_selecionados[0]
        tarefa_selecionada = lista_de_tarefas_carregadas[indice]
        return tarefa_selecionada[0]
    except IndexError:
        messagebox.showwarning("Aviso", "Por favor, selecione uma tarefa na lista.")
        return None

def on_marcar_concluida():
    id_tarefa = get_id_from_selection()
    if id_tarefa:
        marcar_concluida_db(id_tarefa)
        falar_em_thread("Tarefa concluída, Mestre!")
        atualizar_lista_tarefas()

def on_deletar_tarefa():
    id_tarefa = get_id_from_selection()
    if id_tarefa:
        if messagebox.askyesno("Confirmar", "Tem certeza que deseja deletar esta tarefa?"):
            deletar_tarefa_db(id_tarefa)
            falar_em_thread("Tarefa deletada.")
            atualizar_lista_tarefas()

# --- PARTE 5: LÓGICA DE BACKGROUND ---
def saudacao_inicial():
    tarefas = carregar_tarefas_db()
    if not tarefas:
        mensagem = "Olá Mestre! Hoje não temos tarefas pendentes."
    else:
        lista_de_tarefas_str = ", ".join([t[1] for t in tarefas])
        mensagem = f"Olá Mestre! Suas tarefas pendentes para hoje são: {lista_de_tarefas_str}."
    falar_em_thread(mensagem)

def verificar_lembretes():
    logging.info("Verificando lembretes em background...")
    agora_str = datetime.now().strftime('%H:%M')
    tarefas_pendentes = carregar_tarefas_db()

    for tarefa in tarefas_pendentes:
        ### LINHA CORRIGIDA ###
        id_tarefa, descricao, horario_tarefa_str, _, _, lembrete_inicial_dado, proximo_lembrete_horario = tarefa
        
        if not lembrete_inicial_dado and agora_str == horario_tarefa_str:
            mensagem = f"Mestre, está na hora de completar a tarefa: {descricao}."
            falar_em_thread(mensagem)
            horario_tarefa_obj = datetime.strptime(horario_tarefa_str, '%H:%M')
            proximo_horario_obj = horario_tarefa_obj + timedelta(minutes=30)
            proximo_horario_str = proximo_horario_obj.strftime('%H:%M')
            atualizar_status_lembrete_db(id_tarefa, inicial_dado=1, proximo_horario=proximo_horario_str)
            continue
            
        if lembrete_inicial_dado and proximo_lembrete_horario == agora_str:
            mensagem = f"Mestre, um aviso. A tarefa '{descricao}' ainda está pendente."
            falar_em_thread(mensagem)
            horario_lembrete_atual_obj = datetime.strptime(proximo_lembrete_horario, '%H:%M')
            proximo_horario_obj = horario_lembrete_atual_obj + timedelta(minutes=30)
            proximo_horario_str = proximo_horario_obj.strftime('%H:%M')
            atualizar_status_lembrete_db(id_tarefa, proximo_horario=proximo_horario_str)

def rodar_em_background():
    saudacao_inicial()
    schedule.every(1).minute.do(verificar_lembretes)
    while True:
        schedule.run_pending()
        time.sleep(1)

def sair_do_app(icon, item):
    logging.info("Saindo do aplicativo.")
    icon.stop()
    root.destroy()

def mostrar_janela(icon, item):
    icon.stop()
    root.after(0, root.deiconify)
    root.after(0, root.lift)
    root.after(0, root.focus_force)

def esconder_janela():
    root.withdraw()
    image = Image.open(resource_path("icon.png"))
    menu = (pystray.MenuItem('Mostrar', mostrar_janela, default=True), 
            pystray.MenuItem('Sair', sair_do_app))
    icon = pystray.Icon("Assistente", image, "Assistente de Tarefas", menu)
    icon.run()

# --- PARTE 6: CRIAÇÃO DA JANELA PRINCIPAL (TKINTER) ---
if __name__ == "__main__":
    iniciar_banco_de_dados()
    root = tk.Tk()
    root.title("Assistente de Tarefas v3.5")
    root.geometry("500x450")
    root.resizable(False, False)
    try:
        icone_janela = tk.PhotoImage(file=resource_path('icon.png')) 
        root.iconphoto(True, icone_janela)
    except tk.TclError:
        logging.warning("Não foi possível carregar o ícone da janela.")

    frame_entrada = tk.Frame(root, pady=10)
    frame_entrada.pack()
    tk.Label(frame_entrada, text="Tarefa:").pack(side=tk.LEFT, padx=5)
    entry_descricao = tk.Entry(frame_entrada, width=30)
    entry_descricao.pack(side=tk.LEFT)
    tk.Label(frame_entrada, text="Horário (HH:MM):").pack(side=tk.LEFT, padx=5)
    entry_horario = tk.Entry(frame_entrada, width=10)
    entry_horario.pack(side=tk.LEFT)

    frame_lista = tk.Frame(root, pady=10)
    frame_lista.pack()
    listbox_tarefas = tk.Listbox(frame_lista, width=70, height=15)
    listbox_tarefas.pack(side=tk.LEFT, fill=tk.BOTH)
    scrollbar = tk.Scrollbar(frame_lista)
    scrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
    listbox_tarefas.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=listbox_tarefas.yview)

    frame_botoes = tk.Frame(root, pady=10)
    frame_botoes.pack()
    btn_adicionar = tk.Button(frame_botoes, text="Adicionar Tarefa", command=on_adicionar_tarefa)
    btn_adicionar.pack(side=tk.LEFT, padx=10)
    btn_concluir = tk.Button(frame_botoes, text="Marcar como Concluída", command=on_marcar_concluida)
    btn_concluir.pack(side=tk.LEFT, padx=10)
    btn_deletar = tk.Button(frame_botoes, text="Deletar Tarefa", command=on_deletar_tarefa)
    btn_deletar.pack(side=tk.LEFT, padx=10)

    atualizar_lista_tarefas()
    
    thread_background = threading.Thread(target=rodar_em_background, daemon=True)
    thread_background.start()
    
    root.protocol('WM_DELETE_WINDOW', esconder_janela)
    
    logging.info("Aplicativo iniciado com sucesso.")
    root.mainloop()