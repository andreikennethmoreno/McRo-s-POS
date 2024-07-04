import os
from datetime import datetime
import sqlite3
import sys
import uuid

from flask import Flask, abort, send_file, session, request, redirect, render_template_string, make_response
from fpdf import FPDF
import pdfkit

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)



# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///project.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/sales", methods=["GET", "POST"])
@login_required
def index():
    user_id = session.get("user_id")
    username = session.get("username")
    
    heading = "All Time" 
    
    transactions_db=db.execute("SELECT * FROM transactions")
    
    if (request.method == "POST"):
        time_period = request.form.get('time_period');
        
        if (time_period == "daily"):
            heading = "Daily"

            transactions_db = db.execute("SELECT * FROM transactions WHERE DATE(date_time) = DATE('now', 'localtime')")
        elif (time_period == "weekly"):
            heading = "Weekly"

            transactions_db = db.execute("SELECT * FROM transactions WHERE strftime('%Y-%W', date_time) = strftime('%Y-%W', 'now')")
            
        elif (time_period == "monthly"):
            heading = "Monthly"

            transactions_db = db.execute("SELECT * FROM transactions WHERE strftime('%Y-%m', date_time) = strftime('%Y-%m', 'now')")
        elif (time_period == "yearly"):
            heading = "Yearly"

            transactions_db = db.execute("SELECT * FROM transactions WHERE strftime('%Y', date_time) = strftime('%Y', 'now')")
        else: 
            heading = "All Time"
            transactions_db=db.execute("SELECT * FROM transactions")

        

    return render_template("index.html", transactions=transactions_db,user_id=user_id, username=username , heading=heading)


