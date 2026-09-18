import os
import sys
import time
import subprocess
import psutil
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "minuhoster_secret_key_12345")
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Simple Admin Auth (Change these in production or env vars)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Store running processes: bot_id -> subprocess.Popen object
running_bots = {}
bots_db = [
    {
        "id": 1,
        "name": "my bot",
        "script_name": "bot.py",
        "owner": "admin",
        "auto_restart": "YES",
        "env_vars": "0 vars",
        "status": "STOPPED",
        "telegram_name": "RS_NUMBERBOT_BOT",
        "telegram_username": "@RS_NUMBERBOT_BOT",
        "log": "Bot initialized."
    },
    {
        "id": 2,
        "name": "Proxy bot",
        "script_name": "proxy_bot.py",
        "owner": "admin",
        "auto_restart": "YES",
        "env_vars": "0 vars",
        "status": "STOPPED",
        "telegram_name": "RS_IP_SHOPBOT_BD",
        "telegram_username": "@RS_IP_SHOPBOTBD_BOT",
        "log": "Bot initialized."
    }
]

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            error = "ACCESS_DENIED: Invalid Credentials"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Calculate CPU & Memory stats
    try:
        cpu_usage = psutil.cpu_percent(interval=0.1)
        mem_usage = psutil.virtual_memory().percent
    except Exception:
        cpu_usage = 15.3
        mem_usage = 71.8

    running_count = sum(1 for b in bots_db if b['status'] == 'RUNNING')
    
    return render_template('dashboard.html', 
                           bots=bots_db, 
                           total_bots=len(bots_db), 
                           running_bots=running_count,
                           cpu_usage=cpu_usage,
                           mem_usage=mem_usage,
                           username=session.get('username', 'admin'))

@app.route('/api/stats')
def api_stats():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
    except Exception:
        cpu = 15.3
        mem = 71.8
    running_count = sum(1 for b in bots_db if b['status'] == 'RUNNING')
    return jsonify({
        "cpu": cpu,
        "memory": mem,
        "running_bots": running_count,
        "total_bots": len(bots_db)
    })

@app.route('/bot/<int:bot_id>/start', methods=['POST'])
def start_bot(bot_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    for bot in bots_db:
        if bot['id'] == bot_id:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], bot['script_name'])
            # Create a placeholder script if file doesn't exist
            if not os.path.exists(filepath):
                with open(filepath, 'w') as f:
                    f.write('import time\nprint("Bot started...")\nwhile True:\n    time.sleep(5)\n')
            
            if bot_id not in running_bots or running_bots[bot_id].poll() is not None:
                proc = subprocess.Popen([sys.executable, filepath], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                running_bots[bot_id] = proc
                bot['status'] = 'RUNNING'
                bot['log'] += f"\n[{time.strftime('%H:%M:%S')}] Started bot process PID {proc.pid}"
            break
    return redirect(url_for('dashboard'))

@app.route('/bot/<int:bot_id>/stop', methods=['POST'])
def stop_bot(bot_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    for bot in bots_db:
        if bot['id'] == bot_id:
            if bot_id in running_bots:
                proc = running_bots[bot_id]
                proc.terminate()
                del running_bots[bot_id]
            bot['status'] = 'STOPPED'
            bot['log'] += f"\n[{time.strftime('%H:%M:%S')}] Stopped bot process."
            break
    return redirect(url_for('dashboard'))

@app.route('/host-new-bot', methods=['POST'])
def host_new_bot():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    bot_name = request.form.get('bot_name', 'New Bot')
    tg_name = request.form.get('tg_name', 'RS_BOT')
    tg_username = request.form.get('tg_username', '@RS_BOT')
    
    file = request.files.get('bot_file')
    filename = "bot.py"
    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    new_id = max([b['id'] for b in bots_db], default=0) + 1
    bots_db.append({
        "id": new_id,
        "name": bot_name,
        "script_name": filename,
        "owner": session.get('username', 'admin'),
        "auto_restart": "YES",
        "env_vars": "0 vars",
        "status": "STOPPED",
        "telegram_name": tg_name,
        "telegram_username": tg_username,
        "log": "Bot hosted successfully."
    })
    flash("New bot hosted successfully!", "success")
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
