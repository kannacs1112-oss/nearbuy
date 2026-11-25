import os
from decimal import Decimal
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import or_, func
from config import Config
from models import db, User, Shop, Product, Order, OrderItem, Review

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

@app.context_processor
def inject_globals():
    cart = session.get("cart", {})
    return {"cart_count": sum(int(v) for v in cart.values()), "categories": [
        "Groceries", "Furniture", "Meat & Seafood", "Electronics",
        "Clothing", "Hardware", "Pharmacy", "Stationery", "Bakery"
    ]}

@app.route("/")
def index():
    city = request.args.get("city", "Madurai").strip() or "Madurai"
    category = request.args.get("category", "").strip()
    q = request.args.get("q", "").strip()
    shops_query = Shop.query.filter_by(city=city, approved=True)
    if category:
        shops_query = shops_query.filter_by(category=category)
    if q:
        shops_query = shops_query.filter(or_(Shop.name.ilike(f"%{q}%"),
            Shop.category.ilike(f"%{q}%"), Shop.area.ilike(f"%{q}%"),
            Shop.description.ilike(f"%{q}%")))
    shops = shops_query.order_by(Shop.name).all()
    products_query = Product.query.join(Shop).filter(
        Shop.city == city, Shop.approved.is_(True), Product.active.is_(True))
    if q:
        products_query = products_query.filter(or_(Product.name.ilike(f"%{q}%"),
            Product.description.ilike(f"%{q}%")))
    products = products_query.limit(8).all()
    return render_template("index.html", city=city, shops=shops, products=products,
                           selected_category=category, q=q)

@app.route("/shops")
def shops():
    city = request.args.get("city", "Madurai").strip() or "Madurai"
    category = request.args.get("category", "")
    q = request.args.get("q", "").strip()
    query = Shop.query.filter_by(city=city, approved=True)
    if category: query = query.filter_by(category=category)
    if q: query = query.filter(or_(Shop.name.ilike(f"%{q}%"), Shop.area.ilike(f"%{q}%")))
    return render_template("shops.html", shops=query.order_by(Shop.name).all(),
                           city=city, category=category, q=q)

@app.route("/shop/<int:shop_id>")
def shop_detail(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    if not shop.approved: abort(404)
    products = Product.query.filter_by(shop_id=shop.id, active=True).all()
    avg = db.session.query(func.avg(Review.rating)).filter_by(shop_id=shop.id).scalar()
    return render_template("shop_detail.html", shop=shop, products=products,
                           average=round(float(avg), 1) if avg else None)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "customer")
        if role not in ("customer", "shopkeeper", "delivery"): role = "customer"
        if not name or not email or len(password) < 8:
            flash("Enter your name, email and a password with at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "error")
        else:
            user = User(name=name, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to NEARBUY! Your account is ready.", "success")
            return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user)
            flash(f"Welcome back, {user.name}.", "success")
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "shopkeeper":
        shop = Shop.query.filter_by(phone=current_user.phone).first()
        if not shop:
            shop = Shop.query.filter_by(owner_name=current_user.name).first()
        return render_template("shop_dashboard.html", shop=shop)
    if current_user.role == "delivery":
        assigned = Order.query.filter_by(delivery_partner_id=current_user.id).order_by(Order.created_at.desc()).all()
        available = Order.query.filter_by(status="Ready for pickup", delivery_partner_id=None).all()
        return render_template("delivery_dashboard.html", assigned=assigned, available=available)
    if current_user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("customer_dashboard.html", orders=orders)

@app.route("/shop/register", methods=["GET", "POST"])
@role_required("shopkeeper")
def shop_register():
    existing = Shop.query.filter_by(owner_name=current_user.name, phone=current_user.phone).first()
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in
                ["name", "category", "description", "city", "area", "address", "phone"]}
        if not data["name"] or not data["category"] or not data["city"]:
            flash("Shop name, category and city are required.", "error")
        else:
            if existing:
                for k, v in data.items(): setattr(existing, k, v)
                existing.approved = False
                shop = existing
            else:
                shop = Shop(**data, owner_name=current_user.name, approved=False)
                db.session.add(shop)
            current_user.phone = data["phone"]
            db.session.commit()
            flash("Shop submitted for admin approval.", "success")
            return redirect(url_for("dashboard"))
    return render_template("shop_register.html", shop=existing)

