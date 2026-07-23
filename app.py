import os
import sys
import json
import io
import base64
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename

# Try normal import first (works on cloud), fall back to _qrcode
try:
    import qrcode as qrcode_maker
    if not hasattr(qrcode_maker, "QRCode"):
        raise ImportError("old qrcode without QRCode")
except (ImportError, Exception):
    import importlib.util
    _qrcode_path = os.path.join(os.path.dirname(__file__), "_qrcode", "__init__.py")
    _spec = importlib.util.spec_from_file_location("qrcode", _qrcode_path, submodule_search_locations=[os.path.join(os.path.dirname(__file__), "_qrcode")])
    qrcode_maker = importlib.util.module_from_spec(_spec)
    sys.modules["qrcode"] = qrcode_maker
    _spec.loader.exec_module(qrcode_maker)
    # Verify _qrcode has QRCode too
    if not hasattr(qrcode_maker, "QRCode"):
        import sys as _sys
        _sys.stderr.write("FATAL: neither system qrcode nor _qrcode has QRCode attribute\n")
        _sys.exit(1)

import database as db

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("editor.html")


@app.route("/view/<project_id>")
def view_project(project_id):
    project = db.get_project(project_id)
    if project is None:
        abort(404)
    is_first = db.mark_scanned(project_id)
    return render_template("viewer.html", project=project, is_first=is_first)


@app.route("/api/create", methods=["POST"])
def api_create():
    data = request.get_json()
    if not data or "pages" not in data or not data["pages"]:
        return jsonify({"error": "at least one page required"}), 400

    project_id = db.create_project(data["pages"], data.get("title", ""))
    # Use PUBLIC_URL env var if set, otherwise use request URL
    base_url = os.environ.get("PUBLIC_URL", "").rstrip("/") or request.url_root.rstrip("/")
    view_url = f"{base_url}/view/{project_id}"

    qr = qrcode_maker.QRCode(box_size=10, border=4)
    qr.add_data(view_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return jsonify({
        "id": project_id,
        "view_url": view_url,
        "qr_png_b64": qr_b64,
    })


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "unsupported format"}), 400
    filename = secure_filename(file.filename)
    import uuid
    unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
    file.save(save_path)
    return jsonify({"url": f"/uploads/{unique_name}"})


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/api/project/<project_id>")
def api_project(project_id):
    project = db.get_project(project_id)
    if project is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(project)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5777))
    app.run(host="0.0.0.0", port=port, debug=False)
