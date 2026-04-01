"""Webhook registry API (outbound simulation/report hooks)."""

from flask import Blueprint, jsonify, request

from ..config import Config
from ..services.webhook_service import (
    list_subscriptions,
    register_subscription,
    unregister_subscription,
)
from ..utils.api_auth import require_service_api_key

hooks_bp = Blueprint("hooks", __name__)


@hooks_bp.route("/webhooks", methods=["GET"])
def list_hooks():
    auth_err = require_service_api_key()
    if auth_err:
        return auth_err
    return jsonify({"success": True, "data": list_subscriptions()})


@hooks_bp.route("/webhooks", methods=["POST"])
def register_hook():
    auth_err = require_service_api_key()
    if auth_err:
        return auth_err
    if not Config.MIROFISH_API_KEY:
        return jsonify(
            {
                "success": False,
                "error": "Set MIROFISH_API_KEY to use webhook registration",
            }
        ), 403

    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    secret = (data.get("secret") or "").strip()
    if not url:
        return jsonify({"success": False, "error": "url required"}), 400

    if "events" not in data:
        return jsonify({"success": False, "error": "events field is required"}), 400
    events = data["events"]
    if not isinstance(events, list) or not events:
        return jsonify({"success": False, "error": "events must be a non-empty list"}), 400

    try:
        entry = register_subscription(url, [str(e) for e in events], secret)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "data": entry})


@hooks_bp.route("/webhooks/<sub_id>", methods=["DELETE"])
def delete_hook(sub_id: str):
    auth_err = require_service_api_key()
    if auth_err:
        return auth_err
    ok = unregister_subscription(sub_id)
    if not ok:
        return jsonify({"success": False, "error": "subscription not found"}), 404
    return jsonify({"success": True, "message": "removed"})
