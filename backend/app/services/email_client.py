"""邮件验证码发送客户端（SMTP）

用个人邮箱的 SMTP 授权码即可发送，无需任何企业/签名资质审核：
- QQ 邮箱：设置 → 账户 → 开启 SMTP 服务 → 获取授权码（smtp.qq.com:465 SSL）
- 163 邮箱：设置 → POP3/SMTP/IMAP → 开启并获取授权码（smtp.163.com:465 SSL）

未配置时为演示模式：验证码打印到后端控制台，并由接口返回 dev_code 供前端提示。
"""
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

from app.config import settings


class EmailClient:
    def __init__(self):
        self.host = settings.SMTP_HOST.strip()
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER.strip()
        self.auth_code = settings.SMTP_AUTH_CODE.strip()
        self.sender_name = settings.SMTP_SENDER_NAME.strip() or "面霸AI"

    def is_configured(self) -> bool:
        return bool(self.host and self.user)

    def send(self, to_email: str, code: str) -> tuple[bool, str]:
        """发送验证码邮件；返回 (是否成功, 说明)。演示模式下不实际发送。"""
        if not self.is_configured():
            print("=" * 56)
            print(f"[邮件演示模式] 收件邮箱 {to_email} 验证码：{code}（5分钟内有效）")
            print("  → 配置 SMTP_HOST/SMTP_USER/SMTP_AUTH_CODE 后将发送真实邮件")
            print("=" * 56)
            return True, "演示模式：验证码已输出到后端控制台"

        msg = MIMEText(
            f"你的验证码是 {code}，5 分钟内有效。\n如非本人操作，请忽略本邮件。",
            "plain",
            "utf-8",
        )
        msg["Subject"] = Header(f"{self.sender_name} 注册验证码", "utf-8")
        msg["From"] = formataddr((str(Header(self.sender_name, "utf-8")), self.user))
        msg["To"] = to_email
        try:
            if self.port == 465:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=15)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                if self.port == 587:
                    server.starttls()
            try:
                if self.auth_code:
                    server.login(self.user, self.auth_code)
                server.sendmail(self.user, [to_email], msg.as_string())
            finally:
                server.quit()
            return True, "验证码邮件已发送"
        except Exception as exc:
            return False, f"邮件发送失败：{exc}"


email_client = EmailClient()
