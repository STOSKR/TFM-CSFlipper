"""Editable flow runner.

Edit the CONFIG section, then run:

    python run_flow.py

This file is only an orchestrator. Each real operation lives in its own short
script, such as steamdt.py, prefilter.py, steam_market.py, manual_import.py or
ocr_import.py.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

# =============================================================================
# CONFIG
# =============================================================================

# Nombre legible de la ejecucion. Se usa para nombrar el archivo de log.
FLOW_NAME = "steamdt_research_dry_run"

# Carpeta donde se guardan los logs de ejecucion.
LOG_DIR = Path("logs")

# Carpeta donde cada script puede guardar salidas intermedias del flujo.
OUTPUT_DIR = Path("data/flow-runs")

# Si es True, cualquier fase fallida detiene el flujo completo.
# Si es False, el error se registra y se intenta continuar con las siguientes fases.
STOP_ON_ERROR = True

# Si es True, el log incluye todo stdout/stderr de los scripts ejecutados.
# Si es False, solo guarda las ultimas lineas utiles para no llenar el log.
VERBOSE_CHILD_OUTPUT = False

# Numero de lineas finales de salida que se guardan por script si VERBOSE_CHILD_OUTPUT es False.
CHILD_LOG_LINES = 8

# Scripts raiz que ejecuta el flujo. Cambialos solo si renombras archivos.
STEAMDT_SCRIPT = Path("steamdt.py")
PREFILTER_SCRIPT = Path("prefilter.py")
STEAM_MARKET_SCRIPT = Path("steam_market.py")
MANUAL_IMPORT_SCRIPT = Path("manual_import.py")
OCR_IMPORT_SCRIPT = Path("ocr_import.py")

# -----------------------------------------------------------------------------
# Fases
# -----------------------------------------------------------------------------

# Descubre candidatos desde SteamDT Hanging y los guarda en JSON.
RUN_STEAMDT_DISCOVERY = True

# Lee el JSON de SteamDT y crea otro JSON con los mejores candidatos.
RUN_BASELINE_PREFILTER = True

# Consulta precios actuales en Steam Market para el JSON seleccionado.
RUN_FETCH_STEAM_PRICES = True

# Si es True, steam_market.py guarda las observaciones en Postgres/Supabase.
# Recomendado: dejar False hasta revisar el output JSON.
RUN_PERSIST_STEAM_OBSERVATIONS = False

# Valida o importa observaciones desde CSV/JSON manual.
RUN_MANUAL_IMPORT = False

# Si es True, manual_import.py persiste en BD; si es False, solo valida.
RUN_PERSIST_MANUAL_IMPORT = False

# Valida o importa observaciones OCR desde un .txt o imagen.
RUN_OCR_IMPORT = False

# Si es True, ocr_import.py persiste en BD; si es False, solo valida.
RUN_PERSIST_OCR_IMPORT = False

# -----------------------------------------------------------------------------
# Parametros de SteamDT
# -----------------------------------------------------------------------------

# Numero maximo de candidatos a extraer de SteamDT.
STEAMDT_LIMIT = 5

# Si es True se usa el perfil rapido. Si es False se usa el perfil conservador.
STEAMDT_FAST_PROFILE = False

# Si es True se muestra el navegador durante el scraping.
STEAMDT_SHOW_BROWSER = False

# Moneda configurada en SteamDT.
STEAMDT_CURRENCY = "EUR"

# Filtro de precio minimo en SteamDT. Usa None para dejarlo vacio.
STEAMDT_MIN_PRICE: float | None = 300

# Filtro de precio maximo en SteamDT. Usa None para dejarlo vacio.
STEAMDT_MAX_PRICE: float | None = None

# Filtro de volumen minimo en SteamDT. Usa None para dejarlo vacio.
STEAMDT_MIN_VOLUME: int | None = 12

# Plataformas incluidas en la busqueda de SteamDT.
STEAMDT_USE_BUFF = True
STEAMDT_USE_UU = True
STEAMDT_USE_C5GAME = False

# -----------------------------------------------------------------------------
# Parametros del prefiltro local
# -----------------------------------------------------------------------------

# Volumen minimo para que un candidato pase al siguiente paso.
PREFILTER_MIN_VOLUME = 12

# Numero maximo de candidatos que pasan a la consulta de Steam Market.
PREFILTER_LIMIT = 5

# -----------------------------------------------------------------------------
# Parametros de import manual y OCR
# -----------------------------------------------------------------------------

# Archivo usado si RUN_MANUAL_IMPORT esta activo.
MANUAL_IMPORT_PATH = Path("tests/fixtures/manual_observations.csv")

# Archivo usado si RUN_OCR_IMPORT esta activo.
OCR_IMPORT_PATH = Path("tests/fixtures/ocr_observations.txt")

# Confianza minima aceptada en OCR.
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
    verbose_child_output: bool
    child_log_lines: int
    steamdt_script: Path
    prefilter_script: Path
    steam_market_script: Path
    manual_import_script: Path
    ocr_import_script: Path
    run_steamdt_discovery: bool
    run_baseline_prefilter: bool
    run_fetch_steam_prices: bool
    run_persist_steam_observations: bool
    run_manual_import: bool
    run_persist_manual_import: bool
    run_ocr_import: bool
    run_persist_ocr_import: bool
    steamdt_limit: int
    steamdt_fast_profile: bool
    steamdt_show_browser: bool
    steamdt_currency: str
    steamdt_min_price: float | None
    steamdt_max_price: float | None
    steamdt_min_volume: int | None
    steamdt_use_buff: bool
    steamdt_use_uu: bool
    steamdt_use_c5game: bool
    prefilter_min_volume: int
    prefilter_limit: int
    manual_import_path: Path
    ocr_import_path: Path
    ocr_min_confidence: float

    @property
    def steamdt_candidates_path(self) -> Path:
        return self.output_dir / f"steamdt_candidates_{self.run_id}.json"

    @property
    def selected_candidates_path(self) -> Path:
        return self.output_dir / f"selected_candidates_{self.run_id}.json"

    @property
    def steam_observations_path(self) -> Path:
        return self.output_dir / f"steam_observations_{self.run_id}.json"


def main() -> int:
    config = build_config()
    logger = configure_logging(config)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== Iniciando flujo %s ===", config.flow_name)
    logger.info("Fases activas: %s", ", ".join(active_phases(config)) or "ninguna")
    logger.info("Parametros recibidos: %s", serialize_config(config))

    for phase in build_phases(config):
        try:
            run_phase(phase, config, logger)
        except subprocess.CalledProcessError:
            logger.exception("[%s] Fase fallida", phase.name)
            if config.stop_on_error:
                logger.info("=== Flujo detenido ===")
                return 1

    logger.info("=== Flujo finalizado ===")
    return 0


@dataclass(frozen=True, slots=True)
class Phase:
    name: str
    description: str
    command: list[str]


def build_config() -> FlowConfig:
    """Create one immutable config snapshot from the editable constants above."""

    return FlowConfig(
        flow_name=FLOW_NAME,
        run_id=datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S"),
        log_dir=LOG_DIR,
        output_dir=OUTPUT_DIR,
        stop_on_error=STOP_ON_ERROR,
        verbose_child_output=VERBOSE_CHILD_OUTPUT,
        child_log_lines=CHILD_LOG_LINES,
        steamdt_script=STEAMDT_SCRIPT,
        prefilter_script=PREFILTER_SCRIPT,
        steam_market_script=STEAM_MARKET_SCRIPT,
        manual_import_script=MANUAL_IMPORT_SCRIPT,
        ocr_import_script=OCR_IMPORT_SCRIPT,
        run_steamdt_discovery=RUN_STEAMDT_DISCOVERY,
        run_baseline_prefilter=RUN_BASELINE_PREFILTER,
        run_fetch_steam_prices=RUN_FETCH_STEAM_PRICES,
        run_persist_steam_observations=RUN_PERSIST_STEAM_OBSERVATIONS,
        run_manual_import=RUN_MANUAL_IMPORT,
        run_persist_manual_import=RUN_PERSIST_MANUAL_IMPORT,
        run_ocr_import=RUN_OCR_IMPORT,
        run_persist_ocr_import=RUN_PERSIST_OCR_IMPORT,
        steamdt_limit=STEAMDT_LIMIT,
        steamdt_fast_profile=STEAMDT_FAST_PROFILE,
        steamdt_show_browser=STEAMDT_SHOW_BROWSER,
        steamdt_currency=STEAMDT_CURRENCY,
        steamdt_min_price=STEAMDT_MIN_PRICE,
        steamdt_max_price=STEAMDT_MAX_PRICE,
        steamdt_min_volume=STEAMDT_MIN_VOLUME,
        steamdt_use_buff=STEAMDT_USE_BUFF,
        steamdt_use_uu=STEAMDT_USE_UU,
        steamdt_use_c5game=STEAMDT_USE_C5GAME,
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


def build_phases(config: FlowConfig) -> tuple[Phase, ...]:
    """Build script commands in the order they should run."""

    phases: list[Phase] = []

    if config.run_steamdt_discovery:
        phases.append(
            Phase(
                name="steamdt",
                description="Iniciando scraping SteamDT",
                command=steamdt_command(config),
            )
        )

    if config.run_baseline_prefilter:
        phases.append(
            Phase(
                name="prefiltro",
                description="Iniciando prefiltro baseline",
                command=prefilter_command(config),
            )
        )

    if config.run_fetch_steam_prices:
        phases.append(
            Phase(
                name="steam_market",
                description="Iniciando scraping Steam Market",
                command=steam_market_command(config),
            )
        )

    if config.run_manual_import:
        phases.append(
            Phase(
                name="manual",
                description="Iniciando importacion manual",
                command=manual_import_command(config),
            )
        )

    if config.run_ocr_import:
        phases.append(
            Phase(
                name="ocr",
                description="Iniciando importacion OCR",
                command=ocr_import_command(config),
            )
        )

    return tuple(phases)


def steamdt_command(config: FlowConfig) -> list[str]:
    """Build the command that discovers candidates with steamdt.py."""

    command = [
        sys.executable,
        str(config.steamdt_script),
        str(config.steamdt_limit),
        "--currency",
        config.steamdt_currency,
        "--output",
        str(config.steamdt_candidates_path),
    ]
    if config.steamdt_fast_profile:
        command.append("--fast")
    if config.steamdt_show_browser:
        command.append("--show")
    if config.steamdt_min_price is not None:
        command.extend(["--min", str(config.steamdt_min_price)])
    if config.steamdt_max_price is not None:
        command.extend(["--max", str(config.steamdt_max_price)])
    if config.steamdt_min_volume is not None:
        command.extend(["--vol", str(config.steamdt_min_volume)])
    if not config.steamdt_use_buff:
        command.append("--no-buff")
    if not config.steamdt_use_uu:
        command.append("--no-uu")
    if config.steamdt_use_c5game:
        command.append("--c5")
    return command


def prefilter_command(config: FlowConfig) -> list[str]:
    """Build the command that creates a selected-candidates JSON."""

    return [
        sys.executable,
        str(config.prefilter_script),
        str(config.steamdt_candidates_path),
        "--output",
        str(config.selected_candidates_path),
        "--min-volume",
        str(config.prefilter_min_volume),
        "--limit",
        str(config.prefilter_limit),
    ]


def steam_market_command(config: FlowConfig) -> list[str]:
    """Build the command that fetches current Steam Market prices."""

    candidates_path = (
        config.selected_candidates_path
        if config.run_baseline_prefilter
        else config.steamdt_candidates_path
    )
    command = [
        sys.executable,
        str(config.steam_market_script),
        "--candidates",
        str(candidates_path),
        "--output",
        str(config.steam_observations_path),
    ]
    if config.run_persist_steam_observations:
        command.append("--persist")
    else:
        command.append("--dry-run")
    return command


def manual_import_command(config: FlowConfig) -> list[str]:
    """Build the command that validates or persists manual CSV/JSON data."""

    command = [
        sys.executable,
        str(config.manual_import_script),
        str(config.manual_import_path),
    ]
    if config.run_persist_manual_import:
        command.append("--persist")
    return command


def ocr_import_command(config: FlowConfig) -> list[str]:
    """Build the command that validates or persists OCR data."""

    command = [
        sys.executable,
        str(config.ocr_import_script),
        str(config.ocr_import_path),
        "--min-confidence",
        str(config.ocr_min_confidence),
    ]
    if config.run_persist_ocr_import:
        command.append("--persist")
    return command


def run_phase(phase: Phase, config: FlowConfig, logger: logging.Logger) -> None:
    """Execute one script and log a compact status summary."""

    logger.info("[%s] %s", phase.name, phase.description)
    logger.info("[%s] Comando: %s", phase.name, format_command(phase.command))

    result = subprocess.run(
        phase.command,
        check=False,
        capture_output=True,
        text=True,
    )
    log_child_output(phase, config, logger, result.stdout, result.stderr)

    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            phase.command,
            output=result.stdout,
            stderr=result.stderr,
        )

    logger.info("[%s] OK", phase.name)


def log_child_output(
    phase: Phase,
    config: FlowConfig,
    logger: logging.Logger,
    stdout: str,
    stderr: str,
) -> None:
    """Log script output without flooding the flow log."""

    for stream_name, text in (("stdout", stdout), ("stderr", stderr)):
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            continue
        selected = lines if config.verbose_child_output else lines[-config.child_log_lines :]
        for line in selected:
            logger.info("[%s] %s: %s", phase.name, stream_name, line)
        if not config.verbose_child_output and len(lines) > len(selected):
            logger.info(
                "[%s] %s: ... %s lineas omitidas",
                phase.name,
                stream_name,
                len(lines) - len(selected),
            )


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

    return json.dumps(asdict(config), default=str, sort_keys=True)


def format_command(command: list[str]) -> str:
    """Format a command for logs."""

    return " ".join(command)


if __name__ == "__main__":
    raise SystemExit(main())
