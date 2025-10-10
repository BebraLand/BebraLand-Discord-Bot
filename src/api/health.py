import asyncio
import threading
from datetime import datetime
from flask import Flask, jsonify
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

class HealthAPI:
    def __init__(self, bot, port=8080):
        self.bot = bot
        self.port = port
        self.app = Flask(__name__)
        self.start_time = datetime.utcnow()
        self.setup_routes()
        
    def setup_routes(self):
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint for monitoring services like Uptime Robot"""
            try:
                # Check if bot is ready and connected
                is_ready = self.bot.is_ready()
                is_closed = self.bot.is_closed()
                
                # Calculate uptime
                uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
                
                # Get basic bot stats
                guild_count = len(self.bot.guilds) if hasattr(self.bot, 'guilds') else 0
                user_count = sum(guild.member_count for guild in self.bot.guilds) if hasattr(self.bot, 'guilds') else 0
                
                status = "healthy" if is_ready and not is_closed else "unhealthy"
                
                response = {
                    "status": status,
                    "timestamp": datetime.utcnow().isoformat(),
                    "uptime_seconds": uptime_seconds,
                    "bot": {
                        "is_ready": is_ready,
                        "is_closed": is_closed,
                        "guild_count": guild_count,
                        "user_count": user_count,
                        "latency": round(self.bot.latency * 1000, 2) if hasattr(self.bot, 'latency') else None
                    }
                }
                
                return jsonify(response), 200 if status == "healthy" else 503
                
            except Exception as e:
                logger.exception("Health check failed", exc_info=e)
                return jsonify({
                    "status": "error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                }), 500
        
        @self.app.route('/ping', methods=['GET'])
        def ping():
            """Simple ping endpoint"""
            return jsonify({"message": "pong", "timestamp": datetime.utcnow().isoformat()}), 200
            
        @self.app.route('/', methods=['GET'])
        def root():
            """Root endpoint with basic info"""
            return jsonify({
                "service": "BebraLand Discord Bot",
                "endpoints": ["/health", "/ping"],
                "timestamp": datetime.utcnow().isoformat()
            }), 200
    
    def run_server(self):
        """Run the Flask server in a separate thread"""
        try:
            logger.info(f"Starting health API server on port {self.port}")
            self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)
        except Exception as e:
            logger.exception("Failed to start health API server", exc_info=e)
    
    def start(self):
        """Start the health API server in a background thread"""
        server_thread = threading.Thread(target=self.run_server, daemon=True)
        server_thread.start()
        logger.info(f"Health API server started on http://0.0.0.0:{self.port}")
        return server_thread