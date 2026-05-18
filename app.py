"""MarginThrive Capital application entry point."""

from factory import create_app, run_dev_server

app = create_app()

if __name__ == "__main__":
    run_dev_server()
