from flask import Flask, render_template,url_for, session, request, jsonify, redirect
from pymongo import MongoClient
from flask_cors import CORS
from bson import json_util
import json
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)  # enable if testing locally

app.secret_key = 'prograto'

# Replace this with your real MongoDB URI
client = MongoClient("mongodb+srv://smartcheckout:smartcheckout@smartcheckout.z6jaqh9.mongodb.net/?retryWrites=true&w=majority&appName=Smartcheckout")
db = client.smartcheckout

@app.route('/')
def index():
    return render_template('index.html')


@app.route("/trolley/<trolley_id>")
def customer_dashboard(trolley_id):
    # Get last billed timestamp
    trolley_meta = db.trolleyids.find_one({"trolleyid": trolley_id})
    if not trolley_meta:
        return "Trolley not found", 404

    last_billed = trolley_meta.get("lastbilledstamp")

    # Get unbilled products after last billed timestamp
    scanned = list(db.products.find({
        "trolley_id": trolley_id,
        "timestamp": {"$gt": last_billed},
        "billed": False
    }))

    product_list = []
    total_mrp = 0
    total_price = 0

    for item in scanned:
        product = db.mainproducts.find_one({"productid": item["product_id"]})
        if product:
            mrp = float(product.get("mrp", 0))
            price = float(product.get("price", 0))
            discount = round(mrp - price, 2)

            product_list.append({
                "name": product["name"],
                "barcode": item["product_id"],
                "mrp": mrp,
                "price": price,
                "discount": discount,
                "added": item["timestamp"].strftime("%I:%M:%S %p"),
                "quantity": item.get("quantity", 1)
            })

            total_mrp += mrp * item["quantity"]
            total_price += price * item["quantity"]

    
    print("productlist:", product_list)

    total_discount = round(total_mrp - total_price, 2)

    return render_template("trolley.html",
                           trolley_id=trolley_id,
                           products=product_list,
                           total_mrp=total_mrp,
                           total_discount=total_discount,
                           final_amount=total_price)

@app.route('/api/update_quantity', methods=['POST'])
def update_quantity():
    data = request.json
    barcode = data.get("barcode")
    change = data.get("change", 0)

    product = db.products.find_one({"product_id": barcode, "billed": False})
    if not product:
        return jsonify({"success": False, "message": "Product not found"})

    new_qty = product.get("quantity", 1) + change
    if new_qty <= 0:
        return jsonify({"success": False, "message": "Quantity cannot be less than 1"})

    db.products.update_one(
        {"_id": product["_id"]},
        {"$set": {"quantity": new_qty}}
    )
    return jsonify({"success": True, "new_quantity": new_qty})

@app.route('/api/delete_product', methods=['POST'])
def delete_product():
    data = request.json
    barcode = data.get("barcode")
    product = db.products.find_one({"product_id": barcode, "billed": False})
    if not product:
        return jsonify({"success": False, "message": "Product not found"})
    
    db.products.delete_one({"_id": product["_id"]})
    return jsonify({"success": True})

@app.route("/api/trolley_data/<trolley_id>")
def get_trolley_data(trolley_id):
    trolley_meta = db.trolleyids.find_one({"trolleyid": trolley_id})
    if not trolley_meta:
        return jsonify({"success": False, "message": "Trolley not found"}), 404

    last_billed = trolley_meta.get("lastbilledstamp")

    scanned = list(db.products.find({
        "trolley_id": trolley_id,
        "timestamp": {"$gt": last_billed},
        "billed": False
    }))

    product_list = []
    total_mrp = 0
    total_price = 0

    for item in scanned:
        product = db.mainproducts.find_one({"productid": item["product_id"]})
        if product:
            mrp = float(product.get("mrp", 0))
            price = float(product.get("price", 0))
            qty = item.get("quantity", 1)
            discount = round((mrp - price) * qty, 2)

            product_list.append({
                "name": product["name"],
                "barcode": item["product_id"],
                "mrp": mrp,
                "price": round(price * qty, 2),
                "discount": discount,
                "quantity": qty,
                "added": item["timestamp"].strftime("%I:%M:%S %p")
            })

            total_mrp += mrp * qty
            total_price += price * qty

    return jsonify({
        "success": True,
        "products": product_list,
        "total_mrp": total_mrp,
        "total_discount": round(total_mrp - total_price, 2),
        "final_amount": round(total_price, 2)
    })



