import os
import logging
import json
import datetime
import jwt
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from dotenv import load_dotenv
from functools import wraps

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('web_dashboard')

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key_for_development")

# Configure database
# Use either the database in the instance folder or the one in the root directory
if os.path.exists("web_dashboard.db"):
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///web_dashboard.db"
    logger.info("Using SQLite database (web_dashboard.db) in root directory")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/web_dashboard.db"
    logger.info("Using SQLite database in instance directory")

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
from models import db
db.init_app(app)

# Create tables if they don't exist
with app.app_context():
    import models
    db.create_all()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.args.get('token')
        
        if not token:
            return jsonify({'error': 'Token is required!'}), 401
            
        user_token = models.UserToken.query.filter_by(token=token).first()
        
        if not user_token:
            return jsonify({'error': 'Invalid token!'}), 401

        user_token.last_used = datetime.datetime.utcnow()
        db.session.commit()

        kwargs['discord_user_id'] = user_token.discord_user_id
        kwargs['username'] = user_token.username
        
        return f(*args, **kwargs)
        
    return decorated

@app.route('/')
def index():
    """Home page showing bot information."""
    with open("logs/bot.log", "r") as f:
        log_content = f.read().splitlines()[-20:] if os.path.exists("logs/bot.log") else []
    
    bot_status = {
        "name": "Simple Discord Bot",
        "is_running": os.path.exists("logs/bot.log") and len(log_content) > 0,
        "logged_in": any("has connected to Discord" in line for line in log_content) if log_content else False,
        "server_count": next((line.split("Bot is in ")[1].split(" guild")[0] 
                             for line in log_content if "Bot is in " in line), "0") if log_content else "0"
    }
    
    return render_template('index.html', bot_status=bot_status, logs=log_content)

@app.route('/commands')
def commands():
    """Page displaying available bot commands."""

    return render_template('commands.html')

@app.route('/stats')
def stats():
    """Page displaying bot statistics."""

    stats_data = {
        "server_count": 0,
        "uptime": "0 days, 0 hours, 0 minutes"
    }

    with open("logs/bot.log", "r") as f:
        log_content = f.read().splitlines() if os.path.exists("logs/bot.log") else []

    for line in log_content:
        if "Bot is in " in line:
            try:
                stats_data["server_count"] = int(line.split("Bot is in ")[1].split(" guild")[0])
            except (ValueError, IndexError):
                pass
    
    return render_template('stats.html', stats=stats_data)

