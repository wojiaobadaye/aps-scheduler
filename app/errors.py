from flask import jsonify


class AppError(Exception):
    """业务逻辑异常，携带 message 和 status_code，由 errorhandler 统一捕获。"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def register_error_handlers(app):
    """在 Flask app 上注册统一错误处理器。"""

    @app.errorhandler(AppError)
    def handle_app_error(error):
        return jsonify({"error": error.message}), error.status_code

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return jsonify({"error": "method not allowed"}), 405

    @app.errorhandler(500)
    def handle_internal_error(error):
        return jsonify({"error": "internal server error"}), 500
