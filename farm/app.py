import base64
from pathlib import Path
import sqlite3
import csv
from flask import Flask, redirect, render_template
from flask import request, session, url_for

app = Flask(__name__)
app.secret_key = "zaring"

DEFAULT_IMAGE_PATH = "images/default.jpg"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def create_db(db_name: str, datafile: str = "product.csv") -> None:
    datafile_path = Path(__file__).resolve().parent / datafile
    with open(datafile_path, "r", encoding="utf8") as f:
        data = csv.reader(f)
        next(data)
        db_file_path = Path(__file__).resolve().parent / f"{db_name}.sqlite3"
        with sqlite3.connect(f"{db_file_path}") as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS product;")
            cur.execute(
                "CREATE TABLE product (id INTEGER PRIMARY KEY," +
                "description, availability integer," +
                "price integer, image BLOB);"
            )

            for row in data:
                image_path = Path(__file__).resolve().parent / row[-1]

                if image_path.exists():
                    with open(image_path, "rb") as image_file:
                        image_blob = image_file.read()
                else:
                    with open(DEFAULT_IMAGE_PATH, "rb") as default_image_file:
                        image_blob = default_image_file.read()

                row = row[:-1]
                row += (image_blob,)
                cur.execute("INSERT INTO product VALUES(?,?,?,?,?)", row)


create_db("product")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    with sqlite3.connect("product.sqlite3") as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM product;")
        data = cur.fetchall()

    for i, row in enumerate(data):
        image_data = row[-1]
        if image_data:
            encoded_image = base64.b64encode(image_data).decode("utf-8")
            data[i] = row[:-1] + (encoded_image,)

    return render_template("client.html", data=data)


@app.route("/admin")
def admin():
    with sqlite3.connect("product.sqlite3") as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM product;")
        data = cur.fetchall()

    for i, row in enumerate(data):
        image_data = row[-1]
        if image_data:
            encoded_image = base64.b64encode(image_data).decode("utf-8")
            data[i] = row[:-1] + (encoded_image,)

    return render_template("admin.html", data=data)


@app.route("/admin/add", methods=["POST"])
def add():
    if request.method == "POST":
        description = request.form["description"]
        availability = int(request.form["availability"])
        price = request.form["price"]
        image_file = request.files.get("image_file")

        if image_file and allowed_file(image_file.filename):

            image_blob = image_file.read()
        else:

            default_image_path = Path(__file__).resolve(
            ).parent / "images" / "default.jpg"
            with open(default_image_path, "rb") as default_image_file:
                image_blob = default_image_file.read()

        with sqlite3.connect("product.sqlite3") as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO product (description, availability, price, image)"
                + " VALUES (?, ?, ?, ?);",
                (description, availability, price, image_blob)
            )

    return redirect(url_for("admin"))


@app.route("/admin/update<int:id>", methods=["GET", "POST"])
def update(id):
    with sqlite3.connect("product.sqlite3") as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM product WHERE id=?", (id,))
        data = cur.fetchone()

    if data is None:
        return redirect(url_for("admin"))

    if request.method == "POST":

        description = request.form.get("description")
        availability = request.form.get("availability")
        price = request.form.get("price")

        image_file = request.files.get("image_file")

        update_values = {}

        if description:
            update_values["description"] = description
        if availability:
            update_values["availability"] = int(availability)
        if price:
            update_values["price"] = int(price)
        if image_file and allowed_file(image_file.filename):
            update_values["image"] = image_file.read()

        if not update_values:
            return redirect(url_for("admin"))

        set_clause = ", ".join([f"{key} = ?" for key in update_values.keys()])
        update_params = tuple(update_values.values()) + (id,)

        with sqlite3.connect("product.sqlite3") as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE product SET {set_clause} WHERE id=?", update_params)

        return redirect(url_for("admin"))
    else:

        with sqlite3.connect("product.sqlite3") as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM product WHERE id=?", (id,))
            data = cur.fetchone()

        image_data = data[-1]
        if image_data:
            encoded_image = base64.b64encode(image_data).decode("utf-8")
            data = data[:-1] + (encoded_image,)

        return render_template("update.html", id=id, data=data)


