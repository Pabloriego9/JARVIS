import argparse
import getpass
import sys
from pathlib import Path

from .backup import export_backup, restore_backup
from .config import Settings
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="JARVIS — servidor personal")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--remote", action="store_true", help="Permitir interfaz remota detrás de TLS")
    serve.add_argument("--tls-cert")
    serve.add_argument("--tls-key")
    serve.add_argument("--behind-tls-proxy", action="store_true")
    backup = commands.add_parser("backup")
    backup.add_argument("output", type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("input", type=Path)
    restore.add_argument("--destination", required=True, type=Path)
    commands.add_parser("rotate-token")
    commands.add_parser("pair")
    commands.add_parser("configure-openai")
    args = parser.parse_args()
    settings = Settings()
    settings.prepare()
    if args.command == "serve":
        if args.host not in ("127.0.0.1", "::1", "localhost"):
            if not args.remote or not ((args.tls_cert and args.tls_key) or args.behind_tls_proxy):
                parser.error("El modo remoto requiere --remote y TLS o --behind-tls-proxy.")
        import uvicorn

        from .app import create_app

        print(f"JARVIS: {settings.data_dir}; sesión local en admin.token (no compartir).")
        uvicorn.run(
            create_app(settings),
            host=args.host,
            port=args.port,
            ssl_certfile=args.tls_cert,
            ssl_keyfile=args.tls_key,
            access_log=False,
            proxy_headers=False,
        )
    elif args.command == "backup":
        password = getpass.getpass("Frase de cifrado (mínimo 12 caracteres): ")
        store = Store(settings.data_dir / "jarvis.sqlite3")
        try:
            with args.output.open("xb") as f:
                f.write(export_backup(store, password))
            print(f"Copia cifrada creada: {args.output}")
        finally:
            store.close()
    elif args.command == "restore":
        password = getpass.getpass("Frase de la copia: ")
        restore_backup(args.input.read_bytes(), password, args.destination / "jarvis.sqlite3")
        print(
            "Restauración verificada. Dispositivos revocados; emparejalos de nuevo. Una copia antigua puede recuperar memorias borradas."
        )
    elif args.command == "rotate-token":
        (settings.data_dir / "admin.token").unlink(missing_ok=True)
        print("Reiniciá JARVIS para crear una sesión local nueva.")
    elif args.command == "pair":
        from .security import Security

        store = Store(settings.data_dir / "jarvis.sqlite3")
        try:
            code = Security(store, settings).pairing()
            print(f"Código: {code['code']} — vence en {code['expires_in']} segundos.")
        finally:
            store.close()
    elif args.command == "configure-openai":
        if sys.platform != "win32":
            parser.error(
                "En el servidor Linux configurá JARVIS_OPENAI_API_KEY mediante el gestor de secretos de despliegue."
            )
        import keyring

        value = getpass.getpass("Clave OpenAI (se guarda en Windows Credential Manager): ")
        if not value.strip():
            parser.error("La clave no puede estar vacía.")
        keyring.set_password("JARVIS", "openai", value.strip())
        print("Credencial guardada en Windows. Reiniciá el backend y comprobá el modelo desde Ajustes.")


if __name__ == "__main__":
    main()
