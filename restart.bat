@echo off
echo Stopping and removing containers...
docker compose down
echo.
echo Starting containers in detached mode...
docker compose up -d
echo.
echo Containers have been relaunched.
pause