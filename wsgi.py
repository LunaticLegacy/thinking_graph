from config import RuntimeConfig
from web import create_app


app = create_app(RuntimeConfig.load())