@app.route("/shop/manage")
@role_required("shopkeeper")
def manage_shop():
    shop = Shop.query.filter_by(owner_name=current_user.name).first()
    if not shop:
        flash("Register your shop first.", "error")
        return redirect(url_for("shop_register"))
    products = Product.query.filter_by(shop_id=shop.id).all()
    orders = Order.query.filter_by(shop_id=shop.id).order_by(Order.created_at.desc()).all()
    return render_template("manage_shop.html", shop=shop, products=products, orders=orders)

@app.route("/shop/product/add", methods=["POST"])
@role_required("shopkeeper")
def add_product():
    shop = Shop.query.filter_by(owner_name=current_user.name).first()
    if not shop: return redirect(url_for("shop_register"))
    try:
        price = Decimal(request.form.get("price", "0"))
        stock = int(request.form.get("stock", "0"))
        if price <= 0 or stock < 0: raise ValueError()
        product = Product(shop_id=shop.id, name=request.form["name"].strip(),
            description=request.form.get("description", "").strip(), price=price,
            stock=stock, unit=request.form.get("unit", "piece"),
            image_emoji=request.form.get("emoji", "📦"))
        db.session.add(product); db.session.commit()
        flash("Product added.", "success")
    except (ValueError, KeyError):
        flash("Enter a valid product name, price and stock.", "error")
    return redirect(url_for("manage_shop"))

@app.route("/shop/order/<int:order_id>/status", methods=["POST"])
@role_required("shopkeeper")
def shop_order_status(order_id):
    shop = Shop.query.filter_by(owner_name=current_user.name).first()
    order = Order.query.get_or_404(order_id)
    if not shop or order.shop_id != shop.id: abort(403)
    status = request.form.get("status")
    if status in ("Confirmed", "Preparing", "Ready for pickup"):
        order.status = status
        db.session.commit()
        flash("Order status updated.", "success")
    return redirect(url_for("manage_shop"))

@app.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.active or product.stock < 1:
        flash("This product is currently unavailable.", "error")
    else:
        cart = session.get("cart", {})
        key = str(product_id)
        cart[key] = min(int(cart.get(key, 0)) + 1, product.stock)
        session["cart"] = cart
        flash(f"{product.name} added to your cart.", "success")
    return redirect(request.referrer or url_for("index"))

@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})
    products = []
    total = Decimal("0.00")
    for pid, qty in cart_data.items():
        product = db.session.get(Product, int(pid))
        if product and product.active:
            line = product.price * int(qty)
            products.append({"product": product, "qty": int(qty), "line": line})
            total += line
    return render_template("cart.html", items=products, total=total)

