from config import RuntimeConfig
from web import create_app


def main() -> None:
    """Start the development server after validating runtime configuration."""
    runtime_config = RuntimeConfig.load()
    app = create_app(runtime_config)
    app.run(
        host=runtime_config.server.host,
        port=runtime_config.server.port,
        debug=runtime_config.server.debug,
    )


if __name__ == "__main__":
    main()
