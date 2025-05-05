from flask import Flask, render_template, request, redirect, send_file, jsonify
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PIL import Image
import io
import os
import json
from datetime import datetime

app = Flask(__name__)

# Variáveis de dados
etapas = []
receita = []
titulo_grafico = ""
relacao_banho = ""
tempo_total = "0:00"

# Caminho do logotipo da Hanier
LOGO_PATH = "static/logo_hanier.png"

# Classe Etapa
class Etapa:
    def __init__(self, tipo, tempo, temperatura):
        self.tipo = tipo
        self.tempo = float(tempo)
        self.temperatura = float(temperatura)

    def to_dict(self):
        return {
            "tipo": self.tipo,
            "tempo": self.tempo,
            "temperatura": self.temperatura
        }

# Classe ReceitaItem
class ReceitaItem:
    def __init__(self, insumo, quantidade, custo_unitario):
        self.insumo = insumo
        self.quantidade = float(quantidade)
        self.custo_unitario = float(custo_unitario)

    def subtotal(self):
        return self.quantidade * self.custo_unitario

    def to_dict(self):
        return {
            "insumo": self.insumo,
            "quantidade": self.quantidade,
            "custo_unitario": self.custo_unitario
        }

# Funções auxiliares
def calcular_tempo_total():
    total = sum([etapa.tempo for etapa in etapas])
    horas = int(total // 60)
    minutos = int(total % 60)
    return f"{horas}:{minutos:02d}"

def etapas_to_list():
    return [etapa.to_dict() for etapa in etapas]

def receita_to_list():
    return [item.to_dict() for item in receita]

def carregar_dados(data):
    global etapas, receita, titulo_grafico, relacao_banho
    etapas = [Etapa(**e) for e in data.get("etapas", [])]
    receita = [ReceitaItem(**r) for r in data.get("receita", [])]
    titulo_grafico = data.get("titulo", "")
    relacao_banho = data.get("relacao_banho", "")

@app.route("/")
def index():
    return render_template("index.html", etapas=etapas_to_list(), receita=receita_to_list(),
                           titulo=titulo_grafico, relacao_banho=relacao_banho,
                           tempo_total=calcular_tempo_total())

@app.route("/adicionar_etapa", methods=["POST"])
def adicionar_etapa():
    dados = request.json
    etapas.append(Etapa(dados["tipo"], dados["tempo"], dados["temperatura"]))
    return jsonify(success=True, etapas=etapas_to_list(), tempo_total=calcular_tempo_total())

@app.route("/subir_etapa/<int:index>", methods=["POST"])
def subir_etapa(index):
    if 0 < index < len(etapas):
        etapas[index - 1], etapas[index] = etapas[index], etapas[index - 1]
    return jsonify(etapas=etapas_to_list())

@app.route("/descer_etapa/<int:index>", methods=["POST"])
def descer_etapa(index):
    if 0 <= index < len(etapas) - 1:
        etapas[index + 1], etapas[index] = etapas[index], etapas[index + 1]
    return jsonify(etapas=etapas_to_list())

@app.route("/excluir_etapa/<int:index>", methods=["POST"])
def excluir_etapa(index):
    if 0 <= index < len(etapas):
        etapas.pop(index)
    return jsonify(etapas=etapas_to_list(), tempo_total=calcular_tempo_total())

@app.route("/limpar_etapas", methods=["POST"])
def limpar_etapas():
    etapas.clear()
    return jsonify(etapas=etapas_to_list(), tempo_total="0:00")

@app.route("/atualizar_titulo", methods=["POST"])
def atualizar_titulo():
    global titulo_grafico
    titulo_grafico = request.json.get("titulo", "")
    return jsonify(success=True)

@app.route("/atualizar_relacao", methods=["POST"])
def atualizar_relacao():
    global relacao_banho
    relacao_banho = request.json.get("relacao", "")
    return jsonify(success=True)

@app.route("/atualizar_receita", methods=["POST"])
def atualizar_receita():
    global receita
    dados = request.json.get("receita", [])
    receita = [ReceitaItem(item["insumo"], item["quantidade"], item["custo_unitario"]) for item in dados]
    return jsonify(success=True)

@app.route("/grafico.png")
def gerar_grafico():
    if not etapas:
        return "", 204

    tempos = [0]
    temperaturas = []
    acumulado = 0

    for etapa in etapas:
        acumulado += etapa.tempo
        tempos.append(acumulado)
        temperaturas.append(etapa.temperatura)

    if len(temperaturas) < len(tempos):
        temperaturas.insert(0, temperaturas[0])

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(tempos, temperaturas, marker='o', color='royalblue')
    ax.set_xlabel("Tempo (min)")
    ax.set_ylabel("Temperatura (°C)")
    ax.set_title(titulo_grafico or "Gráfico de Tingimento")
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)

    response = send_file(buf, mimetype='image/png')
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/imprimir_pdf", methods=["POST"])
def imprimir_pdf():
    incluir_custo = request.json.get("com_custo", False)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    buf_img = io.BytesIO()
    gerar_grafico().save(buf_img)
    buf_img.seek(0)
    img = ImageReader(buf_img)
    w, h = letter
    img_w = w - 80
    img_h = img_w * 0.5
    c.drawImage(img, 40, h - 40 - img_h, img_w, img_h)

    y = h - 60 - img_h
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Descritivo de Etapas:")
    y -= 20
    c.setFont("Helvetica", 10)
    for i, e in enumerate(etapas, 1):
        if y < 60:
            c.showPage()
            y = h - 40
        resumo = ", ".join(f"{k}: {v}" for k, v in e.to_dict().items())
        tempo = e.to_dict().get("tempo", "")
        c.drawString(40, y, f"{i}. {e.tipo}: {resumo} ({tempo} min)")
        y -= 15

    c.showPage()
    y = h - 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Receita:")
    y -= 20

    colunas = ["insumo", "quantidade"]
    if incluir_custo:
        colunas.append("custo_unitario")

    col_width = (w - 80) // len(colunas)
    c.setFont("Helvetica-Bold", 9)
    x = 40
    for col in colunas:
        c.drawString(x, y, col.capitalize())
        x += col_width
    y -= 12

    c.setFont("Helvetica", 9)
    total = 0.0
    for item in receita:
        if y < 60:
            c.showPage()
            y = h - 40
        x = 40
        for col in colunas:
            val = getattr(item, col)
            if isinstance(val, float):
                val = f"{val:.2f}"
            c.drawString(x, y, str(val))
            x += col_width
        if incluir_custo:
            total += item.subtotal()
        y -= 12

    if incluir_custo:
        y -= 10
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, f"Custo total: R$ {total:.2f}")

    c.save()
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="processo.pdf")

@app.route("/salvar_dados", methods=["GET"])
def salvar_dados():
    dados = {
        "etapas": etapas_to_list(),
        "receita": receita_to_list(),
        "titulo": titulo_grafico,
        "relacao_banho": relacao_banho
    }
    buffer = io.BytesIO()
    buffer.write(json.dumps(dados, indent=2).encode("utf-8"))
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="processo_dados.json", mimetype="application/json")

@app.route("/carregar_dados", methods=["POST"])
def carregar_arquivo():
    file = request.files.get("file")
    if not file:
        return jsonify(success=False, error="Arquivo não encontrado.")
    try:
        dados = json.load(file)
        carregar_dados(dados)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e))

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    if not os.path.exists(LOGO_PATH):
        Image.new("RGBA", (300, 100), (255, 255, 255, 0)).save(LOGO_PATH)
    app.run(host="0.0.0.0", port=10000)
