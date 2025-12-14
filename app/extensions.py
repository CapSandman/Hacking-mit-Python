from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()

# rate limiting – po IP adresi
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[]  # za sada bez globalnih limita, samo po rutama
)

# Special module for extensions to avoid circular imports