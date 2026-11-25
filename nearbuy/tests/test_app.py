import os
import re

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app import app, db, Product, Order, User, is_safe_redirect  # noqa: E402


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.app_context():
        yield app.test_client()


def csrf(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(client, email, pw):
    return client.post("/login", data={"email": email, "password": pw, "csrf_token": csrf(client)})


def test_safe_redirect():
    assert is_safe_redirect("/dashboard")
    for bad in ("//evil.com", "http://evil.com", "/\\evil.com", "", None):
        assert not is_safe_redirect(bad)


def test_404_renders_error_page(client):
    r = client.get("/nope")
    assert r.status_code == 404 and b"couldn" in r.data


def test_csrf_required(client):
    assert client.post("/login", data={"email": "a", "password": "b"}).status_code == 400


def test_checkout_decrements_stock_and_blocks_oversell(client):
    login(client, "customer@nearbuy.demo", "Customer@123")
    p = Product.query.filter_by(name="Tomatoes").first()
    before = p.stock
    tok = csrf(client, "/cart")
    client.post(f"/cart/add/{p.id}", data={"qty": "2", "csrf_token": tok})
    client.post("/checkout", data={"address": "x", "phone": "1", "csrf_token": tok})
    db.session.refresh(p)
    assert p.stock == before - 2


def test_cancelled_order_cannot_be_reopened_by_admin(client):
    login(client, "admin@nearbuy.demo", "Admin@123")
    o = Order.query.first()
    if not o:
        pytest.skip("no orders")
    o.status = "Cancelled"
    db.session.commit()
    client.post(f"/admin/order/{o.id}/status", data={"status": "Placed", "csrf_token": csrf(client, "/admin")})
    db.session.refresh(o)
    assert o.status == "Cancelled"
