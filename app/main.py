from flask import Flask, jsonify

def create_app():
    app = Flask(__name__)

    @app.get("/")
    def home():
        return "Hello from orderlib!"

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
