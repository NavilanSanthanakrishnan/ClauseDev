# Electron Guide

## Role
- Desktop wrapper around the web build.
- Responsible for window creation, preload behavior, and packaging alignment.

## Directory Map
- `main/`: Electron main process
- `preload/`: isolated bridge code
- `build/`: static assets for packaging

## Rules
- Keep preload minimal and explicit.
- Do not put app business logic in Electron when it belongs in web/backend layers.
- Packaging should continue to target macOS `.dmg` and Windows NSIS `.exe`.
- If the web app can do something directly, prefer that over adding Electron-only behavior.
