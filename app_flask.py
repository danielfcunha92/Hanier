
import io
import json
import os
from flask import Flask, render_template, request, session, jsonify, send_file
from matplotlib import pyplot as plt
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret')
LOGO_PATH = 'static/logo_hanier.png'


@app.before_request
def init_session():
    session.setdefault('etapas', [])
    session.setdefault('receita', [])
    session.setdefault('titulo', 'Gráficos de Tingimento')


@app.route('/')
def index():
    etapas = session.get('etapas', [])
    total_min = sum(
        et.get('dados', {}).get('tempo', 0)
        for et in etapas
    )
    horas, minutos = divmod(int(total_min), 60)
    tempo_str = f"{horas}:{minutos:02d}"
    return render_template(
        'index.html',
        etapas=etapas,
        tempo_total=tempo_str,
        titulo=session.get('titulo', ''),
        etapas_json=json.dumps(etapas),
        receita_json=json.dumps(session.get('receita', []))
    )


@app.route('/adicionar_etapa', methods=['POST'])
def adicionar_etapa():
    data = request.get_json()
    session['etapas'].append(data)
    session.modified = True
    total_min = sum(
        et.get('dados', {}).get('tempo', 0)
        for et in session['etapas']
    )
    horas, minutos = divmod(int(total_min), 60)
    tempo_str = f"{horas}:{minutos:02d}"
    return jsonify(success=True, tempo_total=tempo_str)


@app.route('/editar_etapa/<int:idx>', methods=['POST'])
def editar_etapa(idx):
    data = request.get_json()
    if 0 <= idx < len(session['etapas']):
        session['etapas'][idx] = data
        session.modified = True
    return jsonify(success=True)


@app.route('/excluir_etapa/<int:idx>', methods=['POST'])
def excluir_etapa(idx):
    if 0 <= idx < len(session['etapas']):
        session['etapas'].pop(idx)
        session.modified = True
    return jsonify(success=True)


@app.route('/subir_etapa/<int:idx>', methods=['POST'])
def subir_etapa(idx):
    et = session['etapas']
    if 0 < idx < len(et):
        et[idx-1], et[idx] = et[idx], et[idx-1]
        session.modified = True
    return jsonify(success=True)


@app.route('/descer_etapa/<int:idx>', methods=['POST'])
def descer_etapa(idx):
    et = session['etapas']
    if 0 <= idx < len(et)-1:
        et[idx], et[idx+1] = et[idx+1], et[idx]
        session.modified = True
    return jsonify(success=True)


@app.route('/limpar_etapas', methods=['POST'])
def limpar_etapas():
    session['etapas'].clear()
    session.modified = True
    return jsonify(success=True)


@app.route('/atualizar_titulo', methods=['POST'])
def atualizar_titulo():
    data = request.get_json()
    session['titulo'] = data.get('titulo', session['titulo'])
    session.modified = True
    return jsonify(success=True)


@app.route('/salvar_dados')
def salvar_dados():
    dados = {
        'titulo': session['titulo'],
        'etapas': session['etapas'],
        'receita': session['receita']
    }
    buf = io.BytesIO()
    buf.write(json.dumps(dados, indent=2).encode())
    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/json',
        download_name='dados_tingimento.json',
        as_attachment=True
    )


@app.route('/carregar_dados', methods=['POST'])
def carregar_dados():
    file = request.files.get('file')
    try:
        # carrega JSON (pode ser dict ou lista)
        data = json.load(file)

        if isinstance(data, dict):
            # formato { "titulo":..., "etapas":[...], "receita":[...] }
            session['titulo']  = data.get('titulo', session['titulo'])
            session['etapas']  = data.get('etapas', [])
            session['receita'] = data.get('receita', [])
        elif isinstance(data, list):
            # formato antigo: raiz é lista de etapas
            session['etapas'] = data
            # mantém titulo/receita atuais, se houver
        else:
            # tipo inesperado
            return jsonify(success=False, error="JSON deve ser objeto ou lista"), 400

        session.modified = True
        return jsonify(success=True)

    except Exception as e:
        return jsonify(success=False, error=str(e))



@app.route('/grafico.png')
def grafico_png():
    etapas = session.get('etapas', [])
    if not etapas:
        return '', 204

    # ─── montagem de tempos, temps e acum ───
    tempos = [0]
    temps  = [etapas[0].get('dados', {}).get('temperatura', 0)]
    acum   = 0
    for et in etapas:
        t    = et.get('dados', {}).get('tempo', 0)
        temp = et.get('dados', {}).get('temperatura', 0)
        acum += t
        tempos.append(acum)
        temps.append(temp)
    # ────────────────────────────────────────

    buf = io.BytesIO()
    fig, ax = plt.subplots(figsize=(8,4))
    ax.plot(tempos, temps, marker='o')
    ax.set_xlabel('Tempo (min)')
    ax.set_ylabel('Temperatura (°C)')

    # título acima do gráfico
    ax.set_title(session.get('titulo', ''), pad=15)

    # caixa com o tempo total, posicionada acima do quadrado do gráfico
    h, m = divmod(int(acum), 60)
    ax.text(
        0.98, 1.02,
        f"Tempo Total: {h}:{m:02d}",
        transform=ax.transAxes,
        ha='right', va='bottom',
 
    )

    plt.tight_layout()
    fig.savefig(buf, format='png')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')





@app.route('/imprimir_pdf', methods=['POST'])
def imprimir_pdf():
    data = request.get_json()
    com_custo = data.get('com_custo', False)
    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=letter)
    try:
        logo = ImageReader(LOGO_PATH)
        c.drawImage(logo, 440, 750, width=120, preserveAspectRatio=True, mask='auto')
    except:
        pass
    c.setFont('Helvetica-Bold', 14)
    c.drawString(50, 800, session.get('titulo', ''))

    # Gráfico inline
    chart_buf = io.BytesIO()
    tempos = [0]
    temps = [session['etapas'][0].get('dados', {}).get('temperatura', 0) if session['etapas'] else 0]
    acum = 0
    for et in session['etapas']:
        t = et.get('dados', {}).get('tempo', 0)
        temp = et.get('dados', {}).get('temperatura', 0)
        acum += t
        tempos.append(acum)
        temps.append(temp)
    plt.figure(figsize=(8, 4))
    plt.plot(tempos, temps, marker='o')
    plt.tight_layout()
    plt.savefig(chart_buf, format='png')
    chart_buf.seek(0)
    c.drawImage(
        ImageReader(chart_buf),
        50, 500,
        width=500, height=250
    )

    y = 480
    c.setFont('Helvetica', 11)
    for et in session['etapas']:
        txt = f"- {et.get('tipo', '')}: {et.get('dados', {}).get('resumo', '')} ({et.get('dados', {}).get('tempo', 0)} min)"
        c.drawString(50, y, txt)
        y -= 15
        if y < 100:
            c.showPage()
            y = 800

    total_min = sum(et.get('dados', {}).get('tempo', 0) for et in session['etapas'])
    h, m = divmod(int(total_min), 60)
    c.drawString(50, y - 20, f"Tempo total: {h}:{m:02d}")

    c.showPage()
    c.setFont('Helvetica-Bold', 12)
    c.drawString(50, 800, 'Receita' + (' e Custo' if com_custo else ''))
    c.save()

    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/pdf',
        download_name='processo.pdf'
    )


if __name__ == '__main__':
    app.run(debug=True)
