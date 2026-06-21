"""
protocols.py — Builders e validadores de mensagens JSON do protocolo Album P2P
"""
import uuid
import json


def new_uuid() -> str:
    return str(uuid.uuid4())


def build_hello(sender_peer_id: str, peers: list = None) -> dict:
    return {
        "type": "HELLO",
        "message_id": new_uuid(),
        "sender_peer_id": sender_peer_id,
        "peers": peers or []
    }


def build_search(origin_peer_id: str, origin_peer_ip: str, sender_peer_id: str,
                 receiver_peer_id: str, sticker_id: str,
                 query_id: str = None, ttl: int = 7) -> dict:
    return {
        "type": "SEARCH",
        "message_id": new_uuid(),
        "origin_peer_id": origin_peer_id,
        "origin_peer_ip": origin_peer_ip,
        "sender_peer_id": sender_peer_id,
        "receiver_peer_id": receiver_peer_id,
        "query_id": query_id or new_uuid(),
        "ttl": ttl,
        "sticker_id": sticker_id
    }


def build_search_hit(origin_peer_id: str, sender_peer_id: str,
                     receiver_peer_id: str, query_id: str, sticker_id: str) -> dict:
    return {
        "type": "SEARCH_HIT",
        "message_id": new_uuid(),
        "origin_peer_id": origin_peer_id,
        "sender_peer_id": sender_peer_id,
        "receiver_peer_id": receiver_peer_id,
        "query_id": query_id,
        "sticker_id": sticker_id
    }


def build_search_miss(origin_peer_id: str, sender_peer_id: str,
                      receiver_peer_id: str, query_id: str, sticker_id: str) -> dict:
    return {
        "type": "SEARCH_MISS",
        "message_id": new_uuid(),
        "origin_peer_id": origin_peer_id,
        "sender_peer_id": sender_peer_id,
        "receiver_peer_id": receiver_peer_id,
        "query_id": query_id,
        "sticker_id": sticker_id
    }


def build_trade_offer(origin_peer_id: str, sender_peer_id: str,
                      receiver_peer_id: str,
                      offer_sticker_id: str, want_sticker_id: str) -> dict:
    return {
        "type": "TRADE_OFFER",
        "message_id": new_uuid(),
        "origin_peer_id": origin_peer_id,
        "sender_peer_id": sender_peer_id,
        "receiver_peer_id": receiver_peer_id,
        "offer_sticker_id": offer_sticker_id,
        "want_sticker_id": want_sticker_id
    }


def build_trade_accept(origin_peer_id: str, sender_peer_id: str,
                       receiver_peer_id: str,
                       offer_sticker_id: str, want_sticker_id: str) -> dict:
    return {
        "type": "TRADE_ACCEPT",
        "message_id": new_uuid(),
        "origin_peer_id": origin_peer_id,
        "sender_peer_id": sender_peer_id,
        "receiver_peer_id": receiver_peer_id,
        "offer_sticker_id": offer_sticker_id,
        "want_sticker_id": want_sticker_id
    }


def build_trade_reject(origin_peer_id: str, sender_peer_id: str,
                       receiver_peer_id: str,
                       offer_sticker_id: str, want_sticker_id: str) -> dict:
    return {
        "type": "TRADE_REJECT",
        "message_id": new_uuid(),
        "origin_peer_id": origin_peer_id,
        "sender_peer_id": sender_peer_id,
        "receiver_peer_id": receiver_peer_id,
        "offer_sticker_id": offer_sticker_id,
        "want_sticker_id": want_sticker_id
    }


def build_transfer_confirm(origin_peer_id: str, sender_peer_id: str,
                           receiver_peer_id: str,
                           offer_sticker_id: str, want_sticker_id: str) -> dict:
    return {
        "type": "TRANSFER_CONFIRM",
        "message_id": new_uuid(),
        "origin_peer_id": origin_peer_id,
        "sender_peer_id": sender_peer_id,
        "receiver_peer_id": receiver_peer_id,
        "offer_sticker_id": offer_sticker_id,
        "want_sticker_id": want_sticker_id
    }


def serialize(msg: dict) -> str:
    return json.dumps(msg, ensure_ascii=False)


def deserialize(raw: str) -> dict:
    return json.loads(raw)
