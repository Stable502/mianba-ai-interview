"""支付宝客户端（公钥模式 + RSA2）：支持沙箱与生产，raw HTTP 实现，无官方 SDK 依赖

配置项（backend/.env）：
  ALIPAY_APP_ID        应用 APPID（沙箱或正式）
  ALIPAY_PRIVATE_KEY   应用私钥（一行 base64，PKCS1/PKCS8 均可）
  ALIPAY_PUBLIC_KEY    支付宝公钥（注意不是应用公钥，用于验签）
  ALIPAY_GATEWAY       网关，默认沙箱 https://openapi-sandbox.dl.alipaydev.com/gateway.do
  ALIPAY_NOTIFY_URL    异步回调地址（可选，公网部署时填写；本地开发用轮询查询代替）
  ALIPAY_RETURN_URL    支付完成后浏览器跳转地址（可选，如 http://localhost:5173/membership）

流程：page.pay 生成收银台跳转 URL → 用户付款 →
  本地开发：前端轮询 GET /api/orders/{order_no}（内部调 alipay.trade.query）
  生产环境：支付宝异步回调 POST /api/orders/alipay/notify（验签）
"""
import base64
import json
from datetime import datetime
from urllib.parse import urlencode

import httpx
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

from app.config import settings

SANDBOX_GATEWAY = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
PROD_GATEWAY = "https://openapi.alipay.com/gateway.do"


def _wrap_pem(key_b64: str, is_private: bool) -> str:
    """把无头尾的 base64 密钥包装为 PEM；自动区分 PKCS1/PKCS8"""
    body = "\n".join(key_b64[i:i + 64] for i in range(0, len(key_b64), 64))
    if is_private:
        header = "-----BEGIN RSA PRIVATE KEY-----" if key_b64.startswith("MIIC") else "-----BEGIN PRIVATE KEY-----"
        footer = "-----END RSA PRIVATE KEY-----" if key_b64.startswith("MIIC") else "-----END PRIVATE KEY-----"
    else:
        header, footer = "-----BEGIN PUBLIC KEY-----", "-----END PUBLIC KEY-----"
    return f"{header}\n{body}\n{footer}"


class AlipayClient:
    def __init__(self):
        self.app_id = settings.ALIPAY_APP_ID.strip()
        self.private_key = settings.ALIPAY_PRIVATE_KEY.replace(" ", "").replace("\n", "").strip()
        self.alipay_public_key = settings.ALIPAY_PUBLIC_KEY.replace(" ", "").replace("\n", "").strip()
        self.gateway = settings.ALIPAY_GATEWAY.strip() or SANDBOX_GATEWAY
        self.notify_url = settings.ALIPAY_NOTIFY_URL.strip() or None
        self.return_url = settings.ALIPAY_RETURN_URL.strip() or None
        self._priv = None
        self._pub = None

    def is_configured(self) -> bool:
        return bool(self.app_id and self.private_key and self.alipay_public_key)

    _gateway_cache: tuple[float, bool] | None = None  # (时间戳, 结果)

    def is_gateway_alive(self, timeout: float = 3.0, ttl: float = 60.0) -> bool:
        """探测支付宝网关是否可达；结果缓存 60 秒避免频繁请求"""
        import time as _time
        now = _time.time()
        if self._gateway_cache and (now - self._gateway_cache[0]) < ttl:
            return self._gateway_cache[1]
        try:
            r = httpx.get(self.gateway, timeout=timeout)
            alive = r.status_code < 500  # 400/404 说明网关活着，5xx 才是挂了
        except Exception:
            alive = False
        self._gateway_cache = (now, alive)
        return alive

    def _load_keys(self):
        if self._priv is None:
            self._priv = RSA.import_key(_wrap_pem(self.private_key, is_private=True))
            self._pub = RSA.import_key(_wrap_pem(self.alipay_public_key, is_private=False))

    @staticmethod
    def _sign_content(params: dict) -> str:
        """按支付宝规范：剔除 sign 与空值 → key 字典序升序 → k=v& 拼接"""
        items = sorted((k, v) for k, v in params.items() if k != "sign" and v not in (None, ""))
        return "&".join(f"{k}={v}" for k, v in items)

    def _sign(self, params: dict) -> str:
        self._load_keys()
        signer = PKCS1_v1_5.new(self._priv)
        digest = SHA256.new(self._sign_content(params).encode("utf-8"))
        return base64.b64encode(signer.sign(digest)).decode()

    def verify(self, params: dict) -> bool:
        """验签（异步通知）：用支付宝公钥校验 sign"""
        if not self.is_configured():
            return False
        try:
            self._load_keys()
            sign = params.get("sign", "")
            content = self._sign_content(params)
            verifier = PKCS1_v1_5.new(self._pub)
            return verifier.verify(SHA256.new(content.encode("utf-8")), base64.b64decode(sign))
        except Exception:
            return False

    def _common_params(self, method: str, biz_content: str) -> dict:
        params = {
            "app_id": self.app_id,
            "method": method,
            "format": "JSON",
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "biz_content": biz_content,
        }
        if self.notify_url:
            params["notify_url"] = self.notify_url
        return params

    def page_pay_url(self, out_trade_no: str, total_yuan: str, subject: str) -> str:
        """电脑网站支付 alipay.trade.page.pay：返回收银台跳转 URL（GET 方式）"""
        biz = {
            "out_trade_no": out_trade_no,
            "product_code": "FAST_INSTANT_TRADE_PAY",
            "total_amount": total_yuan,
            "subject": subject,
        }
        params = self._common_params("alipay.trade.page.pay", __import__("json").dumps(biz, ensure_ascii=False))
        if self.return_url:
            params["return_url"] = self.return_url
        params["sign"] = self._sign(params)
        return f"{self.gateway}?{urlencode(params)}"

    @staticmethod
    def _parse_gateway_response(resp: httpx.Response) -> dict:
        """解析网关响应；沙箱可能返回 GBK 编码，生产为 UTF-8，两者兼容"""
        raw = resp.content
        for encoding in ("utf-8", "gbk"):
            try:
                return json.loads(raw.decode(encoding))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        return {}

    def query_trade_status(self, out_trade_no: str) -> str | None:
        """alipay.trade.query 查询交易状态；返回 TRADE_SUCCESS / TRADE_FINISHED / 其他 / None(异常或订单不存在)"""
        biz = {"out_trade_no": out_trade_no}
        params = self._common_params("alipay.trade.query", json.dumps(biz))
        params["sign"] = self._sign(params)
        try:
            resp = httpx.post(self.gateway, data=params, timeout=15)
            data = self._parse_gateway_response(resp).get("alipay_trade_query_response", {})
            if data.get("code") == "10000":
                return data.get("trade_status")
        except Exception:
            pass
        return None


alipay_client = AlipayClient()
