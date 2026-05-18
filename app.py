"""MarginThrive Capital application entry point."""

from factory import initialize_application, run_dev_server

app = initialize_application()

if __name__ == "__main__":
    run_dev_server(app)
