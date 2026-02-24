from config import RuntimeConfig
from web import create_app


runtime_config = RuntimeConfig.load()
app = create_app(runtime_config)


if __name__ == "__main__":
    app.run(
        host=runtime_config.server.host,
        port=runtime_config.server.port,
        debug=runtime_config.server.debug,
    )
