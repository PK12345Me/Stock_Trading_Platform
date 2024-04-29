import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

from datetime import datetime



# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    #get current cash standing
    curr_cash = db.execute("SELECT cash from users WHERE id = ?", session["user_id"])
    cash_value = curr_cash[0]['cash']
    print("this is current value from users table", cash_value)

    data = db.execute("SELECT * FROM payments")
    #print (data)


    check2 = db.execute("SELECT symbols, SUM(shares), SUM(purchase) FROM payments WHERE id = ? GROUP BY symbols", session["user_id"])

    sub_total=0
    for row in check2:
        sub_total += row['SUM(purchase)']

    sub_total = int(sub_total)

    cashe = db.execute("SELECT cash FROM users")
    cash = int(cashe[0]['cash'])
    return render_template('index.html', existing = check2, value = sub_total, cash = cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        result = lookup(symbol)
        cash = db.execute("SELECT cash FROM users")
        # Ensure symbol was submitted
        if not symbol:
            return apology("User must provide symbol", 400)
        # Ensure shares was submitted
        elif result is None:
        # Handle the error
            return apology("invalid symbol entered, try again", 400)
        elif not shares:
            return apology("must provide number of shares", 400)
        # Ensure shares are a positive integer
        elif not shares.isdigit() or int(shares) <= 0:
            return apology("Number of shares must be a positive integer", 400)

        #checing avaialable cash and buying price of the shares
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        purchase = int(shares) * result["price"]
        curr_amount = rows[0]["cash"]


        if int(purchase) <= int(curr_amount):
            new_cash = curr_amount - purchase
            print("<<<<<<<<<<<<<<<<this is current amount", curr_amount)
            print("this is amount of stock bought", purchase)
            print("this is curr_amount - purchase", new_cash)
            db.execute("UPDATE users SET cash = ? WHERE id = ?",new_cash, session["user_id"])
            existing_row = db.execute("SELECT * FROM payments WHERE id = ? AND symbols = ?", session["user_id"], symbol)

            if existing_row:
                # Get current date and time
                now = datetime.now()
                # Format as a string
                timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
                # Symbol exists, update the row
                new_shares = int(existing_row[0]["shares"]) + int(shares) #what if there are multiple - lets keep this table aggregate
                new_purchase = int(existing_row[0]["purchase"]) + int(purchase)
                db.execute("UPDATE payments SET shares = ?, purchase = ? WHERE id = ? AND symbols = ?", new_shares, new_purchase, session["user_id"], symbol)
                #db.execute("UPDATE Purchases SET shares = ?, purchase = ? WHERE id = ? AND symbols = ?", shares, purchase, session["user_id"], symbol)
                db.execute("INSERT INTO Purchases (id, symbols, shares, purchase, timestamp) VALUES (?, ?, ?, ?, ?)", session["user_id"], symbol, shares, purchase, timestamp)

                #print("UPDATE statement:", "UPDATE payments SET shares = ?, purchase = ? WHERE id = ? AND symbols = ?", "\nValues:", (new_shares, new_purchase, session["user_id"], symbol))

                #print("Row updated successfully")
            else:
                # Get current date and time
                now = datetime.now()
                # Format as a string
                timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
                # Symbol doesn't exist, insert a new row
                db.execute("INSERT INTO payments (id, symbols, shares, purchase, timestamp) VALUES (?, ?, ?, ?, ?)", session["user_id"], symbol, shares, purchase,timestamp)
                #print("New row inserted successfully")

                db.execute("INSERT INTO Purchases (id, symbols, shares, purchase, timestamp) VALUES (?, ?, ?, ?, ?)", session["user_id"], symbol, shares, purchase, timestamp)
            flash(f"Bought {shares} of {symbol} for {usd(purchase)}, Updated cash: {usd(new_cash)}")
        else:
            return apology("Insufficient Balance", 403)

        return redirect("/")
        #return render_template("bought.html", result = result, shares = shares, cash = cash[0]['cash'])
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():

    if request.method == "GET":
    #union
        union = []
        history = db.execute(
                            "SELECT * FROM ("
                                "SELECT symbols, shares, purchase as amount,  timestamp,  type FROM Purchases WHERE id = ? "
                                "UNION "
                                "SELECT symbols, shares, selling_price as amount, timestamp, type FROM sales WHERE user_id = ?"
                            ") AS subquery ORDER BY timestamp DESC",
                            session["user_id"], session["user_id"]
                            )

        #print (history)
        return render_template("history.html", union = history)
    else:
        #Redirect user to home page
        return redirect("/")


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    symbol = request.form.get("symbol")
    if request.method == "POST":
        if not symbol:
            return apology("no symbol provided", 400)
        else:
            symbol = symbol.upper()
            result = lookup(symbol)


        if result is None:
        # Handle the error
            return apology("invalid symbol entered, try again", 400)
        else:
            #return redirect("/quoted")
            result["price"] = usd(result["price"])
            return render_template("quoted.html", result=result)

    return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    name = request.form.get("username")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")

    if request.method == "POST": #checking if username DOES NOT exist and password is same as confirmation
         # Ensure username was submitted
        if not name:
            return apology("must provide username", 400)
        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)
        # Ensure password was confirmed
        elif password != confirmation:
            return apology("must confirm password", 400)

        # Query database for username
        #print (name + password)
        rows = db.execute("SELECT * FROM users WHERE username = ?", name)

        if len(rows) == 0 and password == confirmation:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", name,generate_password_hash(password))
            # successful (send them to actually login)
            return render_template("login.html")
        # user exists -  (no need to redirect or render any template)
        else:
            return apology("must confirm password", 400)
            # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"]) #ISSUE ISSUE - it is not adding stock prices after selling properly
