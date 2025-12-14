from flask import Flask
import os
from dotenv import load_dotenv
from .extensions import db, limiter
from .auth import bp as auth_bp, login_manager

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config.update(
    SESSION_COOKIE_HTTPONLY=False,
    SESSION_COOKIE_SAMESITE="Lax",
    #SESSION_COOKIE_SECURE=True,  # uključi na HTTPS
    )



    db.init_app(app)
    limiter.init_app(app)

    # Models import to register metadata
    from .models import core


    #Blueprints
    #from .blueprints.main import bp as main_bp
    #from .blueprints.sites import bp as sites_bp
    #from .blueprints.meters import bp as meters_bp
    #from .blueprints.uploads import bp as uploads_bp
    #from .blueprints.alarms import bp as alarms_bp
    #from .blueprints.reports import bp as reports_bp
    #from .blueprints.ppa import bp as ppa_bp

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"  # gde da šalje neregistrovane
    #app.register_blueprint(auth_bp)
    #app.register_blueprint(main_bp)
    #app.register_blueprint(sites_bp, url_prefix='/sites')
    #app.register_blueprint(meters_bp, url_prefix='/meters')
    #app.register_blueprint(uploads_bp, url_prefix='/uploads')
    #app.register_blueprint(alarms_bp, url_prefix="/alarms")
    #app.register_blueprint(reports_bp, url_prefix="/reports")
    #app.register_blueprint(ppa_bp, url_prefix="/ppa")

    #------------------------- LOŠA VERZIJA -----------------------------------
    use_prof =os.getenv("USE_PROFESSOR_MODE", "false").lower() == "true"
    if use_prof:
        from .blueprints.auth_prof import bp as auth_bp     # prof login
        from .blueprints.prof_pages import bp as prof_bp    # prof tabele
        #app.register_blueprint(auth_bp, url_prefix="")      # pregazi login
        app.register_blueprint(prof_bp, url_prefix="/prof") # doda /prof i prof/tickets
    else:
        from .auth import bp as auth_bp          # normalni auth
        app.register_blueprint(auth_bp, url_prefix="")

    #Blueprints
    from .blueprints.main import bp as main_bp
    from .blueprints.sites import bp as sites_bp
    from .blueprints.meters import bp as meters_bp
    from .blueprints.uploads import bp as uploads_bp
    from .blueprints.alarms import bp as alarms_bp
    from .blueprints.reports import bp as reports_bp
    from .blueprints.ppa import bp as ppa_bp
    from .blueprints.tickets import bp as tickets_bp


    app.register_blueprint(main_bp)
    app.register_blueprint(sites_bp, url_prefix='/sites')
    app.register_blueprint(meters_bp, url_prefix='/meters')
    app.register_blueprint(uploads_bp, url_prefix='/uploads')
    app.register_blueprint(alarms_bp, url_prefix="/alarms")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(ppa_bp, url_prefix="/ppa")
    app.register_blueprint(tickets_bp, url_prefix="")


    with app.app_context():
        # Test DB connection
        db.session.execute(db.text('SELECT 1'))
    return app