@app.route('/leveling', methods=['GET', 'POST'])
def leveling_page():
    """Page for viewing and managing leveling stats with a web interface."""
    error = None
    success = None
    authenticated = False
    username = None
    discord_user_id = None
    user_stats = {}
    active_boosts = []
    owned_perks = []
    settings = {}
    
    if request.method == 'POST' and 'token' in request.form:
        # Process token submission
        token = request.form['token']
        user_token = models.UserToken.query.filter_by(token=token).first()
        
        if user_token:
            session['token'] = token
            return redirect(url_for('leveling_page'))
        else:
            error = "Invalid token. Please try again or generate a new token."
    
    if 'token' in session:
        token = session['token']
        user_token = models.UserToken.query.filter_by(token=token).first()
        
        if user_token:
            authenticated = True
            discord_user_id = user_token.discord_user_id
            username = user_token.username
            
            # Get user's leveling stats
            from database import Database
            from shop import ShopCog  # For perks data
            import time
            
            db_instance = Database()
            
            # Get user data
            user_data = db_instance.get_or_create_user(discord_user_id, username)
            settings = db_instance.get_settings()
            
            if user_data:
                # Calculate XP progress for current level
                current_level = user_data['level']
                current_xp = user_data['xp']
                
                # Calculate XP required for next level using the formula from leveling.py
                xp_required = settings['base_xp_required'] * (current_level ** 1.5)
                xp_percent = int((current_xp / xp_required) * 100) if xp_required > 0 else 0
                if xp_percent > 100:
                    xp_percent = 100
                
                # Format user stats
                user_stats = {
                    'level': current_level,
                    'xp': current_xp,
                    'xp_required': int(xp_required),
                    'xp_percent': xp_percent,
                    'coins': user_data['coins'],
                    'prestige': user_data['prestige'],
                    'message_count': user_data['message_count'],
                    'voice_minutes': user_data['voice_minutes'],
                    'streaming_minutes': user_data['streaming_minutes'],
                    'images_shared': user_data['images_shared']
                }
                
                # Get user's perks and boosts
                try:
                    # Create a temporary ShopCog to access user perks
                    shop = ShopCog(None)
                    user_perks = shop.load_user_perks(discord_user_id)
                    
                    # Process active boosts
                    current_time = int(time.time())
                    
                    for boost in user_perks.get('active_boosts', []):
                        if boost['end_time'] > current_time:
                            # Calculate time left
                            time_left_seconds = boost['end_time'] - current_time
                            if time_left_seconds < 3600:
                                time_left = f"{time_left_seconds // 60} minutes"
                            elif time_left_seconds < 86400:
                                time_left = f"{time_left_seconds // 3600} hours"
                            else:
                                time_left = f"{time_left_seconds // 86400} days"
                            
                            # Format boost info
                            boost_info = {
                                'name': boost['item_name'],
                                'multiplier': boost['value'],
                                'time_left': time_left
                            }
                            active_boosts.append(boost_info)
                    
                    # Process owned perks
                    from shop import SHOP_ITEMS
                    
                    for item_name in user_perks.get('owned_items', []):
                        if item_name in SHOP_ITEMS:
                            item_data = SHOP_ITEMS[item_name]
                            
                            # Only show permanent perks in the owned perks section
                            if item_data.get('category') == 'perks':
                                perk_info = {
                                    'name': item_name,
                                    'description': item_data.get('description', ''),
                                    'emoji': item_data.get('emoji', '')
                                }
                                owned_perks.append(perk_info)
                    
                except Exception as e:
                    logger.error(f"Error loading perks for user {discord_user_id}: {e}")
    
    return render_template(
        'leveling.html', 
        authenticated=authenticated,
        username=username,
        user_stats=user_stats,
        active_boosts=active_boosts,
        owned_perks=owned_perks,
        settings=settings,
        error=error,
        success=success
    )

@app.route('/api/leveling', methods=['GET'])
@token_required
def get_leveling_stats(discord_user_id, username):
    """Get leveling stats for a user."""
    from database import Database
    from shop import ShopCog
    import time
    
    db = Database()
    user_data = db.get_or_create_user(discord_user_id, username)
    settings = db.get_settings()
    
    if not user_data:
        return jsonify({
            "error": "Could not retrieve user data"
        }), 400
    
    # Calculate XP required for next level
    current_level = user_data['level']
    current_xp = user_data['xp']
    xp_required = settings['base_xp_required'] * (current_level ** 1.5)
    xp_percent = int((current_xp / xp_required) * 100) if xp_required > 0 else 0
    
    # Format response
    response = {
        "user": {
            "id": user_data['user_id'],
            "username": user_data['username'],
            "level": current_level,
            "xp": current_xp,
            "xp_required": int(xp_required),
            "xp_percent": xp_percent,
            "coins": user_data['coins'],
            "prestige": user_data['prestige'],
            "message_count": user_data['message_count'],
            "voice_minutes": user_data['voice_minutes'],
            "streaming_minutes": user_data['streaming_minutes'],
            "images_shared": user_data['images_shared']
        },
        "settings": {
            "coins_per_level": settings['coins_per_level'],
            "levels_per_prestige": settings['levels_per_prestige'],
            "max_prestige": settings['max_prestige'],
            "prestige_coins": settings['prestige_coins'],
            "prestige_boost_multiplier": settings['prestige_boost_multiplier'],
            "prestige_boost_duration": settings['prestige_boost_duration']
        }
    }
    
    # Add boosts information if available
    try:
        shop = ShopCog(None)
        user_perks = shop.load_user_perks(discord_user_id)
        
        # Active boosts
        active_boosts = []
        current_time = int(time.time())
        
        for boost in user_perks.get('active_boosts', []):
            if boost['end_time'] > current_time:
                time_left_seconds = boost['end_time'] - current_time
                active_boosts.append({
                    "name": boost['item_name'],
                    "stat": boost['stat'],
                    "multiplier": boost['value'],
                    "end_time": boost['end_time'],
                    "time_left_seconds": time_left_seconds
                })
        
        # Permanent boosts
        permanent_boosts = user_perks.get('permanent_boosts', {})
        
        # Add to response
        response["boosts"] = {
            "active": active_boosts,
            "permanent": permanent_boosts
        }
        
        # Owned perks
        from shop import SHOP_ITEMS
        owned_items = []
        
        for item_name in user_perks.get('owned_items', []):
            if item_name in SHOP_ITEMS:
                item_data = SHOP_ITEMS[item_name]
                owned_items.append({
                    "name": item_name,
                    "category": item_data.get('category', ''),
                    "description": item_data.get('description', ''),
                    "emoji": item_data.get('emoji', '')
                })
        
        response["owned_items"] = owned_items if owned_items else []
        
    except Exception as e:
        logger.error(f"Error loading perks data for user {discord_user_id}: {e}")
    
    return jsonify(response)

