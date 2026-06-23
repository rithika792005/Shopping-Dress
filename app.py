from flask import Flask, render_template, request, redirect, session
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from functools import wraps
from config import Config
import bcrypt
import os

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

mongo = PyMongo(app)

# ==========================
# ADMIN AUTH DECORATOR
# ==========================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return redirect("/login")

        if session.get("role") != "admin":
            return "Access Denied"

        return f(*args, **kwargs)

    return decorated_function

# ==========================
# HOME
# ==========================

@app.route("/")
def home():

    search = request.args.get("search")

    if search:
        products = list(
            mongo.db.products.find({
                "name": {
                    "$regex": search,
                    "$options": "i"
                }
            })
        )
    else:
        products = list(
            mongo.db.products.find()
        )

    return render_template(
        "dashboard.html",
        products=products
    )

# ==========================
# REGISTER
# ==========================


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")


        if password != confirm_password:
            return "Passwords do not match"


        if mongo.db.users.find_one({"email": email}):
            return "Email already registered"


        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")


        mongo.db.users.insert_one({

    "username": username,
    "email": email,
    "password": hashed_password,
    "role": "admin"

})


        return redirect("/login")


    return render_template("register.html")

# ==========================
@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        user = mongo.db.users.find_one({
            "email": email
        })

        if not user:
            return "User not found"


        try:

            if bcrypt.checkpw(
                password.encode("utf-8"),
                user["password"].encode("utf-8")
            ):

                session["user_id"] = str(user["_id"])
                session["username"] = user["username"]
                session["role"] = user["role"]


                if user["role"] == "admin":
                    return redirect("/admin")

                return redirect("/")


            else:
                return "Invalid Password"


        except ValueError:

            return "Old password hash. Delete admin user and register again."


    return render_template("login.html")

# ==========================
# LOGOUT
# ==========================

@app.route("/logout")
def logout():

    session.clear()
    return redirect("/login")

# ==========================
# ADMIN DASHBOARD
# ==========================

@app.route("/admin")
@admin_required
def admin():

    products = list(mongo.db.products.find())

    total_products = mongo.db.products.count_documents({})
    total_users = mongo.db.users.count_documents({})
    total_orders = mongo.db.orders.count_documents({})

    return render_template(
        "admin.html",
        products=products,
        total_products=total_products,
        total_users=total_users,
        total_orders=total_orders
    )

# ==========================
# ADD PRODUCT
# ==========================

@app.route("/add_product", methods=["GET", "POST"])
@admin_required
def add_product():

    if request.method == "POST":

        filename = ""

        file = request.files.get("image")

        if file and file.filename:

            filename = secure_filename(
                file.filename
            )

            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

        mongo.db.products.insert_one({

            "name": request.form["name"],
            "price": float(request.form["price"]),
            "description": request.form["description"],
            "image": filename

        })

        return redirect("/admin")

    return render_template("add_product.html")

# ==========================
# EDIT PRODUCT
# ==========================

@app.route("/edit_product/<id>", methods=["GET", "POST"])
@admin_required
def edit_product(id):

    product = mongo.db.products.find_one({
        "_id": ObjectId(id)
    })

    if request.method == "POST":

        mongo.db.products.update_one(
            {"_id": ObjectId(id)},
            {
                "$set": {
                    "name": request.form["name"],
                    "price": float(request.form["price"]),
                    "description": request.form["description"]
                }
            }
        )

        return redirect("/admin")

    return render_template(
        "edit_product.html",
        product=product
    )

# ==========================
# DELETE PRODUCT
# ==========================

@app.route("/delete_product/<id>")
@admin_required
def delete_product(id):

    mongo.db.products.delete_one({
        "_id": ObjectId(id)
    })

    return redirect("/admin")

# ==========================
# PRODUCT DETAILS
# ==========================

@app.route("/product/<id>")
def product(id):

    product = mongo.db.products.find_one({
        "_id": ObjectId(id)
    })

    return render_template(
        "product.html",
        product=product
    )

# ==========================
# ADD TO CART
# ==========================

@app.route("/add_to_cart/<id>")
def add_to_cart(id):

    if "user_id" not in session:
        return redirect("/login")

    mongo.db.cart.insert_one({
        "user_id": session["user_id"],
        "product_id": id
    })

    return redirect("/")

# ==========================
# CART
# ==========================

@app.route("/cart")
def cart():

    if "user_id" not in session:
        return redirect("/login")

    items = []

    cart_items = mongo.db.cart.find({
        "user_id": session["user_id"]
    })

    for item in cart_items:

        product = mongo.db.products.find_one({
            "_id": ObjectId(item["product_id"])
        })

        if product:
            items.append(product)

    return render_template(
        "cart.html",
        items=items
    )

# ==========================
# REMOVE CART ITEM
# ==========================

@app.route("/remove_cart/<id>")
def remove_cart(id):

    if "user_id" not in session:
        return redirect("/login")

    mongo.db.cart.delete_one({
        "user_id": session["user_id"],
        "product_id": str(id)
    })

    return redirect("/cart")

# ==========================
# PLACE ORDER
# ==========================

@app.route("/place_order")
def place_order():

    if "user_id" not in session:
        return redirect("/login")

    cart_items = mongo.db.cart.find({
        "user_id": session["user_id"]
    })

    for item in cart_items:

        mongo.db.orders.insert_one({
            "user_id": session["user_id"],
            "product_id": item["product_id"]
        })

    mongo.db.cart.delete_many({
        "user_id": session["user_id"]
    })

    return redirect("/orders")


# ==========================
# ORDERS
# ==========================

@app.route("/orders")
def orders():

    if "user_id" not in session:
        return redirect("/login")

    order_list = []

    user_orders = mongo.db.orders.find({
        "user_id": session["user_id"]
    })

    for order in user_orders:

        if "product_id" not in order:
            continue

        try:
            product = mongo.db.products.find_one({
                "_id": ObjectId(order["product_id"])
            })

            if product:
                order_list.append({
                    "product_name": product["name"],
                    "price": product["price"],
                    "status": "Delivered"
                })

        except:
            pass

    return render_template(
        "orders.html",
        orders=order_list
    )


# ==========================
# RUN
# ==========================

import webbrowser

if __name__ == "__main__":
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)