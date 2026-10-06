"""Entrypoint for running KORSHI TAP Admin Panel locally."""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"🚀 Запуск Admin-панели KORSHI TAP на http://{settings.ADMIN_HOST}:{settings.ADMIN_PORT}")
    uvicorn.run(
        "app.admin.app:app",
        host=settings.ADMIN_HOST,
        port=settings.ADMIN_PORT,
        reload=False,
    )
