import os
import platform
import socket

from flask import abort, current_app, request
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Item
from . import api_bp

ALLOWED_FIELDS = {"sku", "name", "quantity"}


def _validate_payload(data, partial=False):
    """Validate an item payload. partial=True is used for PATCH."""
    if not isinstance(data, dict):
        abort(400, description="Request body must be a JSON object")
    errors = []
    unknown = set(data) - ALLOWED_FIELDS
    if unknown:
        errors.append(f"unknown fields: {', '.join(sorted(unknown))}")
    if partial and not (set(data) & ALLOWED_FIELDS):
        errors.append("at least one of sku, name, quantity is required")
    if not partial or "sku" in data:
        sku = data.get("sku")
        if not isinstance(sku, str) or not sku.strip() or len(sku) > 32:
            errors.append("sku must be a non-empty string of at most 32 characters")
    if not partial or "name" in data:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            errors.append("name must be a non-empty string of at most 120 characters")
    if not partial or "quantity" in data:
        qty = data.get("quantity", 0)
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 0:
            errors.append("quantity must be a non-negative integer")
    if errors:
        abort(400, description="; ".join(errors))
    return data


@api_bp.get("/info")
def info():
    return {
        "app": "inventory",
        "version": current_app.config["APP_VERSION"],
        "env": current_app.config["APP_ENV"],
        "python": platform.python_version(),
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "client_ip": request.remote_addr,
    }


@api_bp.get("/items")
def list_items():
    stmt = db.select(Item).order_by(Item.id)
    q = request.args.get("q")
    if q:
        stmt = stmt.where(Item.name.ilike(f"%{q}%"))
    min_qty = request.args.get("min_quantity", type=int)
    if min_qty is not None:
        stmt = stmt.where(Item.quantity >= min_qty)
    items = db.session.execute(stmt).scalars().all()
    return {"count": len(items), "items": [item.to_dict() for item in items]}


@api_bp.get("/items/<int:item_id>")
def get_item(item_id):
    item = db.get_or_404(Item, item_id, description=f"Item {item_id} not found")
    return item.to_dict()


@api_bp.post("/items")
def create_item():
    data = _validate_payload(request.get_json(silent=True))
    sku = data["sku"].strip()
    item = Item(sku=sku, name=data["name"].strip(), quantity=data.get("quantity", 0))
    db.session.add(item)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, description=f"Item with sku '{sku}' already exists")
    return item.to_dict(), 201, {"Location": f"/api/v1/items/{item.id}"}


@api_bp.patch("/items/<int:item_id>")
def update_item(item_id):
    item = db.get_or_404(Item, item_id, description=f"Item {item_id} not found")
    data = _validate_payload(request.get_json(silent=True), partial=True)
    for field in ("sku", "name"):
        if field in data:
            setattr(item, field, data[field].strip())
    if "quantity" in data:
        item.quantity = data["quantity"]
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, description=f"Item with sku '{data['sku'].strip()}' already exists")
    return item.to_dict()


@api_bp.delete("/items/<int:item_id>")
def delete_item(item_id):
    item = db.get_or_404(Item, item_id, description=f"Item {item_id} not found")
    db.session.delete(item)
    db.session.commit()
    return "", 204
