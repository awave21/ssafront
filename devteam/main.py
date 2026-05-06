import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uvicorn
from devteam.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

if __name__ == "__main__":
    logging.getLogger(__name__).info("DevTeam API запускается на %s:%d", config.host, config.port)
    uvicorn.run(
        "devteam.api:app",
        host=config.host,
        port=config.port,
        reload=False,
    )
