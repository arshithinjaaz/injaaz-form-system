import os
from dotenv import load_dotenv

def load_config(app):
    # load .env from repo root
    load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))
    app.config['CLOUDINARY_URL'] = os.environ.get('CLOUDINARY_URL')
    app.config['REDIS_URL'] = os.environ.get('REDIS_URL')
    app.config['RQ_DEFAULT_QUEUE'] = os.environ.get('RQ_DEFAULT_QUEUE', 'default')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', app.config.get('SECRET_KEY'))