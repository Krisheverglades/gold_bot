"""Minimal cTrader Open API connection/authentication layer.

Uses Spotware's official ctrader-open-api Python SDK. Order execution is kept
out of this first conversion until symbol metadata (symbolId, min/max/step
volume and broker-specific XAUUSD name) has been loaded and validated.
"""
from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAApplicationAuthReq,
    ProtoOAApplicationAuthRes,
    ProtoOAAccountAuthReq,
    ProtoOAAccountAuthRes,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetAccountListByAccessTokenRes,
)
from twisted.internet import reactor
import ctrader_config as cfg


class CTraderClient:
    def __init__(self, on_ready=None, on_message=None):
        host = (
            EndPoints.PROTOBUF_LIVE_HOST
            if cfg.CTRADER_ENV == "live"
            else EndPoints.PROTOBUF_DEMO_HOST
        )
        self.client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
        self.account_id = cfg.CTRADER_ACCOUNT_ID or None
        self.on_ready = on_ready
        self.on_message = on_message

        self.client.setConnectedCallback(self._connected)
        self.client.setDisconnectedCallback(self._disconnected)
        self.client.setMessageReceivedCallback(self._message)

    def validate_config(self):
        missing = [
            name for name, value in (
                ("CTRADER_CLIENT_ID", cfg.CTRADER_CLIENT_ID),
                ("CTRADER_CLIENT_SECRET", cfg.CTRADER_CLIENT_SECRET),
                ("CTRADER_ACCESS_TOKEN", cfg.CTRADER_ACCESS_TOKEN),
            ) if not value
        ]
        if missing:
            raise ValueError("Missing cTrader settings: " + ", ".join(missing))

    def start(self):
        self.validate_config()
        self.client.startService()
        reactor.run()

    def _connected(self, client):
        req = ProtoOAApplicationAuthReq()
        req.clientId = cfg.CTRADER_CLIENT_ID
        req.clientSecret = cfg.CTRADER_CLIENT_SECRET
        client.send(req).addErrback(self._error)

    def _disconnected(self, client, reason):
        print("cTrader disconnected:", reason)

    def _error(self, failure):
        print("cTrader API error:", failure)

    def _message(self, client, message):
        payload_type = message.payloadType

        if payload_type == ProtoOAApplicationAuthRes().payloadType:
            if self.account_id:
                self._authorize_account()
            else:
                req = ProtoOAGetAccountListByAccessTokenReq()
                req.accessToken = cfg.CTRADER_ACCESS_TOKEN
                client.send(req).addErrback(self._error)
            return

        if payload_type == ProtoOAGetAccountListByAccessTokenRes().payloadType:
            res = Protobuf.extract(message)
            accounts = list(res.ctidTraderAccount)
            if not accounts:
                raise RuntimeError("No cTrader accounts authorized by access token")
            self.account_id = int(accounts[0].ctidTraderAccountId)
            self._authorize_account()
            return

        if payload_type == ProtoOAAccountAuthRes().payloadType:
            if self.on_ready:
                self.on_ready(self)
            return

        if self.on_message:
            self.on_message(self, message)

    def _authorize_account(self):
        req = ProtoOAAccountAuthReq()
        req.ctidTraderAccountId = int(self.account_id)
        req.accessToken = cfg.CTRADER_ACCESS_TOKEN
        self.client.send(req).addErrback(self._error)
