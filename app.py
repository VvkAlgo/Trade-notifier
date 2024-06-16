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
        stocks TEXT,
        volumes TEXT,
        traded_prices TEXT,
        alert_sent INTEGER DEFAULT 0,
        alert_sent_negative INTEGER DEFAULT 0
    )
    ''')
    conn.commit()
    conn.close()
# Call create_tables to ensure the table is created only if it does not exist
create_tables()

def fetch_real_time_price(stock_name):
    stock = yf.Ticker(stock_name)
    price = stock.history(period='1d')['Close'][0]
    return price

def update_prices(df):
    prices = []
    for stock in df['Stock Name']:
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

def calculate_totals(df):
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
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        
        if user_data:
            flash('Email already exists. Please use a different email.')
            conn.close()
        else:
            cursor.execute('INSERT INTO users (username, password, name, stocks, volumes, traded_prices, alert_sent,alert_sent_negative) VALUES (?, ?, ?, ?, ?,?,?, ?)',
                           (username, password, name, '[]','[]', '[]',0,0))
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
# Continued from Part 1

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name,stocks FROM users WHERE username = ?', (user,))
    user_data = cursor.fetchone()

    if user_data:
        name=user_data['name']
        stocks = json.loads(user_data['stocks'])
        print(f"User data found: {user_data}") 
        return render_template('dashboard.html',stocks=stocks,name=name)
    else:
        flash('User data not found.')
    
    conn.close()
    return redirect(url_for('login'))
    
@app.route('/update', methods=['GET'])
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

    # Retrieve user's name
    name=user_data['name']
    stocks = json.loads(user_data['stocks'])
    volumes = json.loads(user_data['volumes'])
    traded_prices = json.loads(user_data['traded_prices'])

    # Calculate only if there are stocks in the portfolio
    if stocks:
        df = pd.DataFrame({
            "Stock Name": stocks,
            "Total Volume Purchased": volumes,
            "Traded Price": traded_prices
        })

        df = update_prices(df)
        invested_total, total_return, total_profit_loss, total_profit_percent = calculate_totals(df)
        df = df.round(2)
        
  
        # Check if alert needs to be sent for exceeding 10% profit
        if user_data['alert_sent'] == 0 and total_profit_percent > 10:
            send_email(user, "Portfolio Alert", f"Congratulations {name}!! Your portfolio has exceeded 10% profit.")
            cursor.execute('UPDATE users SET alert_sent = 1 WHERE username = ?', (user,))
            conn.commit()

        # Check if alert needs to be reset (portfolio goes below 10% profit)
        if user_data['alert_sent'] == 1 and total_profit_percent < 10:
            cursor.execute('UPDATE users SET alert_sent = 0 WHERE username = ?', (user,))
            conn.commit()

        # Check if alert needs to be sent for going below 0% profit
        if user_data['alert_sent_negative'] == 0 and total_profit_percent < 0:
            send_email(user, "Portfolio Alert", f"Alert {name}!! Your portfolio has gone below 0% profit.")
            cursor.execute('UPDATE users SET alert_sent_negative = 1 WHERE username = ?', (user,))
            conn.commit()

        # Check if alert needs to be reset (portfolio goes above 0% profit)
        if user_data['alert_sent_negative'] == 1 and total_profit_percent >= 0:
            cursor.execute('UPDATE users SET alert_sent_negative = 0 WHERE username = ?', (user,))
            conn.commit()

        conn.close()

        return jsonify({
            "data": df.to_dict(orient='records'),
            "invested_total": invested_total,
            "total_return": total_return,
            "total_profit_loss": total_profit_loss,
            "total_profit_percent": total_profit_percent
        })

    # If no stocks are present, notify the user that the portfolio is empty
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
    new_stock = data.get('stock_name')
    new_volume = int(data.get('stock_volume'))
    traded_price = float(data.get('traded_price'))

    if not new_stock or not new_volume or not traded_price:
        return jsonify({"error": "Incomplete data provided"}), 400

    stocks = json.loads(user_data['stocks'])
    volumes = json.loads(user_data['volumes'])
    traded_prices = json.loads(user_data['traded_prices'])

    stocks.append(new_stock)
    volumes.append(new_volume)
    traded_prices.append(traded_price)

    cursor.execute('UPDATE users SET stocks = ?, volumes = ?, traded_prices = ? WHERE username = ?',
                   (json.dumps(stocks), json.dumps(volumes), json.dumps(traded_prices), user))
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
        stock_name = data.get('stock_name')

        if not stock_name:
            return jsonify({"error": "Stock name not provided"}), 400

        print(f"Deleting stock {stock_name} for user {user}")
        print(f"Current user data: {user_data}")

        stocks = json.loads(user_data['stocks'])
        volumes = json.loads(user_data['volumes'])
        traded_prices = json.loads(user_data['traded_prices'])

        if stock_name in stocks:
            index_to_delete = stocks.index(stock_name)
            del stocks[index_to_delete]
            del volumes[index_to_delete]
            del traded_prices[index_to_delete]

            cursor.execute('UPDATE users SET stocks = ?, volumes = ?, traded_prices = ? WHERE username = ?',
                           (json.dumps(stocks), json.dumps(volumes), json.dumps(traded_prices), user))
            conn.commit()
            conn.close()

            return jsonify({"message": "Stock deleted successfully!"}), 200
        else:
            conn.close()
            return jsonify({"error": "Stock not found"}), 404

    except Exception as e:
        print(f"Error deleting stock: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)


