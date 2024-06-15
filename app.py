from flask import Flask, request, jsonify, session, redirect, url_for, render_template, flash
import pandas as pd
import yfinance as yf
import sqlite3
import json
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Necessary for session management
app.config['CORS_HEADERS'] = 'Content-Type'
CORS(app)

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
        password TEXT,
        stocks TEXT,
        volumes TEXT,
        traded_prices TEXT
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

@app.route('/update', methods=['GET'])
def update_data():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (user,))
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data:
        return jsonify({"error": "User data not found"}), 404

    stocks = json.loads(user_data['stocks'])
    volumes = json.loads(user_data['volumes'])
    traded_prices = json.loads(user_data['traded_prices'])

    df = pd.DataFrame({
        "Stock Name": stocks,
        "Total Volume Purchased": volumes,
        "Traded Price": traded_prices
    })

    df = update_prices(df)
    invested_total, total_return, total_profit_loss, total_profit_percent = calculate_totals(df)
    df = df.round(2)
    return jsonify({
        "data": df.to_dict(orient='records'),
        "invested_total": invested_total,
        "total_return": total_return,
        "total_profit_loss": total_profit_loss,
        "total_profit_percent": total_profit_percent
    })

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data and user_data['password'] == password:
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        
        if user_data:
            flash('Username already exists')
        else:
            cursor.execute('INSERT INTO users (username, password, stocks, volumes, traded_prices) VALUES (?, ?, ?, ?, ?)',
                           (username, password, '[]', '[]', '[]'))
            conn.commit()
            conn.close()
            flash('Signup successful, please login')
            return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT stocks FROM users WHERE username = ?', (user,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        stocks = json.loads(user_data['stocks'])
        return render_template('dashboard.html', stocks=stocks)
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
