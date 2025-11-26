# # app.py
# import base64, io, os, subprocess, hashlib, json
# from flask import Flask, request, send_file, render_template_string
# from PIL import Image
# import matplotlib
# matplotlib.use('Agg')   # headless backend
# import matplotlib.pyplot as plt
# import qrcode
# from jinja2 import Template

# app = Flask(__name__)

# # ---------- Helpers ----------
# def bytes_to_data_uri(b: bytes, mime: str):
#     return f"data:{mime};base64," + base64.b64encode(b).decode()

# def fig_to_png_bytes(fig, dpi=150):
#     buf = io.BytesIO()
#     fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi)
#     plt.close(fig)
#     buf.seek(0)
#     return buf.getvalue()

# def generate_pie(values, labels, px=(480,360), dpi=150):
#     fig = plt.figure(figsize=(px[0]/dpi, px[1]/dpi), dpi=dpi)
#     ax = fig.add_subplot(111)
#     ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90, textprops=dict(color='white'))
#     ax.axis('equal')
#     img_bytes = fig_to_png_bytes(fig, dpi=dpi)
#     return bytes_to_data_uri(img_bytes, "image/png")

# def generate_bar(categories, values, px=(640,360), dpi=150):
#     fig = plt.figure(figsize=(px[0]/dpi, px[1]/dpi), dpi=dpi)
#     ax = fig.add_subplot(111)
#     ax.bar(categories, values)
#     ax.set_xlabel('Category')
#     ax.set_ylabel('Value')
#     ax.grid(axis='y', linestyle='--', alpha=0.4)
#     img_bytes = fig_to_png_bytes(fig, dpi=dpi)
#     return bytes_to_data_uri(img_bytes, "image/png")

# def generate_qr(data: str, px=300):
#     qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
#     qr.add_data(data); qr.make(fit=True)
#     img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
#     img = img.resize((px,px), Image.LANCZOS)
#     buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True)
#     return bytes_to_data_uri(buf.getvalue(), "image/png")

# def load_logo(path):
#     if not path:
#         return "", ""
#     ext = os.path.splitext(path)[1].lower()
#     if ext == '.svg':
#         with open(path, 'r', encoding='utf-8') as f:
#             return f.read(), ""
#     else:
#         with open(path, 'rb') as f:
#             b = f.read()
#         mime = "image/png" if ext==".png" else "image/jpeg"
#         return "", bytes_to_data_uri(b, mime)

# # ---------- HTML template (self-contained) ----------
# TEMPLATE = """
# <!doctype html>
# <html>
# <head>
# <meta charset="utf-8"/>
# <style>
#   body{font-family:Arial, sans-serif; color:#222; margin:24mm;}
#   .header{display:flex;align-items:center;gap:12px}
#   .logo{width:120px}
#   .charts{display:flex;gap:8px;margin-top:8px}
#   img{max-width:100%;height:auto;display:block}
# </style>
# </head>
# <body>
#   <div class="header">
#     {% if logo_svg %}
#       <div class="logo">{{ logo_svg | safe }}</div>
#     {% elif logo_data %}
#       <img class="logo" src="{{ logo_data }}" />
#     {% endif %}
#     <div>
#       <h1>{{ title }}</h1>
#       <div>{{ subtitle }}</div>
#     </div>
#   </div>

#   <div class="charts">
#     <div><h3>Pie</h3><img src="{{ pie }}" width="{{ pie_w }}" height="{{ pie_h }}"/></div>
#     <div><h3>Bar</h3><img src="{{ bar }}" width="{{ bar_w }}" height="{{ bar_h }}"/></div>
#   </div>

#   <div style="margin-top:12px;">
#     <h3>QR</h3>
#     <img src="{{ qr }}" width="150" height="150"/>
#   </div>

#   <div style="margin-top:12px;">Notes: {{ notes }}</div>
# </body>
# </html>
# """

# # ---------- Routes ----------
# @app.route('/render_html', methods=['POST'])
# def render_html():
#     """
#     Accepts JSON with fields:
#     {
#       title, subtitle, pie_values[], pie_labels[], bar_categories[], bar_values[],
#       qr_text, logo_path (server-side path or empty), notes
#     }
#     Returns generated HTML string.
#     """
#     payload = request.get_json(force=True)
#     # Generate assets
#     pie = generate_pie(payload.get('pie_values', [50,30,20]), payload.get('pie_labels', ['A','B','C']))
#     bar = generate_bar(payload.get('bar_categories', ['Jan','Feb']), payload.get('bar_values', [10,20]))
#     qr = generate_qr(payload.get('qr_text', 'https://example.com'))
#     svg, raster = load_logo(payload.get('logo_path', ''))
#     html = Template(TEMPLATE).render(
#         title=payload.get('title','Report'),
#         subtitle=payload.get('subtitle',''),
#         pie=pie, bar=bar, qr=qr,
#         logo_svg=svg, logo_data=raster,
#         pie_w=payload.get('pie_size_px',480), pie_h=payload.get('pie_size_px_h',360),
#         bar_w=payload.get('bar_size_px',640), bar_h=payload.get('bar_size_px_h',360),
#         notes=payload.get('notes','')
#     )
#     return html, 200, {'Content-Type':'text/html; charset=utf-8'}

# @app.route('/render_pdf', methods=['POST'])
# def render_pdf():
#     """
#     Accepts same JSON; returns PDF bytes. Requires wkhtmltopdf installed and in PATH.
#     """
#     payload = request.get_json(force=True)
#     html = render_html_internal(payload)
#     tmp_html = '/tmp/report.html'
#     tmp_pdf = '/tmp/report.pdf'
#     with open(tmp_html, 'w', encoding='utf-8') as f:
#         f.write(html)
#     # wkhtmltopdf flags recommended
#     cmd = ["wkhtmltopdf", "--enable-local-file-access", "--enable-javascript",
#            "--no-stop-slow-scripts", "--javascript-delay", "200",
#            "--image-quality", "94", "--dpi", "150", tmp_html, tmp_pdf]
#     subprocess.run(cmd, check=True)
#     return send_file(tmp_pdf, mimetype='application/pdf', as_attachment=True, download_name='report.pdf')

# def render_html_internal(payload):
#     pie = generate_pie(payload.get('pie_values', [50,30,20]), payload.get('pie_labels', ['A','B','C']))
#     bar = generate_bar(payload.get('bar_categories', ['Jan','Feb']), payload.get('bar_values', [10,20]))
#     qr = generate_qr(payload.get('qr_text', 'https://example.com'))
#     svg, raster = load_logo(payload.get('logo_path', ''))
#     html = Template(TEMPLATE).render(
#         title=payload.get('title','Report'),
#         subtitle=payload.get('subtitle',''),
#         pie=pie, bar=bar, qr=qr,
#         logo_svg=svg, logo_data=raster,
#         pie_w=payload.get('pie_size_px',480), pie_h=payload.get('pie_size_px_h',360),
#         bar_w=payload.get('bar_size_px',640), bar_h=payload.get('bar_size_px_h',360),
#         notes=payload.get('notes','')
#     )
#     return html

# if __name__ == "__main__":
#     app.run(host='0.0.0.0', port=5000, debug=True)
