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
    total = sum([etapa["tempo"] for etapa in etapas])
    horas = int(total // 60)
    minutos = int(total % 60)
    return f"{horas}:{minutos:02d}"

def etapas_to_list():
    return etapas  # etapas já é uma lista de dicionários


def receita_to_list():
    return [item.to_dict() for item in receita]

def carregar_dados(data):
    global etapas, receita, titulo_grafico, relacao_banho
    etapas = data.get("etapas", [])
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
    tipo = dados["tipo"]
    etapa_dados = dados["dados"]

    tempo = etapa_dados.get("tempo", 0)
    temperatura = etapa_dados.get("temperatura", 0)
    resumo = etapa_dados.get("resumo", "")

    etapas.append({
        "tipo": tipo,
        "dados": {
            "tempo": tempo,
            "temperatura": temperatura,
            "resumo": resumo
        }
    })

    return jsonify(success=True, etapas=etapas, tempo_total=calcular_tempo_total())


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
        return "", 204  # Sem conteúdo

    tempos = [0]
    temperaturas = []

    acumulado = 0
    for etapa in etapas:
        tempo = etapa["dados"].get("tempo", 0)
        temp = etapa["dados"].get("temperatura", 0)

        acumulado += tempo
        tempos.append(acumulado)
        temperaturas.append(temp)

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
    return send_file(buf, mimetype='image/png')  # ✅ Agora dentro da função


@app.route("/imprimir_pdf", methods=["POST"])
def imprimir_pdf():
    incluir_custo = request.json.get("com_custo", False)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    try:
        logo = ImageReader(LOGO_PATH)
        c.drawImage(logo, 440, 720, width=120, preserveAspectRatio=True, mask='auto')
    except:
        pass

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, titulo_grafico or "Processo de Tingimento")
    c.setFont("Helvetica", 11)

    y = 720
    for etapa in etapas:
        dados = etapa["dados"]
        resumo = dados.get("resumo", "")
        linha = f"{etapa['tipo']}: {resumo} - {dados.get('tempo', 0)} min, {dados.get('temperatura', 0)}°C"

        c.drawString(50, y, linha)
        y -= 18
        if y < 100:
            c.showPage()
            y = 750

    c.drawString(50, y - 25, f"Tempo total: {calcular_tempo_total()} h")
    c.drawString(50, y - 40, f"Relação de banho: {relacao_banho}")

    # Página 2: Receita
    c.showPage()
    try:
        c.drawImage(logo, 440, 720, width=120, preserveAspectRatio=True, mask='auto')
    except:
        pass

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "Receita")
    c.setFont("Helvetica", 11)

    y = 720
    total = 0
    for item in receita:
        if incluir_custo:
            subtotal = item.subtotal()
            linha = f"{item.insumo}: {item.quantidade} kg x R$ {item.custo_unitario:.2f} = R$ {subtotal:.2f}"
            total += subtotal
        else:
            linha = f"{item.insumo}: {item.quantidade} kg"
        c.drawString(50, y, linha)
        y -= 18
        if y < 100:
            c.showPage()
            y = 750

    if incluir_custo:
        c.drawString(50, y - 25, f"Total: R$ {total:.2f}")

    c.save()
    buffer.seek(0)

    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name="processo.pdf")


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
    # Configura o diretório 'static' para servir imagens, logo, etc.
    os.makedirs("static", exist_ok=True)
    if not os.path.exists(LOGO_PATH):
        # Cria um placeholder se o logo não existir
        Image.new("RGBA", (300, 100), (255, 255, 255, 0)).save(LOGO_PATH)

    app.run(host="0.0.0.0", port=10000)