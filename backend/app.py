from flask import Flask, jsonify
from flask_cors import CORS
from core.firebase_config import initialize_firebase
from features.risk_detection.routes import risk_bp
from features.deadman_switch.routes import deadman_switch_bp
from features.deadman_switch.service import start_deadman_switch_monitor

def create_app():
    # Initialize Firebase 
    initialize_firebase()
    
    app = Flask(__name__)
    CORS(app) # Enable CORS for Flutter app communication
    
    # Register API blueprints
    app.register_blueprint(risk_bp, url_prefix='/api/v1/risk-detection')
    app.register_blueprint(deadman_switch_bp, url_prefix='/api/v1/deadman-switch')

    start_deadman_switch_monitor()

    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({"status": "HERO-IE Backend is running smoothly."}), 200

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