@app.route("/admin/remove/<int:id>")
def remove(id):
    with sqlite3.connect("product.sqlite3") as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM product WHERE id=?", (id,))

    return redirect(url_for("admin"))


"""Create new function that can view the cart in the client template"""
"""Create a function that can add items to the cart and display them"""
"""Create a function that removes the items from the cart"""
"""Create a function that can manipulate quantity of items
    in the cart and calculate the price"""
SHIPPING_COST = 10
TAX_RATE = 0.06


@app.route("/cart")
def view_cart():
    total = sum(item["total_price"] for item in session.get("cart", []))
    shipping_cost = 5.00
    tax = 0.06 * total
    subtotal = tax + total + shipping_cost
    return render_template("cart.html", total=total,
                           shipping_cost=shipping_cost,
                           tax=tax,
                           subtotal=subtotal)


@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    with sqlite3.connect("product.sqlite3") as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM product WHERE id=?", (product_id,))
        product = cur.fetchone()

    if product:

        cart = session.get("cart", [])
        item_index = next((index for (index, item) in enumerate(
            cart) if item["id"] == product_id), None)

        if item_index is not None:

            cart[item_index]["quantity"] += 1
            cart[item_index]["total_price"] = cart[item_index]["quantity"] * product[3]
        else:
            item = {
                "id": product[0],
                "name": product[1],
                "price": product[3],
                "quantity": 1,
                "total_price": product[3],
                "image": base64.b64encode(product[-1]).decode("utf-8")
            }
            cart.append(item)

        session["cart"] = cart

    return redirect(url_for("index"))


@app.route("/remove_all", methods=["POST"])
def remove_all():
    session["cart"] = []
    return redirect(url_for("view_cart"))


@app.route("/remove_all_client", methods=["POST"])
def remove_all_client():
    session["cart"] = []
    return redirect(url_for("index"))


@app.route("/remove_cart_client/<int:item_id>", methods=["POST"])
def remove_cart_client(item_id):
    cart = session.get("cart", [])
    item_index = next((index for (index, item) in enumerate(
        cart) if item["id"] == item_id), None)

    if item_index is not None:
        quantity_input = request.form.get("quantity", "")
        quantity_to_remove = int(quantity_input) if quantity_input.isdigit() and int(
            quantity_input) > 0 else 1

        if quantity_to_remove >= cart[item_index]["quantity"]:
            cart.pop(item_index)
        else:
            cart[item_index]["quantity"] -= quantity_to_remove
            cart[item_index]["total_price"] = cart[item_index]["quantity"] * \
                cart[item_index]["price"]

    session["cart"] = cart

    return redirect(url_for("index"))


@app.route("/remove_quantity/<int:item_id>", methods=["POST"])
def remove_quantity(item_id):
    cart = session.get("cart", [])

    item_index = next((index for (index, item) in enumerate(
        cart) if item["id"] == item_id), None)

    if item_index is not None:
        quantity_input = request.form.get("quantity", "")
        quantity_to_remove = int(quantity_input) if quantity_input.isdigit() and int(
            quantity_input) > 0 else 1

        if quantity_to_remove >= cart[item_index]["quantity"]:
            cart.pop(item_index)
        else:
            cart[item_index]["quantity"] -= quantity_to_remove
            cart[item_index]["total_price"] = cart[item_index]["quantity"] * \
                cart[item_index]["price"]

    session["cart"] = cart

    return redirect(url_for("view_cart"))


@app.route("/increase_quantity/<int:item_id>", methods=["POST"])
def increase_quantity(item_id):
    quantity_to_increase = int(request.form.get("quantity", 1))

    cart = session.get("cart", [])

    for item in cart:
        if item["id"] == item_id:
            item["quantity"] += quantity_to_increase
            item["total_price"] = item["quantity"] * item["price"]
            break

    session["cart"] = cart

    return redirect(url_for("view_cart"))


def start_app():
    app.run(debug=True)


if __name__ == "__main__":
    start_app()