@app.route("/cart/update", methods=["POST"])
def cart_update():
    cart_data = session.get("cart", {})
    for pid in list(cart_data):
        try:
            qty = int(request.form.get(pid, "0"))
            product = db.session.get(Product, int(pid))
            if qty <= 0 or not product: cart_data.pop(pid, None)
            else: cart_data[pid] = min(qty, product.stock)
        except ValueError: cart_data.pop(pid, None)
    session["cart"] = cart_data
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart_data = session.get("cart", {})
    if not cart_data:
        flash("Your cart is empty.", "error"); return redirect(url_for("cart"))
    lines = []
    for pid, qty in cart_data.items():
        p = db.session.get(Product, int(pid))
        if p and p.active and p.stock >= int(qty):
            lines.append((p, int(qty)))
    if not lines:
        flash("Your cart items are no longer available.", "error"); return redirect(url_for("cart"))
    shops_in_cart = {p.shop_id for p, q in lines}
    if len(shops_in_cart) > 1:
        flash("For this prototype, checkout is limited to one shop per order. Place separate orders for different shops.", "error")
        return redirect(url_for("cart"))
    total = sum((p.price * q for p, q in lines), Decimal("0.00"))
    if request.method == "POST":
        address = request.form.get("address", "").strip()
        phone = request.form.get("phone", "").strip()
        if not address:
            flash("Please enter a delivery address.", "error")
        else:
            shop = lines[0][0].shop
            order = Order(customer_id=current_user.id, shop_id=shop.id,
                customer_name=current_user.name, phone=phone,
                delivery_address=address, city=shop.city, total=total,
                payment_method="Demo / cash on delivery")
            db.session.add(order); db.session.flush()
            for p, qty in lines:
                db.session.add(OrderItem(order_id=order.id, product_id=p.id,
                    product_name=p.name, quantity=qty, unit_price=p.price))
                p.stock -= qty
            db.session.commit()
            session["cart"] = {}
            flash(f"Order #{order.id} placed successfully!", "success")
            return redirect(url_for("dashboard"))
    return render_template("checkout.html", lines=lines, total=total)