@app.route('/api/investments', methods=['GET'])
@token_required
def get_investments(discord_user_id, username):
    """Get all investments for a user."""
    from investment_system_new import InvestmentManager
    from database import Database
    
    db = Database()
    investment_manager = InvestmentManager(None)
    investment_manager.load_data()
    
    user_properties = investment_manager.get_user_properties(str(discord_user_id))
    
    investments = []
    for investment in user_properties:
        property_details = investment_manager.get_property_details(investment.property_name)
        if property_details:
            investments.append({
                "name": investment.property_name,
                "maintenance": investment.maintenance,
                "accumulated": investment.accumulated_income,
                "purchase_time": investment.purchase_time.isoformat(),
                "risk_event": investment.risk_event,
                "repair_cost": property_details["maintenance_cost"] * 2 if investment.risk_event else 0,
                "hourly_income": property_details["hourly_income"],
                "max_accumulation": property_details["max_accumulation"]
            })
    
    return jsonify({
        "investments": investments
    })

@app.route('/api/collect/<investment_name>', methods=['POST'])
@token_required
def collect_investment(discord_user_id, username, investment_name):
    """Collect income from an investment."""
    from investment_system_new import InvestmentManager
    from database import Database
    
    db = Database()
    investment_manager = InvestmentManager(None)
    investment_manager.load_data()
    
    success, message, collected = investment_manager.collect_income(str(discord_user_id), investment_name)
    
    if success:
        return jsonify({
            "success": True,
            "collected": collected,
            "message": message
        })
    
    return jsonify({
        "success": False,
        "message": message
    }), 400

@app.route('/api/maintain/<investment_name>', methods=['POST'])
@token_required
def maintain_investment(discord_user_id, username, investment_name):
    """Perform maintenance on an investment."""
    from investment_system_new import InvestmentManager
    from database import Database
    
    db = Database()
    investment_manager = InvestmentManager(None)
    investment_manager.load_data()
    
    success, message = investment_manager.maintain_property(str(discord_user_id), investment_name)
    
    if success:
        return jsonify({
            "success": True,
            "message": message
        })
    
    return jsonify({
        "success": False,
        "message": message
    }), 400

@app.route('/api/repair/<investment_name>', methods=['POST'])
@token_required
def repair_investment(discord_user_id, username, investment_name):
    """Repair an investment after a risk event."""
    from investment_system_new import InvestmentManager
    from database import Database
    
    db = Database()
    investment_manager = InvestmentManager(None)
    investment_manager.load_data()
    
    success, message = investment_manager.repair_property(str(discord_user_id), investment_name)
    
    if success:
        return jsonify({
            "success": True,
            "message": message
        })
    
    return jsonify({
        "success": False,
        "message": message
    }), 400

@app.route('/investments', methods=['GET', 'POST'])
def investments_page():
    """Page for managing investments with a web interface."""
    error = None
    success = None
    authenticated = False
    username = None
    discord_user_id = None
    investments = []
    coins = 0
    
    if request.method == 'POST' and 'token' in request.form:
        # Process token submission
        token = request.form['token']
        user_token = models.UserToken.query.filter_by(token=token).first()
        
        if user_token:
            session['token'] = token
            return redirect(url_for('investments_page'))
        else:
            error = "Invalid token. Please try again or generate a new token."
    
    if 'token' in session:
        token = session['token']
        user_token = models.UserToken.query.filter_by(token=token).first()
        
        if user_token:
            authenticated = True
            discord_user_id = user_token.discord_user_id
            username = user_token.username
            
            from database import Database
            from investment_system_new import InvestmentManager
            
            db_instance = Database()
            investment_manager = InvestmentManager(None)
            investment_manager.load_data()
            
            user_data = db_instance.get_user(discord_user_id)
            if user_data:
                coins = user_data.get('coins', 0)
                
            user_properties = investment_manager.get_user_properties(str(discord_user_id))
            
            for investment in user_properties:
                property_details = investment_manager.get_property_details(investment.property_name)
                if property_details:
                    investments.append({
                        "name": investment.property_name,
                        "maintenance": investment.maintenance,
                        "accumulated": investment.accumulated_income,
                        "purchase_time": investment.purchase_time,
                        "risk_event": investment.risk_event,
                        "repair_cost": property_details["maintenance_cost"] * 2 if investment.risk_event else 0,
                        "hourly_return": property_details["hourly_income"],
                        "max_holding": property_details["max_accumulation"]
                    })
    
    system_disabled = False
    
    return render_template(
        'investments.html', 
        authenticated=authenticated,
        username=username,
        investments=investments,
        coins=coins,
        error=error,
        success=success,
        system_disabled=system_disabled
    )

