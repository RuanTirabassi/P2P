"""
peer.py — Nó principal do sistema P2P de figurinhas
Uso:
    python peer.py --peer-id ALUNO-02 --port 8080 --sticker FIG-02 [--peers 192.168.1.1:8080,192.168.1.2:8080]

Requisitos:
    pip install websockets
"""
import asyncio
import json
import argparse
import socket
import logging
from inventory import Inventory
from protocols import (
    build_hello, build_search, build_search_hit, build_search_miss,
    build_trade_offer, build_trade_accept, build_trade_reject,
    build_transfer_confirm, serialize, deserialize, new_uuid
)
try:
    import websockets
except ImportError:
    raise ImportError("Instale a dependência: pip install websockets")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

DEFAULT_TTL = 7
DEFAULT_PORT = 8080


class Peer:
    def __init__(self, peer_id: str, port: int, own_sticker_id: str,
                 initial_peers: list = None):
        self.peer_id = peer_id
        self.port = port
        self.ip = self._get_local_ip()
        self.own_sticker_id = own_sticker_id
        self.inventory = Inventory(peer_id, own_sticker_id, f"inventory_{peer_id}.json")

        self.connections: dict = {}
        self.known_peers: set = set(initial_peers or [])
        self.seen_queries: set = set()
        self.pending_searches: dict = {}
        self.pending_trades: dict = {}

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _addr_to_ws_uri(self, addr: str) -> str:
        return f"ws://{addr}"

    async def connect_to(self, addr: str):
        if addr in self.connections:
            return
        try:
            uri = self._addr_to_ws_uri(addr)
            ws = await websockets.connect(uri)
            self.connections[addr] = ws
            self.known_peers.add(addr)
            log.info(f"Conectado a {addr}")
            hello = build_hello(self.peer_id, list(self.known_peers))
            await ws.send(serialize(hello))
            asyncio.ensure_future(self._listen(ws, addr))
        except Exception as e:
            log.warning(f"Falha ao conectar em {addr}: {e}")

    async def _listen(self, ws, addr: str):
        try:
            async for raw in ws:
                try:
                    msg = deserialize(raw)
                    await self._dispatch(msg, ws, addr)
                except Exception as e:
                    log.error(f"Erro ao processar mensagem de {addr}: {e}")
        except websockets.exceptions.ConnectionClosed:
            log.info(f"Conexão com {addr} encerrada")
            self.connections.pop(addr, None)

    async def _send_to(self, addr: str, msg: dict):
        ws = self.connections.get(addr)
        if ws:
            try:
                await ws.send(serialize(msg))
            except Exception as e:
                log.warning(f"Erro ao enviar para {addr}: {e}")
        else:
            await self.connect_to(addr)
            ws = self.connections.get(addr)
            if ws:
                await ws.send(serialize(msg))

    async def _broadcast(self, msg: dict, exclude_addr: str = None):
        for addr, ws in list(self.connections.items()):
            if addr == exclude_addr:
                continue
            try:
                await ws.send(serialize(msg))
            except Exception as e:
                log.warning(f"Erro ao enviar para {addr}: {e}")

    async def _dispatch(self, msg: dict, ws, sender_addr: str):
        t = msg.get("type")
        log.info(f"← [{t}] de {sender_addr}")
        handlers = {
            "HELLO":            self._handle_hello,
            "SEARCH":           self._handle_search,
            "SEARCH_HIT":       self._handle_search_hit,
            "SEARCH_MISS":      self._handle_search_miss,
            "TRADE_OFFER":      self._handle_trade_offer,
            "TRADE_ACCEPT":     self._handle_trade_accept,
            "TRADE_REJECT":     self._handle_trade_reject,
            "TRANSFER_CONFIRM": self._handle_transfer_confirm,
        }
        handler = handlers.get(t)
        if handler:
            await handler(msg, ws, sender_addr)
        else:
            log.warning(f"Tipo de mensagem desconhecido: {t}")

    async def _handle_hello(self, msg: dict, ws, sender_addr: str):
        sender_id = msg.get("sender_peer_id")
        received_peers = msg.get("peers", [])
        new_peers = []
        for p in received_peers:
            if p not in self.known_peers and p != f"{self.ip}:{self.port}":
                self.known_peers.add(p)
                new_peers.append(p)
        log.info(f"HELLO de {sender_id} | novos peers: {new_peers}")
        resp = build_hello(self.peer_id, list(self.known_peers))
        await ws.send(serialize(resp))
        for p in new_peers:
            asyncio.ensure_future(self.connect_to(p))

    async def _handle_search(self, msg: dict, ws, sender_addr: str):
        query_id = msg.get("query_id")
        sticker_id = msg.get("sticker_id")
        ttl = msg.get("ttl", 0)
        origin_peer_id = msg.get("origin_peer_id")
        origin_peer_ip = msg.get("origin_peer_ip")
        sender_peer_id = msg.get("sender_peer_id")

        if query_id in self.seen_queries:
            return
        if ttl <= 0:
            return

        self.seen_queries.add(query_id)

        if self.inventory.has(sticker_id):
            log.info(f"Tenho {sticker_id}! Enviando SEARCH_HIT para {origin_peer_id}")
            hit = build_search_hit(
                origin_peer_id=self.peer_id,
                sender_peer_id=self.peer_id,
                receiver_peer_id=origin_peer_id,
                query_id=query_id,
                sticker_id=sticker_id
            )
            await self._send_to_peer_id(origin_peer_id, origin_peer_ip, hit)
        else:
            miss = build_search_miss(
                origin_peer_id=self.peer_id,
                sender_peer_id=self.peer_id,
                receiver_peer_id=origin_peer_id,
                query_id=query_id,
                sticker_id=sticker_id
            )
            await self._send_to_peer_id(origin_peer_id, origin_peer_ip, miss)

        new_ttl = ttl - 1
        if new_ttl > 0:
            for addr, peer_ws in list(self.connections.items()):
                if addr == sender_addr:
                    continue
                forward = build_search(
                    origin_peer_id=origin_peer_id,
                    origin_peer_ip=origin_peer_ip,
                    sender_peer_id=self.peer_id,
                    receiver_peer_id=addr,
                    sticker_id=sticker_id,
                    query_id=query_id,
                    ttl=new_ttl
                )
                try:
                    await peer_ws.send(serialize(forward))
                except Exception as e:
                    log.warning(f"Falha ao repassar SEARCH para {addr}: {e}")

    async def _handle_search_hit(self, msg: dict, ws, sender_addr: str):
        sticker_id = msg.get("sticker_id")
        query_id = msg.get("query_id")
        owner_peer_id = msg.get("origin_peer_id")
        log.info(f"SEARCH_HIT: {owner_peer_id} tem {sticker_id} (query={query_id})")
        offer = self.own_sticker_id
        if self.inventory.has(offer) and offer != sticker_id:
            log.info(f"Enviando TRADE_OFFER para {owner_peer_id}")
            trade = build_trade_offer(
                origin_peer_id=self.peer_id,
                sender_peer_id=self.peer_id,
                receiver_peer_id=owner_peer_id,
                offer_sticker_id=offer,
                want_sticker_id=sticker_id
            )
            self.pending_trades[trade["message_id"]] = {
                "offer": offer,
                "want": sticker_id,
                "with": owner_peer_id
            }
            await ws.send(serialize(trade))

    async def _handle_search_miss(self, msg: dict, ws, sender_addr: str):
        log.info(f"SEARCH_MISS de {msg.get('origin_peer_id')} para {msg.get('sticker_id')}")

    async def _handle_trade_offer(self, msg: dict, ws, sender_addr: str):
        offer_sticker = msg.get("offer_sticker_id")
        want_sticker = msg.get("want_sticker_id")
        proposer = msg.get("origin_peer_id")
        log.info(f"TRADE_OFFER de {proposer}: oferece {offer_sticker}, quer {want_sticker}")
        if self.inventory.has(want_sticker):
            accept = build_trade_accept(
                origin_peer_id=self.peer_id,
                sender_peer_id=self.peer_id,
                receiver_peer_id=proposer,
                offer_sticker_id=offer_sticker,
                want_sticker_id=want_sticker
            )
            await ws.send(serialize(accept))
            confirm = build_transfer_confirm(
                origin_peer_id=self.peer_id,
                sender_peer_id=self.peer_id,
                receiver_peer_id=proposer,
                offer_sticker_id=want_sticker,
                want_sticker_id=offer_sticker
            )
            await ws.send(serialize(confirm))
            self.inventory.apply_trade(
                give_sticker_id=want_sticker,
                receive_sticker_id=offer_sticker
            )
        else:
            reject = build_trade_reject(
                origin_peer_id=self.peer_id,
                sender_peer_id=self.peer_id,
                receiver_peer_id=proposer,
                offer_sticker_id=offer_sticker,
                want_sticker_id=want_sticker
            )
            await ws.send(serialize(reject))

    async def _handle_trade_accept(self, msg: dict, ws, sender_addr: str):
        log.info(f"TRADE_ACCEPT de {msg.get('origin_peer_id')}: nossa oferta foi aceita!")

    async def _handle_trade_reject(self, msg: dict, ws, sender_addr: str):
        rejector = msg.get("origin_peer_id")
        log.info(f"TRADE_REJECT de {rejector}")
        for k, v in list(self.pending_trades.items()):
            if v.get("with") == rejector:
                del self.pending_trades[k]

    async def _handle_transfer_confirm(self, msg: dict, ws, sender_addr: str):
        offer_sticker = msg.get("offer_sticker_id")
        want_sticker = msg.get("want_sticker_id")
        confirmer = msg.get("origin_peer_id")
        log.info(f"TRANSFER_CONFIRM de {confirmer}: recebo {offer_sticker}, entrego {want_sticker}")
        success = self.inventory.apply_trade(
            give_sticker_id=want_sticker,
            receive_sticker_id=offer_sticker
        )
        if success:
            log.info(f"Inventário atualizado! {self.inventory}")
        else:
            log.error(f"Falha na atualização do inventário após TRANSFER_CONFIRM")

    async def search(self, sticker_id: str):
        query_id = new_uuid()
        self.seen_queries.add(query_id)
        self.pending_searches[query_id] = {"sticker_id": sticker_id}
        log.info(f"Iniciando busca por {sticker_id} (query_id={query_id})")
        for addr, ws in list(self.connections.items()):
            msg = build_search(
                origin_peer_id=self.peer_id,
                origin_peer_ip=self.ip,
                sender_peer_id=self.peer_id,
                receiver_peer_id=addr,
                sticker_id=sticker_id,
                query_id=query_id,
                ttl=DEFAULT_TTL
            )
            try:
                await ws.send(serialize(msg))
            except Exception as e:
                log.warning(f"Falha ao enviar SEARCH para {addr}: {e}")

    async def _send_to_peer_id(self, peer_id: str, peer_ip: str, msg: dict):
        target_addr = f"{peer_ip}:{DEFAULT_PORT}"
        if target_addr in self.connections:
            await self._send_to(target_addr, msg)
        else:
            sent = False
            for addr, ws in self.connections.items():
                if peer_ip in addr:
                    try:
                        await ws.send(serialize(msg))
                        sent = True
                        break
                    except Exception:
                        pass
            if not sent:
                log.warning(f"Não encontrei conexão para {peer_id} ({peer_ip})")

    async def _server_handler(self, ws):
        addr = f"{ws.remote_address[0]}:{ws.remote_address[1]}"
        log.info(f"Nova conexão entrante de {addr}")
        self.connections[addr] = ws
        try:
            async for raw in ws:
                try:
                    msg = deserialize(raw)
                    await self._dispatch(msg, ws, addr)
                except Exception as e:
                    log.error(f"Erro ao processar mensagem de {addr}: {e}")
        except websockets.exceptions.ConnectionClosed:
            log.info(f"Conexão com {addr} encerrada")
        finally:
            self.connections.pop(addr, None)

    async def start(self):
        log.info(f"Iniciando peer {self.peer_id} em {self.ip}:{self.port}")
        for addr in list(self.known_peers):
            asyncio.ensure_future(self.connect_to(addr))
        server = await websockets.serve(self._server_handler, "0.0.0.0", self.port)
        log.info(f"Servidor WebSocket escutando na porta {self.port}")
        log.info(str(self.inventory))
        asyncio.ensure_future(self._cli())
        await server.wait_closed()

    async def _cli(self):
        await asyncio.sleep(1)
        print("\n=== Album P2P CLI ===")
        print("Comandos: search <FIG-XX> | inventory | peers | quit")
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, input, "> ")
                parts = line.strip().split()
                if not parts:
                    continue
                cmd = parts[0].lower()
                if cmd == "search" and len(parts) == 2:
                    await self.search(parts[1].upper())
                elif cmd == "inventory":
                    print(self.inventory)
                elif cmd == "peers":
                    print(f"Peers conhecidos: {self.known_peers}")
                    print(f"Conectados: {list(self.connections.keys())}")
                elif cmd == "quit":
                    print("Encerrando...")
                    asyncio.get_event_loop().stop()
                    break
                else:
                    print("Uso: search <FIG-XX> | inventory | peers | quit")
            except EOFError:
                break


def parse_args():
    parser = argparse.ArgumentParser(description="Album P2P Node")
    parser.add_argument("--peer-id", required=True, help="Ex: ALUNO-02")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--sticker", required=True, help="Ex: FIG-02")
    parser.add_argument("--peers", default="", help="Ex: 192.168.1.1:8080,192.168.1.2:8080")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    initial_peers = [p.strip() for p in args.peers.split(",") if p.strip()]
    peer = Peer(
        peer_id=args.peer_id,
        port=args.port,
        own_sticker_id=args.sticker,
        initial_peers=initial_peers
    )
    try:
        asyncio.run(peer.start())
    except KeyboardInterrupt:
        print("\nEncerrado pelo usuário.")
