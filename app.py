from flask import Flask, request, jsonify, session, redirect, url_for, render_template, flash
import pandas as pd
import yfinance as yf
import sqlite3
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Necessary for session management
app.config['CORS_HEADERS'] = 'Content-Type' 
CORS(app)

# Sample user data (for demonstration purposes)
users = {
    "user1": {
        "password": "password1",
        "stocks": [],
        "volumes": [],
        "traded_prices": []
    }
}

# Counter to generate unique IDs for stocks
next_stock_id = 1

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
    user_data = users.get(user)
    if not user_data:
        return jsonify({"error": "User data not found"}), 404

    df = pd.DataFrame({
        "Stock Name": user_data["stocks"],
        "Total Volume Purchased": user_data["volumes"],
        "Traded Price": user_data["traded_prices"]
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
    user_data = users.get(user)
    if not user_data:
        return jsonify({"error": "User data not found"}), 404

    data = request.json
    new_stock = data.get('stock_name')
    new_volume = int(data.get('stock_volume'))
    traded_price = float(data.get('traded_price'))

    if not new_stock or not new_volume or not traded_price:
        return jsonify({"error": "Incomplete data provided"}), 400

    user_data["stocks"].append(new_stock)
    user_data["volumes"].append(new_volume)
    user_data["traded_prices"].append(traded_price)

    return jsonify({"message": "Stock added successfully!"}), 200

def fetch_real_time_price(stock_name):
    stock = yf.Ticker(stock_name)
    price = stock.history(period='1d')['Close'][0]
    return price

@app.route('/delete_stock', methods=['POST'])
def delete_stock():
    try:
        # Check if user is logged in
        if 'user' not in session:
            return jsonify({"error": "User not logged in"}), 401

        user = session['user']
        user_data = users.get(user)
        if not user_data:
            return jsonify({"error": "User data not found"}), 404

        # Retrieve stock name from request data
        data = request.json
        stock_name = data.get('stock_name')

        if not stock_name:
            return jsonify({"error": "Stock name not provided"}), 400

        print(f"Deleting stock {stock_name} for user {user}")
        print(f"Current user data: {user_data}")

        # Verify user_data["stocks"] structure
        if not isinstance(user_data["stocks"], list):
            return jsonify({"error": "User stocks data is not a list"}), 500
        
        # Find the index of the stock based on the stock name
        index_to_delete = None
        for i, stock in enumerate(user_data["stocks"]):
            if isinstance(stock, dict) and stock.get("Stock Name") == stock_name:
                index_to_delete = i
                break

        if index_to_delete is not None:
            # Delete stock from user_data
            del user_data["stocks"][index_to_delete]
            del user_data["volumes"][index_to_delete]
            del user_data["traded_prices"][index_to_delete]

            # Optionally, update a persistent database here

            return jsonify({"message": "Stock deleted successfully!"}), 200
        else:
            return jsonify({"error": "Stock not found"}), 404

    except Exception as e:
        print(f"Error deleting stock: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
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
        if username in users:
            flash('Username already exists')
        else:
            users[username] = {
                "password": password,
                "stocks": [],
                "volumes": [],
                "traded_prices": []
            }
            flash('Signup successful, please login')
            return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', stocks=users[session['user']]['stocks'])

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

