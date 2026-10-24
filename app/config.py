from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AlgoTrade AI — Production Trading Workstation"
    version: str = "1.0.0"
    environment: str = "development"
    paper_trading_only: bool = True
    database_url: str = "sqlite:///./algotrade.db"
    log_level: str = "INFO"

    # Supabase Configuration
    supabase_url: str = ""
    supabase_key: str = ""

    # DhanHQ Broker Configuration
    dhan_client_id: str = ""
    dhan_access_token: str = ""
    dhan_env: str = "sandbox"  # "sandbox" or "live"

    # TradingView Webhook Configuration
    tradingview_webhook_secret: str = "default_secret_change_in_production"

    # Risk Management Defaults
    risk_fraction: float = 0.0025  # 0.25% equity risk per trade
    max_position_value_fraction: float = 0.10  # 10% max notional exposure
    max_daily_loss_fraction: float = 0.01  # 1% max daily drawdown
    max_drawdown_limit_fraction: float = 0.05  # 5% max peak-to-trough circuit breaker
    max_open_positions: int = 10
    default_account_equity: float = 1_000_000.0  # ₹10,00,000 INR default paper balance

    # Notification Services
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    alert_email: str = ""

    # Safety: Live execution adapter is strictly absent in this release.
    # Live mode is forbidden by policy and cannot be activated.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

if not settings.paper_trading_only:
    raise RuntimeError(
        "CRITICAL SAFETY VIOLATION: PAPER_TRADING_ONLY is hard-enforced in this platform release. "
        "Live broker execution adapter is completely absent and live execution cannot be enabled."
    )