@login_required
def sell():
    """Sell shares of stock"""
    symbol = request.form.get("symbol")
    quantity = request.form.get("shares")
    stocks = db.execute("SELECT symbols FROM payments WHERE id = ? GROUP BY symbols", session["user_id"])
    print(stocks)
    if request.method == "POST": #checking if username DOES NOT exist and password is same as confirmation

         # Ensure stock symbol was submitted
        if not symbol:
            return apology("must provide stock symbol selling", 400)
        # Ensure quantity was submitted
        elif not quantity:
            return apology("must provide quantity", 400)
         #Db query to check information
        symbol = symbol.upper()
        check = db.execute("SELECT symbols, SUM(shares) FROM payments WHERE id = ? GROUP BY symbols", session["user_id"])
        #print ("just checking", check)

        for record in check:
            if record['symbols'] == symbol:
                availability = record['SUM(shares)']
                if int(quantity) <= int(availability): #now the selling begins
                    curr_price = lookup(symbol)

                    value = (curr_price.get('price', None))*int(quantity)
                    newQ = int(availability) - int(quantity)
                    # Get current date and time
                    now = datetime.now()
                    # Format as a string
                    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
                    #update sales table
                    db.execute("INSERT INTO sales (user_id, symbols, shares, selling_price, timestamp) VALUES (?, ?, ?, ?, ?)",
                       session["user_id"], symbol, quantity, value, timestamp)
                    #access user table for cash
                    users = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
                    #initiating available cash variable
                    av_cash = users[0]["cash"]
                    #incrementing the cash in hand
                    av_cash += value
                    #print(av_cash)

                    #update cash in primary
                    db.execute("UPDATE users SET cash = ? WHERE id = ?",av_cash, session["user_id"])
                    if newQ == 0:
                        db.execute("DELETE FROM payments WHERE id = ? AND symbols = ?", session["user_id"], symbol)
                    else:
                        #update quantity and remaining VALUE of stocks in portfolio
                        ex_value = db.execute("SELECT purchase FROM payments where id = ? and symbols = ?", session["user_id"], symbol)
                        val = ex_value[0]['purchase']
                        db.execute("UPDATE payments SET shares = ?, purchase = ? WHERE id = ? AND symbols = ?",newQ, (val-value) ,session["user_id"], symbol)

                    flash(f"Sold {quantity} of {symbol} for {usd(value)}, Updated cash: {usd(av_cash)}")
                    #Redirect user to home page
                    return redirect("/")

                else:
                    return apology("Insufficient quantity", 400)



        return apology("Stock not owned ")

    else:
        return render_template("sell.html", stocks=stocks)

@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Sell shares of stock"""
    current = request.form.get("curr_pass")
    new = request.form.get("new_pass")
    # Query database for username
    hashed_password = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
    row = hashed_password[0]
    print("this is hashed password", row["hash"])
    if request.method == "POST": #checking if username DOES NOT exist and password is same as confirmation
        if not current:
            return apology("enter password", 403)
        else:
        # Ensure username exists and password is correct
            if check_password_hash(row["hash"], current):
                # Password is correct
                db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(new), session["user_id"])
                # Proceed with your logic here

            else:
                # Password is incorrect
                return apology("Password is incorrect, try again", 403)
                # Handle the incorrect password scenario here

            return redirect("/")
    return render_template("password.html")