@app.route('/api/check_trolley_id', methods=['POST'])
def check_trolley_id():
    data = request.json
    trolley_id = data.get("trolleyid")
    print("Trolley id:", trolley_id)

    all_ids = list(db.trolleysids.find({}, {"trolleyid": 1}))
    print("Available trolley IDs in DB:", all_ids)

    match = db.trolleyids.find_one({"trolleyid": trolley_id})
    print(match)
    if match:
        print("matched")
        return jsonify({"valid": True})
        
    else:
        print("Unmatched")
        return jsonify({"valid": False})
    
#employee
@app.route("/employee/login", methods=["GET", "POST"])
def employee_login():
    if request.method == "POST":
        userid = request.form.get("userid")
        password = request.form.get("password")

        employee = db.employee_credentials.find_one({"userid": userid})
        if not employee:
            return render_template("employee_login.html", error="Invalid user ID")

        if employee["password"] != password:
            return render_template("employee_login.html", error="Incorrect password")

        # Save user in session
        session["employee"] = {
            "name": employee["name"],
            "userid": employee["userid"],
            "position": employee["position"]
        }

        return redirect(url_for("employee_dashboard"))

    return render_template("employee_login.html")

@app.route("/employee/dashboard")
def employee_dashboard():
    if "employee" not in session:
        return redirect("/employee/login")

    emp = session["employee"]
    return render_template("employee_dashboard.html", employee=emp)

@app.route('/api/clear_trolley/<trolley_id>', methods=['POST'])
def clear_trolley(trolley_id):
    now = datetime.now(timezone.utc)

    # Get unbilled products before deleting
    scanned = list(db.products.find({"trolley_id": trolley_id, "billed": False}))
    if not scanned:
        return jsonify({"success": False, "message": "No items to clear"})

    # Prepare product list for cancelled bill
    products = []
    for item in scanned:
        main = db.mainproducts.find_one({"productid": item["product_id"]})
        if main:
            products.append({
                "product_id": item["product_id"],
                "quantity": item.get("quantity", 1),
                "mrp": float(main.get("mrp", 0)),
                "price": float(main.get("price", 0)),
                "name": main.get("name", "")
            })

    # Delete products
    result = db.products.delete_many({
        "trolley_id": trolley_id,
        "billed": False
    })

    # Insert into bills collection
    bill_no = generate_bill_number()
    db.bills.insert_one({
        "billno": bill_no,
        "trolleyid": trolley_id,
        "timestamp": now,
        "status": "CANCELLED",
        "products": products
    })

    return jsonify({
        "success": True,
        "deleted_count": result.deleted_count,
        "message": f"Cleared trolley and saved cancellation bill {bill_no}",
        "billno": bill_no
    })


@app.route('/api/process_payment/<trolley_id>', methods=['POST'])
def process_payment(trolley_id):
    now = datetime.now(timezone.utc)

    # Get unbilled products
    scanned = list(db.products.find({"trolley_id": trolley_id, "billed": False}))
    if not scanned:
        return jsonify({"success": False, "message": "No items to bill"})

    # Update billed status
    db.products.update_many(
        {"trolley_id": trolley_id, "billed": False},
        {"$set": {"billed": True}}
    )

    # Update last billed timestamp
    db.trolleyids.update_one(
        {"trolleyid": trolley_id},
        {"$set": {"lastbilledstamp": now}}
    )

    # Prepare bill data
    products = []
    for item in scanned:
        main = db.mainproducts.find_one({"productid": item["product_id"]})
        if main:
            products.append({
                "product_id": item["product_id"],
                "quantity": item.get("quantity", 1),
                "mrp": float(main.get("mrp", 0)),
                "price": float(main.get("price", 0)),
                "name": main.get("name", "")
            })

    # Insert into bills collection
    bill_no = generate_bill_number()
    db.bills.insert_one({
        "billno": bill_no,
        "trolleyid": trolley_id,
        "timestamp": now,
        "status": "PAID",
        "products": products
    })

    return jsonify({
        "success": True,
        "message": f"Processed payment and saved bill {bill_no}",
        "billno": bill_no
    })


def generate_bill_number():
    count = db.bills.count_documents({})
    return f"BILL-{datetime.now(timezone.utc).year}-{count + 1:03d}"


@app.route("/employee/logout")
def employee_logout():
    session.pop("employee", None)
    return redirect("/employee/login")



if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)

