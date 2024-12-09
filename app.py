from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
import mysql.connector.pooling
import os
import binascii
import os
import binascii
import app
app = Flask(__name__)
app.secret_key = binascii.hexlify(os.urandom(24)).decode()  # Needed for flash messages

db_config = {
    'host': 'localhost',  
    'user': 'root',  
    'password': 'Rakshi@16',  
    'database': 'fresh'  
}

# Connection Pool
cnxpool = mysql.connector.pooling.MySQLConnectionPool(pool_name="mypool",
                                                       pool_size=5,
                                                       **db_config)
def get_db_connection():
    try:
        return cnxpool.get_connection()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# Routes

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        password = request.form.get('password')
        default_address = request.form.get('default_address')

        if not default_address:
            flash('Default address is required!')
            return redirect(url_for('register'))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, mobile, email, password, address) VALUES (%s, %s, %s, %s, %s)",
            (name, mobile, email, password, default_address)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash('Thank you for registering!')
        return redirect(url_for('login'))

    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            flash('Login successful!')
            return redirect(url_for('shop'))
        else:
            flash('Invalid email or password!')

    return render_template('login.html')


@app.route('/shop')
def shop():
    return render_template('shop.html')

@app.route('/items', methods=['GET', 'POST'])
def items():
    if request.method == 'POST':
        # Handle adding items to the cart in session
        item_name = request.form.get("name")
        item_price = float(request.form.get('price'))
        item_quantity = int(request.form.get("quantity"))

        cart_items = session.get("cart_items", [])

        # Check if item already exists in the cart
        for item in cart_items:
            if item['name'] == item_name:
                item['quantity'] += item_quantity
                break
        else:
            cart_items.append({'name': item_name, 'price': item_price, 'quantity': item_quantity})

        session['cart_items'] = cart_items
        flash(f'{item_name} added to your cart!')
        return redirect(url_for('items'))

    # Fetch items from the database for display
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT item_id, item_name, price FROM items")
    items = cursor.fetchall()
    cursor.close()
    conn.close()

    cart_items = session.get('cart_items', [])
    return render_template('items.html', items=items, cart_items=cart_items)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    item_data = request.get_json()
    item_name = item_data['name']
    item_price = item_data['price']
    item_quantity = item_data['quantity']

    cart_items = session.get('cart_items', [])

    # Check if the item is already in the cart
    item_found = False
    for item in cart_items:
        if item['name'] == item_name:
            item_found = True
            item['quantity'] += item_quantity
            break

    if not item_found:
        cart_items.append({
            'name': item_name,
            'price': item_price,
            'quantity': item_quantity
        })

    session['cart_items'] = cart_items
    return jsonify(success=True)

@app.route('/cart', methods=['GET'])
def cart():
    # Get cart items from session
    cart_items = session.get('cart_items', [])
    
    # Calculate total price
    cart_total = sum(item['price'] * item['quantity'] for item in cart_items)
    
    # Render the cart template
    return render_template('cart.html', cart_items=cart_items, cart_total=cart_total)
@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    # Logic to clear the cart (e.g., clearing the session or database)
    session.pop('cart', None)  # Clear the cart from session (if using session)
    return redirect(url_for('cart'))  

@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user_id' not in session:
        return jsonify(success=False, message="User not logged in")

    delivery_address = request.form.get("address", 'Default Address')
    payment_method = request.form['payment_method']
    total_price = float(request.form['total_price'])
    
    # Parse items from the form input fields
    items = []
    cart_items = request.form.getlist('items[]')
    for item_data in cart_items:
        item_name, item_quantity, item_price = item_data.split('|')
        items.append({
            'name': item_name,
            'quantity': int(item_quantity),
            'price': float(item_price)
        })

    try:
        # Insert order into the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert into orders table
        cursor.execute(
            "INSERT INTO orders (user_id, delivery_address, payment_method, status, order_date, total_price) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['user_id'], delivery_address, payment_method, "Yet to Ship", datetime.now(), total_price)
        )
        order_id = cursor.lastrowid  # Get the last inserted order_id
        
        for item in items:
            cursor.execute(
                "INSERT INTO order_items (order_id, item_name, item_price, item_quantity) VALUES (%s, %s, %s, %s)",
                (order_id, item['name'], item['price'], item['quantity'])
            )

        # Commit transaction
        conn.commit()

        # Fetch order details for display (make sure the column name is correct, e.g., 'id' instead of 'order_id')
        cursor.execute("SELECT order_date, status, payment_method, delivery_address FROM orders WHERE id = %s", (order_id,))
        order_details = cursor.fetchone()

        # Close cursor and connection
        cursor.close()
        conn.close()

        # After placing the order, render the success page with order details
        return render_template('order_success.html', 
                               order_id=order_id, 
                               order_date=order_details[0], 
                               status=order_details[1], 
                               payment_method=order_details[2], 
                               delivery_address=order_details[3], 
                               cart_total=total_price)

    except Exception as e:
        print("Error:", str(e))
        conn.rollback()
        return jsonify(success=False, message="Failed to place order: " + str(e))

if __name__ == "__main__":
    app.run(debug=True)
