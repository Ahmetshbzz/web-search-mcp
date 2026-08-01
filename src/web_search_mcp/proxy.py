import os


class ProxyManager:
    """HTTP / HTTPS / SOCKS5 Proxy rotasyonu ve konfigürasyon yönetimi."""

    @staticmethod
    def get_proxy_url() -> str | None:
        return (
            os.environ.get("PROXY_URL", "").strip()
            or os.environ.get("HTTPS_PROXY", "").strip()
            or os.environ.get("HTTP_PROXY", "").strip()
            or None
        )

    @classmethod
    def is_proxy_configured(cls) -> bool:
        return bool(cls.get_proxy_url())
