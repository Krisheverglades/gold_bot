"""cTrader Open API transport for the rapid XAUUSD strategy."""
from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAApplicationAuthReq, ProtoOAApplicationAuthRes,
    ProtoOAAccountAuthReq, ProtoOAAccountAuthRes,
    ProtoOAGetAccountListByAccessTokenReq, ProtoOAGetAccountListByAccessTokenRes,
    ProtoOASymbolsListReq, ProtoOASymbolsListRes,
    ProtoOASymbolByIdReq, ProtoOASymbolByIdRes,
    ProtoOASubscribeSpotsReq, ProtoOASubscribeSpotsRes, ProtoOASpotEvent,
)
from twisted.internet import reactor
import ctrader_config as cfg


class CTraderClient:
    def __init__(self, on_ready=None, on_tick=None):
        host = EndPoints.PROTOBUF_LIVE_HOST if cfg.CTRADER_ENV == "live" else EndPoints.PROTOBUF_DEMO_HOST
        self.client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
        self.account_id = cfg.CTRADER_ACCOUNT_ID or None
        self.on_ready = on_ready
        self.on_tick = on_tick
        self.symbol_id = None
        self.symbol = None
        self.bid = None
        self.ask = None
        self.client.setConnectedCallback(self._connected)
        self.client.setDisconnectedCallback(self._disconnected)
        self.client.setMessageReceivedCallback(self._message)

    def validate_config(self):
        missing = [n for n,v in (
            ("CTRADER_CLIENT_ID",cfg.CTRADER_CLIENT_ID),
            ("CTRADER_CLIENT_SECRET",cfg.CTRADER_CLIENT_SECRET),
            ("CTRADER_ACCESS_TOKEN",cfg.CTRADER_ACCESS_TOKEN),
        ) if not v]
        if missing:
            raise ValueError("Missing cTrader settings: " + ", ".join(missing))

    def start(self):
        self.validate_config()
        self.client.startService()
        reactor.run()

    def _connected(self, client):
        req=ProtoOAApplicationAuthReq()
        req.clientId=cfg.CTRADER_CLIENT_ID
        req.clientSecret=cfg.CTRADER_CLIENT_SECRET
        client.send(req).addErrback(self._error)

    def _disconnected(self, client, reason):
        print("cTrader disconnected:", reason)

    def _error(self, failure):
        print("cTrader API error:", failure)

    def _send_symbols_list(self):
        req=ProtoOASymbolsListReq()
        req.ctidTraderAccountId=int(self.account_id)
        req.includeArchivedSymbols=False
        self.client.send(req).addErrback(self._error)

    def _send_symbol_details(self):
        req=ProtoOASymbolByIdReq()
        req.ctidTraderAccountId=int(self.account_id)
        req.symbolId.append(int(self.symbol_id))
        self.client.send(req).addErrback(self._error)

    def subscribe_spots(self):
        req=ProtoOASubscribeSpotsReq()
        req.ctidTraderAccountId=int(self.account_id)
        req.symbolId.append(int(self.symbol_id))
        req.subscribeToSpotTimestamp=True
        self.client.send(req).addErrback(self._error)

    def _message(self, client, message):
        pt=message.payloadType
        if pt == ProtoOAApplicationAuthRes().payloadType:
            if self.account_id: self._authorize_account()
            else:
                req=ProtoOAGetAccountListByAccessTokenReq()
                req.accessToken=cfg.CTRADER_ACCESS_TOKEN
                client.send(req).addErrback(self._error)
            return
        if pt == ProtoOAGetAccountListByAccessTokenRes().payloadType:
            res=Protobuf.extract(message)
            accounts=list(res.ctidTraderAccount)
            if not accounts: raise RuntimeError("No cTrader accounts authorized by access token")
            self.account_id=int(accounts[0].ctidTraderAccountId)
            self._authorize_account(); return
        if pt == ProtoOAAccountAuthRes().payloadType:
            self._send_symbols_list(); return
        if pt == ProtoOASymbolsListRes().payloadType:
            res=Protobuf.extract(message)
            wanted=cfg.SYMBOL_NAME.replace("/","").replace("_","").upper()
            match=None
            for s in res.symbol:
                normalized=s.symbolName.replace("/","").replace("_","").upper()
                if normalized == wanted:
                    match=s; break
            if match is None:
                names=", ".join(s.symbolName for s in list(res.symbol)[:30])
                raise RuntimeError(f"Symbol {cfg.SYMBOL_NAME} not found. First available symbols: {names}")
            self.symbol_id=int(match.symbolId)
            self._send_symbol_details(); return
        if pt == ProtoOASymbolByIdRes().payloadType:
            res=Protobuf.extract(message)
            if not res.symbol: raise RuntimeError("No full symbol metadata returned")
            self.symbol=res.symbol[0]
            self.subscribe_spots()
            if self.on_ready: self.on_ready(self)
            return
        if pt == ProtoOASubscribeSpotsRes().payloadType:
            return
        if pt == ProtoOASpotEvent().payloadType:
            e=Protobuf.extract(message)
            if int(e.symbolId) != int(self.symbol_id): return
            if e.HasField("bid"): self.bid=round(e.bid/100000.0, self.symbol.digits)
            if e.HasField("ask"): self.ask=round(e.ask/100000.0, self.symbol.digits)
            if self.bid is not None and self.ask is not None and self.on_tick:
                self.on_tick(self, self.bid, self.ask)
            return

    def _authorize_account(self):
        req=ProtoOAAccountAuthReq()
        req.ctidTraderAccountId=int(self.account_id)
        req.accessToken=cfg.CTRADER_ACCESS_TOKEN
        self.client.send(req).addErrback(self._error)
