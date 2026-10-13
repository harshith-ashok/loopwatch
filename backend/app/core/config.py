from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LOOPWATCH_", extra="ignore")

    env: str = "dev"
    demo_seed: int | None = None  # seeds the simulator and the shop's random choices
    demo_data: bool = False  # seed flagged sample history at startup
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://loopwatch:loopwatch@localhost:5433/loopwatch"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    sse_heartbeat_s: float = 2.0
    # Demo shop timings (ms). These defaults are the DEMO profile: tuned so a fault is noticed in
    # seconds. The thresholds in TODO.md (10 s hold, 2 s heartbeat) are the "spec" profile; the
    # test suite pins those in tests/conftest.py.
    shop_payment_ok_ms: int = 40
    shop_payment_slow_ms: int = 800
    shop_payment_timeout_ms: int = 1500
    shop_timeout_error_rate: float = 0.08  # demo: after the guaranteed first failure, an occasional one, not a flood
    shop_worker_tick_ms: int = 50
    # Journey runner and detector
    journey_runner_enabled: bool = True
    journey_interval_s: float = 1.0
    journey_base_url: str = ""  # empty = probe the in-process app over ASGI
    journey_step_timeout_ms: int = 5000
    journey_order_timeout_ms: int = 1500
    detector_window_s: int = 30
    detector_min_runs: int = 5
    detector_timeout_rate: float = 0.15
    detector_sigma: float = 3.0
    detector_state_check_s: int = 5
    detector_reopen_cooldown_s: float = 60.0  # after an escalation, the same ongoing fault does not re-open
    # Edge node (simulated; a real board posts the same schema)
    edge_node: str = "fulfillment-hub-01"
    edge_watch_enabled: bool = True  # tick simulator and evaluate edge rules in the background
    edge_sim_enabled: bool = True
    edge_tick_s: float = 1.0
    edge_watch_s: float = 1.0
    edge_temp_limit_c: float = 70.0
    edge_overheat_hold_s: float = 4.0
    edge_missed_beats: int = 3
    edge_sim_drop_ticks: int = 2  # degraded messages before the simulated node goes silent
    edge_sim_heat_step_c: float = 10.0
    shop_ack_hot_slow_ms: int = 1500
    # Agents
    agents_enabled: bool = True
    agents_auto_act: bool = True  # after diagnosis, hand off to policy and the executor
    agents_max_steps: int = 12  # tool calls per investigation
    agents_time_limit_s: float = 20.0
    agents_llm_timeout_s: float = 15.0
    agents_slow_gateway_ms: int = 300  # mean primary latency above this counts as degraded
    llm_provider: str = "none"  # none | ollama
    llm_model: str = "gpt-oss:120b-cloud"
    ollama_url: str = "http://localhost:11434"
    llm_api_key: str = ""  # only for calling ollama.com directly; the local daemon needs none


@lru_cache
def get_settings() -> Settings:
    return Settings()
