from flask import Flask, request, jsonify, session, redirect, url_for, render_template, flash
import pandas as pd
import yfinance as yf
import sqlite3
import json
import os
from flask_cors import CORS
from flask_mail import Mail, Message

app = Flask(__name__)
app.static_folder = 'static'
app.secret_key = 'supersecretkey'  # Necessary for session management
app.config['CORS_HEADERS'] = 'Content-Type'
CORS(app)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'oo7dwaynerock@gmail.com'  # Update with your Gmail username
app.config['MAIL_PASSWORD'] = 'ignt udiu ypac kvzb'         # Update with your Gmail password
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)
# Database connection
def get_db_connection():
    conn = sqlite3.connect('database.db')  # Ensure persistent storage path
    conn.row_factory = sqlite3.Row
    return conn

# Create tables if they do not exist
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        name TEXT,
        password TEXT,
        symbol TEXT,
        volumes TEXT,
        traded_prices TEXT,
        alert_sent INTEGER DEFAULT 0,
        alert_sent_negative INTEGER DEFAULT 0,
        lower_threshold REAL DEFAULT 0,
        upper_threshold REAL DEFAULT 10,
    email_notifications INTEGER DEFAULT 0 
    )
''')
    conn.commit()
    conn.close()

    
# Call create_tables to ensure the table is created only if it does not exist
create_tables()

def fetch_real_time_price(symbol_name):
    stock = yf.Ticker(symbol_name)
    price = stock.history(period='1d')['Close'][0]
    return price

def update_prices(df):
    prices = []
    for stock in df['Symbol Name']:
        try:
            price = fetch_real_time_price(stock)
            prices.append(price)
        except Exception as e:
            print(f"Error fetching price for {stock}: {e}")
            prices.append(0)
    df['Current Trading Price'] = prices
    df['Invested Total'] = df['Total Volume Purchased'] * df['Traded Price']
    df['Total Return'] = df['Current Trading Price'] * df['Total Volume Purchased']
    df['Profit/Loss'] = df['Total Return'] - df['Invested Total']
    df['Invested Return%'] = ((df['Total Return'] - df['Invested Total']) / df['Invested Total']) * 100
    return df

def calculate_totals(df, lower_threshold, upper_threshold):
    invested_total = df['Invested Total'].sum()
    total_return = df['Total Return'].sum()
    total_profit_loss = df['Profit/Loss'].sum()
    total_profit_percent = ((total_return - invested_total) / invested_total) * 100
    
    return invested_total.round(2), total_return.round(2), total_profit_loss.round(2), total_profit_percent.round(2)

def send_email(username, subject, message):
    msg = Message(subject, sender='your_email@gmail.com', recipients=[username])
    msg.body = message
    try:
        mail.send(msg)
        print(f"Email sent to {username} with message: {message}")
        return True
    except Exception as e:
        print(f"Failed to send email to {username}: {str(e)}")
        return False

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form.get('name')
        
        # Ensure these variables are set with default values
        lower_threshold = 0  # Example default lower threshold
        upper_threshold = 10  # Example default upper threshold
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        
        if user_data:
            flash('Email already exists. Please use a different email.')
            conn.close()
        else:
            cursor.execute('INSERT INTO users (username, password, name, symbol, volumes, traded_prices, alert_sent, alert_sent_negative, lower_threshold, upper_threshold,email_notifications) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)',
                           (username, password, name, '[]', '[]', '[]', 0, 0, lower_threshold, upper_threshold,0))
            conn.commit()
            conn.close()
            flash('Account created successfully. Please log in.')
            return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        
        if user:
            session['user'] = username
            conn.close()
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password')
            conn.close()

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetching user data from the database
    cursor.execute('SELECT name, symbol, lower_threshold, upper_threshold FROM users WHERE username = ?', (user,))
    user_data = cursor.fetchone()

    if user_data:
        name = user_data['name']
        symbol = json.loads(user_data['symbol'])
        
        # Retrieve thresholds and apply defaults if necessary
        lower_threshold = user_data['lower_threshold'] if user_data['lower_threshold'] is not None else 0
        upper_threshold = user_data['upper_threshold'] if user_data['upper_threshold'] is not None else 10

        return render_template('dashboard.html', symbol=symbol, name=name, lower_threshold=lower_threshold, upper_threshold=upper_threshold)
    else:
        flash('User data not found.')
        return redirect(url_for('login'))
from flask import request, jsonify, redirect, url_for, session
import pandas as pd
import json

# Assuming you have your existing functions like get_db_connection(), send_email(), update_prices(), calculate_totals() defined elsewhere.

@app.route('/update', methods=['GET', 'POST'])
def update_data():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (user,))
    user_data = cursor.fetchone()

    if not user_data:
        return jsonify({"error": "User data not found"}), 404

    # Handling POST request for updating email notifications
    if request.method == 'POST' and 'email_notifications' in request.json:
        email_notifications = request.json['email_notifications']
        cursor.execute('UPDATE users SET email_notifications = ? WHERE username = ?', (email_notifications, user))
        conn.commit()

        return jsonify({"message": "Email notifications preference updated successfully"}), 200

    # Fetching user's data for dashboard display
    name = user_data['name']
    lower_threshold = user_data['lower_threshold']
    upper_threshold = user_data['upper_threshold']
    symbol = json.loads(user_data['symbol'])
    volumes = json.loads(user_data['volumes'])
    traded_prices = json.loads(user_data['traded_prices'])

    if symbol:
        df = pd.DataFrame({
            "Symbol Name": symbol,
            "Total Volume Purchased": volumes,
            "Traded Price": traded_prices
        })

        df = update_prices(df)
        invested_total, total_return, total_profit_loss, total_profit_percent = calculate_totals(df, lower_threshold, upper_threshold)
        df = df.round(2)

        # Check and send alerts based on thresholds
        if user_data['alert_sent'] == 0 and total_profit_percent > upper_threshold and user_data['email_notifications'] == 1:
            send_email(user, "Portfolio Alert", f"Congratulations {name}!! Your portfolio has exceeded {upper_threshold}% profit.")
            cursor.execute('UPDATE users SET alert_sent = 1 WHERE username = ?', (user,))
            conn.commit()

        if user_data['alert_sent'] == 1 and total_profit_percent < upper_threshold:
            cursor.execute('UPDATE users SET alert_sent = 0 WHERE username = ?', (user,))
            conn.commit()

        if user_data['alert_sent_negative'] == 0 and total_profit_percent < lower_threshold and user_data['email_notifications'] == 1:
            send_email(user, "Portfolio Alert", f"Alert {name}!! Your portfolio has gone below {lower_threshold}% profit.")
            cursor.execute('UPDATE users SET alert_sent_negative = 1 WHERE username = ?', (user,))
            conn.commit()

        if user_data['alert_sent_negative'] == 1 and total_profit_percent >= lower_threshold:
            cursor.execute('UPDATE users SET alert_sent_negative = 0 WHERE username = ?', (user,))
            conn.commit()

        conn.close()

        return jsonify({
            "data": df.to_dict(orient='records'),
            "invested_total": invested_total,
            "total_return": total_return,
            "total_profit_loss": total_profit_loss,
            "total_profit_percent": total_profit_percent,
            "lower_threshold": lower_threshold,
            "upper_threshold": upper_threshold
        })

    else:
        conn.close()
        return jsonify({"message": "Your portfolio is currently empty."}), 200

@app.route('/add_stock', methods=['POST'])
def add_stock():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (user,))
    user_data = cursor.fetchone()
    
    if not user_data:
        return jsonify({"error": "User data not found"}), 404

    data = request.json
    new_symbol = data.get('symbol_name')
    new_volume = int(data.get('stock_volume'))
    traded_price = float(data.get('traded_price'))

    if not new_symbol or not new_volume or not traded_price:
        return jsonify({"error": "Incomplete data provided"}), 400

    symbol = json.loads(user_data['symbol'])
    volumes = json.loads(user_data['volumes'])
    traded_prices = json.loads(user_data['traded_prices'])

    symbol.append(new_symbol)
    volumes.append(new_volume)
    traded_prices.append(traded_price)

    cursor.execute('UPDATE users SET symbol = ?, volumes = ?, traded_prices = ? WHERE username = ?',
                   (json.dumps(symbol), json.dumps(volumes), json.dumps(traded_prices), user))
    conn.commit()
    conn.close()

    return jsonify({"message": "Stock added successfully!"}), 200

@app.route('/delete_stock', methods=['POST'])
def delete_stock():
    try:
        if 'user' not in session:
            return jsonify({"error": "User not logged in"}), 401

        user = session['user']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (user,))
        user_data = cursor.fetchone()
        
        if not user_data:
            return jsonify({"error": "User data not found"}), 404

        data = request.json
        symbol_name = data.get('symbol_name')

        if not symbol_name:
            return jsonify({"error": "Stock name not provided"}), 400

        print(f"Deleting stock {symbol_name} for user {user}")
        print(f"Current user data: {user_data}")

        symbol = json.loads(user_data['symbol'])
        volumes = json.loads(user_data['volumes'])
        traded_prices = json.loads(user_data['traded_prices'])

        if symbol_name in symbol:
            index_to_delete = symbol.index(symbol_name)
            del symbol[index_to_delete]
            del volumes[index_to_delete]
            del traded_prices[index_to_delete]

            cursor.execute('UPDATE users SET symbol = ?, volumes = ?, traded_prices = ? WHERE username = ?',
                           (json.dumps(symbol), json.dumps(volumes), json.dumps(traded_prices), user))
            conn.commit()
            conn.close()

            return jsonify({"message": "Stock deleted successfully!"}), 200
        else:
            conn.close()
            return jsonify({"error": "Stock not found"}), 404

    except Exception as e:
        print(f"Error deleting stock: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Load stock data

@app.route('/stock_data', methods=['GET'])
def get_stock_data():
    stock_data = pd.read_csv('stocks.csv')
    return jsonify(stock_data.to_dict(orient='records'))

@app.route('/update_thresholds', methods=['POST'])
def update_thresholds():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    lower_threshold = request.form.get('lower_threshold', 0, type=float)
    upper_threshold = request.form.get('upper_threshold', 10, type=float)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET lower_threshold = ?, upper_threshold = ? WHERE username = ?', 
                   (lower_threshold, upper_threshold, user))
    conn.commit()
    conn.close()

    flash('Threshold values updated successfully!')
    return redirect(url_for('dashboard'))

@app.route('/toggle_email_notifications', methods=['POST'])
def toggle_email_notifications():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Retrieve current user data
    cursor.execute('SELECT email_notifications FROM users WHERE username = ?', (user,))
    current_status = cursor.fetchone()['email_notifications']

    # Toggle the status
    new_status = 1 - current_status  # Toggle between 0 and 1
    cursor.execute('UPDATE users SET email_notifications = ? WHERE username = ?', (new_status, user))
    conn.commit()
    conn.close()

    return jsonify({"message": "Email notifications updated successfully!"}), 200

@app.route('/get_email_notifications', methods=['GET'])
def get_email_notifications():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT email_notifications FROM users WHERE username = ?', (user,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        return jsonify({"email_notifications": user_data['email_notifications']})
    else:
        return jsonify({"error": "User data not found"}), 404


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)  # Assuming you store user info in the session
    return jsonify({"message": "Logged out successfully"}), 200


@app.route('/')
def index():
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

