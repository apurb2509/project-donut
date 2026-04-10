from flask import Flask, jsonify
from flask_cors import CORS
from core.firebase_config import initialize_firebase
from features.risk_detection.routes import risk_bp

def create_app():
    # Initialize Firebase 
    initialize_firebase()
    
    app = Flask(__name__)
    CORS(app) # Enable CORS for Flutter app communication
    
    # Register API blueprints
    app.register_blueprint(risk_bp, url_prefix='/api/v1/risk-detection')

    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({"status": "HERO-IE Backend is running smoothly."}), 200

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