@app.route('/collect_investment', methods=['POST'])
def collect_investment_web():
    """Web endpoint to collect investment income."""
    investment_name = request.form.get('investment_name')
    
    if not investment_name:
        flash("No investment specified.", "danger")
        return redirect(url_for('investments_page'))
    
    if 'token' not in session:
        flash("You need to be logged in.", "danger")
        return redirect(url_for('investments_page'))
    
    token = session['token']
    user_token = models.UserToken.query.filter_by(token=token).first()
    
    if not user_token:
        flash("Invalid session. Please log in again.", "danger")
        return redirect(url_for('investments_page'))
    
    discord_user_id = user_token.discord_user_id
    
    from investment_system_new import InvestmentManager
    from database import Database
    
    db = Database()
    investment_manager = InvestmentManager(None)
    investment_manager.load_data()
    
    success, message, collected = investment_manager.collect_income(str(discord_user_id), investment_name)
    
    if success:
        flash(f"Collected {collected} coins from {investment_name}!", "success")
    else:
        flash(message, "warning")
    
    return redirect(url_for('investments_page'))

@app.route('/maintain_investment', methods=['POST'])
def maintain_investment_web():
    """Web endpoint to maintain an investment."""
    investment_name = request.form.get('investment_name')
    
    if not investment_name:
        flash("No investment specified.", "danger")
        return redirect(url_for('investments_page'))
    
    if 'token' not in session:
        flash("You need to be logged in.", "danger")
        return redirect(url_for('investments_page'))
    
    token = session['token']
    user_token = models.UserToken.query.filter_by(token=token).first()
    
    if not user_token:
        flash("Invalid session. Please log in again.", "danger")
        return redirect(url_for('investments_page'))
    
    discord_user_id = user_token.discord_user_id
    
    from investment_system_new import InvestmentManager
    from database import Database
    
    db = Database()
    investment_manager = InvestmentManager(None)
    investment_manager.load_data()
    
    success, message = investment_manager.maintain_property(str(discord_user_id), investment_name)
    
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    
    return redirect(url_for('investments_page'))

@app.route('/repair_investment', methods=['POST'])
def repair_investment_web():
    """Web endpoint to repair an investment."""
    investment_name = request.form.get('investment_name')
    
    if not investment_name:
        flash("No investment specified.", "danger")
        return redirect(url_for('investments_page'))
    
    if 'token' not in session:
        flash("You need to be logged in.", "danger")
        return redirect(url_for('investments_page'))
    
    token = session['token']
    user_token = models.UserToken.query.filter_by(token=token).first()
    
    if not user_token:
        flash("Invalid session. Please log in again.", "danger")
        return redirect(url_for('investments_page'))
    
    discord_user_id = user_token.discord_user_id
    
    from investment_system_new import InvestmentManager
    from database import Database
    
    db = Database()
    investment_manager = InvestmentManager(None)
    investment_manager.load_data()
    
    success, message = investment_manager.repair_property(str(discord_user_id), investment_name)
    
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    
    return redirect(url_for('investments_page'))

@app.route('/logout', methods=['POST'])
def logout():
    """Log out and clear session."""
    session.pop('token', None)
    session.pop('discord_user_id', None)
    session.pop('username', None)
    
    # Redirect to the referring page or to the leveling page by default
    referrer = request.referrer
    if referrer and ('/leveling' in referrer or '/investments' in referrer):
        return redirect(referrer)
    return redirect(url_for('leveling_page'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)