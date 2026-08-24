import logging

# 1. Package Metadata (Crucial for project lifecycle tracking)
__title__ = "Airbnb Atlas Orchestrator"
__version__ = "2.0.0"

# 2. Centralized Operational Logging
# This establishes a strict formatting framework for monitoring agent behavior
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | [%(levelname)s] | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("atlas_engine")
logger.info(f"Initializing {__title__} v{__version__} Engine...")

# 3. Namespace Flattening
# This explicitly defines what is exposed to the outside world when 'app' is imported
from .graph import app_graph

__all__ = ["app_graph", "logger"]