"""
@app.route("/history")
@login_required
def history():
    return apology("TODO")
"""



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session['username'] = rows[0]["username"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/cart")
@login_required
def cart():
    user_id = session['user_id']

    # Retrieve cart items for the logged-in user
    cart_db = db.execute("SELECT * FROM Cart WHERE user_id = ?", (user_id,))

    inventory_db = db.execute("SELECT * FROM Inventory")


    search_query = request.args.get('q')
    if search_query:
        inventory_db = db.execute("SELECT * FROM inventory WHERE itemName LIKE ?", f"%{search_query}%")

    
    
    return render_template("cart.html", cart=cart_db, inventory=inventory_db, search_query=search_query)




@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    if 'user_id' not in session:
        flash("You need to log in first")
        return redirect('/login')
    
    item_code = request.form.get('item_code')
    item_name = request.form.get('item_name')
    price = float(request.form.get('price'))
    quantity = int(request.form.get('quantity'))
    image_url = request.form.get('image_url')
    user_id = request.form.get('user_id')
    category = request.form.get('category')
    
    
    # Check if item is already in the cart
    result = db.execute("SELECT * FROM Cart WHERE item_name = ? AND user_id = ?", item_name, user_id)
    if result:
        # Item is already in the cart, update the quantity and total
        flash("Item already exist in the cart")
    else:
        # Item is not in the cart, insert a new row
        date = datetime.now()
        total = price * quantity
        db.execute("INSERT INTO Cart (date_time, item_code, item_name, quantity, price, total, image_url, user_id, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", date, item_code, item_name, quantity, price, total, image_url, user_id, category)

    return redirect('/cart')


#ADD
@app.route("/", methods=["GET", "POST"])
@login_required
def add():
    if (request.method == "POST"):
        itemName = request.form.get('itemName')
        description = request.form.get('description')
        category = request.form.get('category')
        price = request.form.get('price')
        stocks = request.form.get('stocks')
        image_url = request.form.get('image_url')

        try:
            db.execute("INSERT INTO inventory (itemName, description, category, price, stocks, image_url) VALUES (?, ?, ?, ?, ?, ?)",
                       itemName, description, category, price, stocks, image_url)

            return redirect('/')
        except:
            return apology('item already exists')

    else:
        search_query = request.args.get('q')        
        search_category = request.args.get('c')

        if search_query:
            inventory_db = db.execute("SELECT * FROM inventory WHERE itemName LIKE ?", f"%{search_query}%")
        elif search_category:
            inventory_db = db.execute("SELECT * FROM inventory WHERE category LIKE ?", f"%{search_category}%")
        else:
            inventory_db = db.execute("SELECT * FROM inventory")
            
            
        return render_template("add.html", inventory=inventory_db, search_query=search_query,  search_category=search_category )


import io

transaction_receipts = {}

        

@app.route("/process", methods=["POST"])
def process():
    user_id = session['user_id']

    if request.method == "POST":
        # Generate a unique transaction code
        transaction_code = str(uuid.uuid4())
        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Insert into transactions
        db.execute("""
            INSERT INTO transactions (transaction_code, date_time, item_id, item_name, quantity, price, total, user_id, category)
            SELECT ?, ?, item_code, item_name, quantity, price, total, user_id, category
            FROM Cart
            WHERE user_id = ?
        """, transaction_code, date_time, user_id)
        
        db.execute("DELETE FROM Cart WHERE user_id = ?", (user_id))

        # Fetch the current transaction details to include in the receipt
        transaction_details = db.execute("""
            SELECT transaction_code, date_time, item_name, quantity, price, total
            FROM transactions
            WHERE transaction_code = ?
        """, transaction_code)

        # Generate PDF receipt
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        pdf.cell(200, 10, txt="Receipt", ln=True, align="C")
        pdf.cell(200, 10, txt="Transaction Details", ln=True, align="L")
        
        for detail in transaction_details:
            pdf.cell(200, 10, txt=f"Transaction Code: {detail['transaction_code']} ", ln=True, align="L")
            pdf.cell(200, 10, txt=f"Transaction Date: {detail['date_time']} ", ln=True, align="L")

            pdf.cell(200, 10, txt=f"Item: {detail['item_name']} | Quantity: {detail['quantity']} | Price: {detail['price']} | Total: {detail['total']}", ln=True)

        # Create a bytes buffer to store the PDF
        buffer = io.BytesIO()
        pdf_str = pdf.output(dest='S').encode('latin1')  # Output PDF as string and encode it
        buffer.write(pdf_str)
        buffer.seek(0)
        
        transaction_receipts[transaction_code] = buffer 
        
         # Send PDF as attachment
        flash('Your receipt is ready for download!', 'info')
        
        return render_template("cart.html", transaction_code=transaction_code )



@app.route("/download_receipt/<transaction_code>")
def download_receipt(transaction_code):
  if transaction_code in transaction_receipts:
    buffer = transaction_receipts[transaction_code]
    del transaction_receipts[transaction_code]  # Remove after download
    return send_file(buffer, as_attachment=True, download_name='receipt.pdf', mimetype='application/pdf')
  else:
    return abort(404) 

        




@app.route("/delete_item", methods=["POST"])
def delete_item():
#REMOVE ITEM
        transaction_code = request.form.get("transaction_code")

        if transaction_code:
            db.execute("DELETE FROM Cart WHERE transaction_code = ?", transaction_code)

        return redirect("/cart")


@app.route("/remove", methods=["POST"])
def remove():
#REMOVE ID
        id = request.form.get("id")

        if id:
            db.execute("DELETE FROM inventory WHERE id = ?", id)

        return redirect("/")



@app.route("/edit", methods=["POST"])
def edit():

        id = request.form.get("id")
        itemName = request.form.get('itemName')
        description = request.form.get('description')
        category = request.form.get('category')
        price = request.form.get('price')
        stocks = request.form.get('stocks')
        image_url = request.form.get('image_url')


        if id:   #updates the cash in the data sbe
            db.execute("UPDATE inventory SET itemName=?, description=?, category=?, price=?, stocks=?, image_url=? WHERE id=?", itemName, description, category, price, stocks, image_url, id)

        return redirect("/")





@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if (request.method == "POST"):
        username = request.form.get('username')
        password = request.form.get('password')
        confirmation = request.form.get('confirmation')

         #chekcs if empty
        if not username:
            return apology("Must Give Username")

        if not password:
            return apology("Must Give password")

        if not confirmation:
            return apology("Must give Pass Confirmaiton")
        #pass must ==  to confirmation
        if password != confirmation:
            return apology("Password Do Not Match ")
        #turns pass into encrypted int
        hash = generate_password_hash(password)

        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
            return redirect('/')
        except:
            return apology('username has already been registered')
    else:
        return render_template("register.html")


@app.route('/item/<int:item_id>')
def item_info(item_id):
    # Retrieve item information based on item_id from the database
    item = db.execute("SELECT * FROM inventory WHERE id = ?", (item_id,))
    
    if item:
       
        # Retrieve similar items based on the category
        category = db.execute("SELECT category FROM inventory WHERE id = ?", (item_id,))
        item_category = (category[0]['category'])
        print(item_id)
        print(item_category)
        similar_items = db.execute("SELECT * FROM inventory WHERE category = ? ", (item_category))
        # Render the template with the item information and similar items
        return render_template('item_info.html', item=item, similar_items=similar_items)
    else:
        # If item is not found, return an error page or redirect to a different page
        return render_template('error.html', message='Item not found'), 404


@app.route('/home')
def home():
    return render_template('home.html')


if __name__ == '__main__':
    app.run(debug=True)


