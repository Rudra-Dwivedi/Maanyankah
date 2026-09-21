from flask import Flask, g, render_template

from config import Config
from app.db import register_db
from app.auth_utils import load_logged_in_user


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    register_db(app)

    app.before_request(load_logged_in_user)

    from app.routes.auth import bp as auth_bp
    from app.routes.items import bp as items_bp
    from app.routes.recommend import bp as recommend_bp
    from app.routes.feed import bp as feed_bp
    from app.routes.settings import bp as settings_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.agent import bp as agent_bp
    from app.routes.collections import bp as collections_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(recommend_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(collections_bp)

    @app.route("/")
    def index():
        return render_template("index.html", user=g.user)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    return app
