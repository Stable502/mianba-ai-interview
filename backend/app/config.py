"""应用配置模块"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，可通过环境变量或 .env 文件覆盖"""

    # 数据库
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "interview_ai"

    # JWT
    SECRET_KEY: str = "change-me-to-a-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ===== DeepSeek LLM =====
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ===== 百度语音识别 ASR =====
    BAIDU_ASR_API_KEY: str = ""
    BAIDU_ASR_SECRET_KEY: str = ""
    BAIDU_ASR_DEV_PID: str = "1537"  # 1537=普通话(纯中文识别), 1737=中英文混合

    # 支付宝支付（沙箱/生产共用，公钥模式）
    ALIPAY_APP_ID: str = ""
    ALIPAY_PRIVATE_KEY: str = ""
    ALIPAY_PUBLIC_KEY: str = ""
    ALIPAY_GATEWAY: str = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
    ALIPAY_NOTIFY_URL: str = ""
    ALIPAY_RETURN_URL: str = ""

    # 邮箱验证码（SMTP，无需任何资质审核；推荐 QQ/163 邮箱授权码；未配置时为演示模式）
    SMTP_HOST: str = ""       # 如 smtp.qq.com / smtp.163.com
    SMTP_PORT: int = 465      # 465=SSL(推荐)，587=STARTTLS，其他端口不加密
    SMTP_USER: str = ""       # 发件邮箱地址
    SMTP_AUTH_CODE: str = ""  # SMTP 授权码（不是邮箱登录密码）
    SMTP_SENDER_NAME: str = "面霸AI"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
