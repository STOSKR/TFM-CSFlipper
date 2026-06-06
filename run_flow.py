"""Editable flow runner for CS2 market acquisition.

Edit the CONFIG section, then run:

    python run_flow.py

The default flow is conservative: it does not persist anything unless you set
the corresponding RUN_PERSIST_* flag to True.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from apps.acquisition.manual_import import load_manual_observations
from apps.acquisition.ocr_import import load_ocr_observations
from apps.acquisition.steam_market import SteamMarketCandidate, SteamMarketConnector
from apps.acquisition.steamdt_hanging import (
    SteamDTCandidate,
    SteamDTHangingDiscovery,
    SteamDTHangingFilters,
    save_candidates,
)
from packages.persistence.connection import create_pool
from packages.persistence.repositories import MarketObservationIngestionRepository
from packages.prediction.baseline import BaselineCandidate, prioritize_candidates

# =============================================================================
# CONFIG
# =============================================================================

# Nombre legible de la ejecucion. Se usa para nombrar el archivo de log.
FLOW_NAME = "steamdt_research_dry_run"

# Carpeta donde se guardan los logs de ejecucion.
LOG_DIR = Path("logs")

# Carpeta donde se guardan salidas intermedias, como candidatos y observaciones JSON.
OUTPUT_DIR = Path("data/flow-runs")

# Si es True, cualquier error detiene el flujo completo.
# Si es False, el error se registra y el script intenta terminar con lo que pueda.
STOP_ON_ERROR = True

# Phases
# Activa el scraping inicial de candidatos desde SteamDT Hanging.
RUN_STEAMDT_DISCOVERY = True

# Activa un prefiltro ligero para ordenar/recortar candidatos antes de pedir precios a Steam.
RUN_BASELINE_PREFILTER = True

# Activa la consulta de precios actuales en Steam Market para los candidatos seleccionados.
RUN_FETCH_STEAM_PRICES = True

# Si es True, guarda en Postgres/Supabase las observaciones obtenidas de Steam.
# Recomendado: dejar False hasta verificar los resultados generados en data/flow-runs.
RUN_PERSIST_STEAM_OBSERVATIONS = False

# Activa la importacion de observaciones desde CSV/JSON manual.
RUN_MANUAL_IMPORT = False

# Si es True, persiste en BD los registros del import manual.
RUN_PERSIST_MANUAL_IMPORT = False

# Activa la importacion OCR desde un .txt ya extraido o una imagen.
RUN_OCR_IMPORT = False

# Si es True, persiste en BD los registros OCR.
RUN_PERSIST_OCR_IMPORT = False

# SteamDT discovery
# Numero maximo de candidatos a extraer de SteamDT.
STEAMDT_LIMIT = 5

# True ejecuta Playwright sin mostrar navegador. False muestra la ventana para depurar.
STEAMDT_HEADLESS = True

# Moneda configurada en SteamDT.
STEAMDT_CURRENCY = "EUR"

# Tipo de balance elegido en la UI de SteamDT.
STEAMDT_BALANCE_TYPE = "Platform Balance"

# Modo de venta elegido en SteamDT.
STEAMDT_SELL_MODE = "Sell at Platform Lowest Price"

# Modo de compra elegido en SteamDT. Puede ser None si el perfil no lo necesita.
STEAMDT_BUY_MODE = "Buy via STEAM Buy Order"

# Filtro de precio minimo en SteamDT. Usa None para dejarlo vacio.
STEAMDT_MIN_PRICE: Decimal | None = Decimal("300")

# Filtro de precio maximo en SteamDT. Usa None para dejarlo vacio.
STEAMDT_MAX_PRICE: Decimal | None = None

# Filtro de volumen minimo en SteamDT. Usa None para dejarlo vacio.
STEAMDT_MIN_VOLUME: int | None = 12

# Plataformas incluidas en la busqueda de SteamDT.
STEAMDT_PLATFORM_BUFF = True
STEAMDT_PLATFORM_C5GAME = False
STEAMDT_PLATFORM_UU = True

# Candidate prefilter
# Volumen minimo que debe tener un candidato para pasar el prefiltro local.
PREFILTER_MIN_VOLUME = 12

# Numero maximo de candidatos que pasan a la fase de consulta de Steam Market.
PREFILTER_LIMIT = 5

# Manual/OCR imports
# Archivo CSV/JSON usado si RUN_MANUAL_IMPORT esta activo.
MANUAL_IMPORT_PATH = Path("tests/fixtures/manual_observations.csv")

# Archivo .txt o imagen usado si RUN_OCR_IMPORT esta activo.
OCR_IMPORT_PATH = Path("tests/fixtures/ocr_observations.txt")

# Confianza minima aceptada para OCR. Por debajo de este valor se descarta.
OCR_MIN_CONFIDENCE = 0.5


# =============================================================================
# FLOW IMPLEMENTATION
# =============================================================================


@dataclass(frozen=True, slots=True)
class FlowConfig:
    flow_name: str
    run_id: str
    log_dir: Path
    output_dir: Path
    stop_on_error: bool
    run_steamdt_discovery: bool
    run_baseline_prefilter: bool
    run_fetch_steam_prices: bool
    run_persist_steam_observations: bool
    run_manual_import: bool
    run_persist_manual_import: bool
    run_ocr_import: bool
    run_persist_ocr_import: bool
    steamdt_limit: int
    steamdt_headless: bool
    steamdt_currency: str
    steamdt_balance_type: str
    steamdt_sell_mode: str
    steamdt_buy_mode: str | None
    steamdt_min_price: Decimal | None
    steamdt_max_price: Decimal | None
    steamdt_min_volume: int | None
    steamdt_platform_buff: bool
    steamdt_platform_c5game: bool
    steamdt_platform_uu: bool
    prefilter_min_volume: int
    prefilter_limit: int
    manual_import_path: Path
    ocr_import_path: Path
    ocr_min_confidence: float


def build_config() -> FlowConfig:
    """Create one immutable config snapshot from the editable constants above."""

    return FlowConfig(
        flow_name=FLOW_NAME,
        run_id=datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S"),
        log_dir=LOG_DIR,
        output_dir=OUTPUT_DIR,
        stop_on_error=STOP_ON_ERROR,
        run_steamdt_discovery=RUN_STEAMDT_DISCOVERY,
        run_baseline_prefilter=RUN_BASELINE_PREFILTER,
        run_fetch_steam_prices=RUN_FETCH_STEAM_PRICES,
        run_persist_steam_observations=RUN_PERSIST_STEAM_OBSERVATIONS,
        run_manual_import=RUN_MANUAL_IMPORT,
        run_persist_manual_import=RUN_PERSIST_MANUAL_IMPORT,
        run_ocr_import=RUN_OCR_IMPORT,
        run_persist_ocr_import=RUN_PERSIST_OCR_IMPORT,
        steamdt_limit=STEAMDT_LIMIT,
        steamdt_headless=STEAMDT_HEADLESS,
        steamdt_currency=STEAMDT_CURRENCY,
        steamdt_balance_type=STEAMDT_BALANCE_TYPE,
        steamdt_sell_mode=STEAMDT_SELL_MODE,
        steamdt_buy_mode=STEAMDT_BUY_MODE,
        steamdt_min_price=STEAMDT_MIN_PRICE,
        steamdt_max_price=STEAMDT_MAX_PRICE,
        steamdt_min_volume=STEAMDT_MIN_VOLUME,
        steamdt_platform_buff=STEAMDT_PLATFORM_BUFF,
        steamdt_platform_c5game=STEAMDT_PLATFORM_C5GAME,
        steamdt_platform_uu=STEAMDT_PLATFORM_UU,
        prefilter_min_volume=PREFILTER_MIN_VOLUME,
        prefilter_limit=PREFILTER_LIMIT,
        manual_import_path=MANUAL_IMPORT_PATH,
        ocr_import_path=OCR_IMPORT_PATH,
        ocr_min_confidence=OCR_MIN_CONFIDENCE,
    )


def configure_logging(config: FlowConfig) -> logging.Logger:
    """Configure compact console logs and a persistent log file for the run."""

    config.log_dir.mkdir(parents=True, exist_ok=True)
    log_path = config.log_dir / f"{config.flow_name}_{config.run_id}.log"

    logger = logging.getLogger("csflipper.flow")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )

    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.info("Log file: %s", log_path)
    return logger


async def run_flow() -> None:
    """Run the selected phases in order."""

    config = build_config()
    logger = configure_logging(config)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== Iniciando flujo %s ===", config.flow_name)
    logger.info("Fases activas: %s", ", ".join(active_phases(config)) or "ninguna")
    logger.info("Parametros recibidos: %s", serialize_config(config))

    candidates: tuple[SteamDTCandidate, ...] = ()
    selected_candidates: tuple[SteamDTCandidate, ...] = ()

    try:
        if config.run_steamdt_discovery:
            candidates = await phase_steamdt_discovery(config, logger)
            selected_candidates = candidates

        if config.run_baseline_prefilter:
            selected_candidates = phase_baseline_prefilter(config, logger, candidates)

        if config.run_fetch_steam_prices:
            await phase_fetch_steam_prices(config, logger, selected_candidates)

        if config.run_manual_import:
            await phase_manual_import(config, logger)

        if config.run_ocr_import:
            await phase_ocr_import(config, logger)

    except Exception:
        logger.exception("Flujo detenido por error")
        if config.stop_on_error:
            raise

    logger.info("=== Flujo finalizado ===")


async def phase_steamdt_discovery(
    config: FlowConfig,
    logger: logging.Logger,
) -> tuple[SteamDTCandidate, ...]:
    """Scrape candidate opportunities from SteamDT and save them as JSON."""

    logger.info("[steamdt] Iniciando scraping SteamDT")
    filters = SteamDTHangingFilters(
        headless=config.steamdt_headless,
        max_candidates=config.steamdt_limit,
        min_price=config.steamdt_min_price,
        max_price=config.steamdt_max_price,
        min_volume=config.steamdt_min_volume,
        currency_code=config.steamdt_currency,
        balance_type=config.steamdt_balance_type,
        sell_mode=config.steamdt_sell_mode,
        buy_mode=config.steamdt_buy_mode,
        platform_buff=config.steamdt_platform_buff,
        platform_c5game=config.steamdt_platform_c5game,
        platform_uu=config.steamdt_platform_uu,
    )
    candidates = await SteamDTHangingDiscovery(filters).discover()
    output_path = config.output_dir / f"steamdt_candidates_{config.run_id}.json"
    save_candidates(output_path, candidates)
    logger.info("[steamdt] OK candidatos=%s output=%s", len(candidates), output_path)
    return candidates


def phase_baseline_prefilter(
    config: FlowConfig,
    logger: logging.Logger,
    candidates: tuple[SteamDTCandidate, ...],
) -> tuple[SteamDTCandidate, ...]:
    """Keep the best candidates using the current simple baseline score."""

    logger.info("[prefiltro] Iniciando prefiltro baseline de candidatos")
    ranked = prioritize_candidates(
        tuple(
            BaselineCandidate(
                candidate_id=candidate.market_hash_name,
                market_hash_name=candidate.market_hash_name,
                price=candidate.steam_price or candidate.buff_price,
                volume=candidate.volume,
                expected_return_hint=_percent_to_return(candidate.profitability_percent),
            )
            for candidate in candidates
        ),
        min_volume=config.prefilter_min_volume,
        limit=config.prefilter_limit,
    )
    ranked_ids = {candidate.candidate_id for candidate in ranked}
    selected = tuple(
        candidate for candidate in candidates if candidate.market_hash_name in ranked_ids
    )
    logger.info(
        "[prefiltro] OK entrada=%s seleccionados=%s min_volume=%s limit=%s",
        len(candidates),
        len(selected),
        config.prefilter_min_volume,
        config.prefilter_limit,
    )
    return selected


async def phase_fetch_steam_prices(
    config: FlowConfig,
    logger: logging.Logger,
    candidates: tuple[SteamDTCandidate, ...],
) -> None:
    """Fetch current Steam Market prices and optionally persist observations."""

    if not candidates:
        logger.info("[steam] Saltado: no hay candidatos")
        return

    logger.info("[steam] Iniciando scraping Steam Market")
    correlation_id = f"flow:{config.run_id}:{uuid4()}"
    async with SteamMarketConnector() as connector:
        observations = await connector.fetch_candidates(
            [
                SteamMarketCandidate(
                    market_hash_name=candidate.market_hash_name,
                    asset_name=candidate.item_name,
                    quality=candidate.quality,
                    stattrak=candidate.stattrak,
                )
                for candidate in candidates
            ],
            correlation_id=correlation_id,
        )

    output_path = config.output_dir / f"steam_observations_{config.run_id}.json"
    output_path.write_text(
        json.dumps(
            [observation.observation.model_dump(mode="json") for observation in observations],
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("[steam] OK observaciones=%s output=%s", len(observations), output_path)

    if not config.run_persist_steam_observations:
        logger.info("[steam] Persistencia desactivada")
        return

    logger.info("[steam] Persistiendo observaciones")
    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            repository = MarketObservationIngestionRepository(connection)
            for observation in observations:
                await repository.record_observation(
                    observation.observation,
                    asset_name=observation.asset_name,
                    category=observation.category,
                    quality=observation.quality,
                    variant_key=observation.variant_key,
                )
    finally:
        await pool.close()
    logger.info("[steam] Persistencia OK observaciones=%s", len(observations))


async def phase_manual_import(config: FlowConfig, logger: logging.Logger) -> None:
    """Validate or persist manual CSV/JSON observations."""

    logger.info("[manual] Iniciando importacion manual")
    records = load_manual_observations(config.manual_import_path)
    logger.info("[manual] OK registros=%s path=%s", len(records), config.manual_import_path)

    if not config.run_persist_manual_import:
        logger.info("[manual] Persistencia desactivada")
        return

    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            repository = MarketObservationIngestionRepository(connection)
            for record in records:
                await repository.record_observation(
                    record.observation,
                    asset_name=record.asset_name,
                    category=record.category,
                    quality=record.quality,
                    variant_key=record.variant_key,
                )
    finally:
        await pool.close()
    logger.info("[manual] Persistencia OK registros=%s", len(records))


async def phase_ocr_import(config: FlowConfig, logger: logging.Logger) -> None:
    """Validate or persist observations extracted from OCR."""

    logger.info("[ocr] Iniciando importacion OCR")
    records = await load_ocr_observations(
        config.ocr_import_path,
        min_confidence=config.ocr_min_confidence,
    )
    logger.info("[ocr] OK registros=%s path=%s", len(records), config.ocr_import_path)

    if not config.run_persist_ocr_import:
        logger.info("[ocr] Persistencia desactivada")
        return

    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            repository = MarketObservationIngestionRepository(connection)
            for record in records:
                await repository.record_observation(
                    record.observation,
                    asset_name=record.asset_name,
                    category=record.category,
                    quality=record.quality,
                    variant_key=record.variant_key,
                )
    finally:
        await pool.close()
    logger.info("[ocr] Persistencia OK registros=%s", len(records))


def active_phases(config: FlowConfig) -> tuple[str, ...]:
    """Return the human-readable list of enabled phases for the initial log."""

    phases: list[str] = []
    if config.run_steamdt_discovery:
        phases.append("steamdt_discovery")
    if config.run_baseline_prefilter:
        phases.append("baseline_prefilter")
    if config.run_fetch_steam_prices:
        phases.append("fetch_steam_prices")
    if config.run_persist_steam_observations:
        phases.append("persist_steam_observations")
    if config.run_manual_import:
        phases.append("manual_import")
    if config.run_persist_manual_import:
        phases.append("persist_manual_import")
    if config.run_ocr_import:
        phases.append("ocr_import")
    if config.run_persist_ocr_import:
        phases.append("persist_ocr_import")
    return tuple(phases)


def serialize_config(config: FlowConfig) -> str:
    """Serialize config values so the log records exactly what was executed."""

    payload = asdict(config)
    return json.dumps(payload, default=str, sort_keys=True)


def _percent_to_return(value: Decimal | None) -> Decimal | None:
    """Normalize SteamDT percentages into return values used by the prefiltro."""

    if value is None:
        return None
    return value / Decimal("100") if abs(value) > Decimal("3") else value


if __name__ == "__main__":
    asyncio.run(run_flow())