@app.route("/delivery/claim/<int:order_id>", methods=["POST"])
@role_required("delivery")
def claim_delivery(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status == "Ready for pickup" and not order.delivery_partner_id:
        order.delivery_partner_id = current_user.id
        order.status = "Out for delivery"
        db.session.commit()
        flash("Delivery assigned to you.", "success")
    else:
        flash("This delivery is no longer available.", "error")
    return redirect(url_for("dashboard"))

@app.route("/delivery/status/<int:order_id>", methods=["POST"])
@role_required("delivery")
def delivery_status(order_id):
    order = Order.query.get_or_404(order_id)
    if order.delivery_partner_id != current_user.id: abort(403)
    status = request.form.get("status")
    if status in ("Out for delivery", "Delivered"):
        order.status = status
        db.session.commit()
        flash("Delivery status updated.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    return render_template("admin_dashboard.html",
        shops=Shop.query.order_by(Shop.created_at.desc()).all(),
        orders=Order.query.order_by(Order.created_at.desc()).limit(30).all(),
        users_count=User.query.count(), products_count=Product.query.count(),
        orders_count=Order.query.count(),
        revenue=db.session.query(func.sum(Order.total)).filter(Order.status=="Delivered").scalar() or 0)

@app.route("/admin/shop/<int:shop_id>/approve", methods=["POST"])
@role_required("admin")
def approve_shop(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    shop.approved = True
    db.session.commit()
    flash(f"{shop.name} approved.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/order/<int:order_id>/status", methods=["POST"])
@role_required("admin")
def admin_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get("status")
    if status in ("Placed", "Confirmed", "Preparing", "Ready for pickup", "Out for delivery", "Delivered", "Cancelled"):
        order.status = status
        db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/ai-search")
def ai_search():
    # Transparent demo assistant: keyword-based matching, ready to connect to an LLM later.
    q = request.args.get("q", "").strip()
    city = request.args.get("city", "Madurai").strip()
    terms = [t for t in q.lower().split() if len(t) > 2]
    query = Product.query.join(Shop).filter(Shop.city == city, Shop.approved.is_(True), Product.active.is_(True))
    if terms:
        clauses = [Product.name.ilike(f"%{t}%") | Product.description.ilike(f"%{t}%") |
                   Shop.category.ilike(f"%{t}%") for t in terms]
        query = query.filter(or_(*clauses))
    results = query.limit(20).all()
    return render_template("ai_search.html", q=q, city=city, results=results)

@app.route("/health")
def health():
    return {"status": "ok", "app": "NEARBUY"}

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="We couldn't find that page."), 404

def seed_demo():
    if User.query.filter_by(email="admin@nearbuy.demo").first():
        return
    admin = User(name="NEARBUY Admin", email="admin@nearbuy.demo", role="admin")
    admin.set_password("Admin@123")
    customer = User(name="Demo Customer", email="customer@nearbuy.demo", role="customer")
    customer.set_password("Customer@123")
    shop_user = User(name="Kavitha", email="shop@nearbuy.demo", phone="9876500001", role="shopkeeper")
    shop_user.set_password("Shop@123")
    delivery = User(name="Arun Delivery", email="delivery@nearbuy.demo", role="delivery")
    delivery.set_password("Delivery@123")
    db.session.add_all([admin, customer, shop_user, delivery])
    db.session.flush()
    sample_shops = [
        Shop(name="Meenakshi Fresh Mart", owner_name="Kavitha", category="Groceries",
             description="Daily essentials, fresh vegetables and pantry staples.",
             city="Madurai", area="Anna Nagar", address="Anna Nagar, Madurai", phone="9876500001"),
        Shop(name="Vaigai Furniture House", owner_name="Ramesh", category="Furniture",
             description="Practical furniture for homes, hostels and offices.",
             city="Madurai", area="KK Nagar", address="KK Nagar, Madurai", phone="9876500002"),
        Shop(name="Madurai Fresh Cuts", owner_name="Salim", category="Meat & Seafood",
             description="Fresh cuts with hygienic handling. Demo catalogue only.",
             city="Madurai", area="Goripalayam", address="Goripalayam, Madurai", phone="9876500003"),
        Shop(name="Pixel Point Electronics", owner_name="Dinesh", category="Electronics",
             description="Accessories and everyday electronics.",
             city="Madurai", area="Tallakulam", address="Tallakulam, Madurai", phone="9876500004"),
        Shop(name="South Street Hardware", owner_name="Muthu", category="Hardware",
             description="Tools, fittings and home repair essentials.",
             city="Madurai", area="Bypass Road", address="Bypass Road, Madurai", phone="9876500005"),
        Shop(name="Cotton Lane", owner_name="Priya", category="Clothing",
             description="Everyday clothing and local styles.",
             city="Madurai", area="Town Hall Road", address="Town Hall Road, Madurai", phone="9876500006"),
    ]
    db.session.add_all(sample_shops)
    db.session.flush()
    catalog = [
        (0, "Basmati Rice", "Premium rice · 1 kg", 115, 40, "kg", "🍚"),
        (0, "Tomatoes", "Farm-fresh tomatoes · 1 kg", 32, 60, "kg", "🍅"),
        (0, "Cold-Pressed Groundnut Oil", "Traditional cooking oil · 1 L", 185, 25, "litre", "🫙"),
        (1, "Study Table", "Engineered wood · compact design", 3499, 8, "piece", "🪑"),
        (1, "Bookshelf", "Four-tier storage shelf", 2299, 6, "piece", "🗄️"),
        (1, "Dining Chair", "Solid wood finish", 1599, 12, "piece", "🪑"),
        (2, "Chicken Curry Cut", "Fresh chicken · 500 g (demo listing)", 145, 20, "pack", "🍗"),
        (2, "Mutton Curry Cut", "Fresh mutton · 500 g (demo listing)", 420, 12, "pack", "🥩"),
        (3, "Wireless Mouse", "2.4 GHz USB mouse", 499, 18, "piece", "🖱️"),
        (3, "USB-C Cable", "Fast charging cable", 249, 30, "piece", "🔌"),
        (4, "Tool Kit", "Home repair starter kit", 899, 10, "kit", "🧰"),
        (5, "Cotton Kurta", "Everyday cotton wear", 799, 15, "piece", "👕"),
    ]
    for si, name, desc, price, stock, unit, emoji in catalog:
        db.session.add(Product(shop_id=sample_shops[si].id, name=name, description=desc,
            price=Decimal(str(price)), stock=stock, unit=unit, image_emoji=emoji))
    db.session.commit()

with app.app_context():
    db.create_all()
    seed_demo()

if __name__ == "__main__":
    app.run(debug=True)
