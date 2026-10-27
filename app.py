import os
from flask import Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge
from config import Config
from routes.exports import exports_bp
from routes.pages import pages_bp
from routes.processing import processing_bp
from routes.projects import projects_bp
from routes.upload import upload_bp


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["PROJECTS_FOLDER"], exist_ok=True)
    os.makedirs(app.config["FONTS_FOLDER"], exist_ok=True)

    app.register_blueprint(pages_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(processing_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(exports_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if request.path.startswith("/static/js/") or request.path.startswith("/static/css/"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    @app.errorhandler(RequestEntityTooLarge)
    @app.errorhandler(413)
    def handle_file_too_large(exc):
        max_mb = round(app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024), 1)
        return (
            jsonify(
                {
                    "error": f"Uploaded file exceeds maximum allowed size ({max_mb} MB)."
                }
            ),
            413,
        )

    @app.errorhandler(400)
    def handle_bad_request(exc):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Bad request."}), 400
        return "Bad Request", 400

    @app.errorhandler(404)
    def handle_not_found(exc):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Endpoint not found."}), 404
        return "Not Found", 404

    @app.errorhandler(500)
    def handle_server_error(exc):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error."}), 500
        return "Internal Server Error", 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="127.0.0.1",
        port=port,
        debug=Config.DEBUG,
        use_reloader=(Config.FLASK_ENV != "production"),
    )
