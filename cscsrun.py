#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "nicegui",
#     "fabric",
# ]
# ///
from __future__ import annotations

import paramiko
from fabric import Connection
from nicegui import run, ui


def ssh_exec(
    hostname: str,
    username: str,
    port: int,
    password: str,
    command: str,
    environment: dict[str, str] | None,
    forward_x11: bool,  # noqa: ARG001 — accepted but unused; Fabric/Paramiko don't support X11 forwarding
) -> tuple[str, str, int]:
    """Execute a command on a remote host via SSH.

    Returns (stdout, stderr, exit_code).
    """
    connect_kwargs: dict = {}
    if password:
        connect_kwargs["password"] = password
    conn = Connection(
        host=hostname,
        user=username,
        port=port,
        connect_kwargs=connect_kwargs,
    )
    conn.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        result = conn.run(command, hide=True, warn=True, env=environment or None)
        return result.stdout, result.stderr, result.return_code
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

# -- Connection card --
with ui.card().classes("w-full max-w-2xl mx-auto mt-4"):
    ui.label("Connection").classes("text-lg font-bold")
    hostname = ui.input("Hostname", placeholder="login.example.com").classes("w-full")
    with ui.row().classes("w-full"):
        username = ui.input("Username").classes("flex-grow")
        port = ui.number("Port", value=22, min=1, max=65535, precision=0).classes("w-24")
    password = ui.input(
        "Password",
        placeholder="Leave empty for key-based auth",
        password=True,
        password_toggle_button=True,
    ).classes("w-full")

# -- Command card --
with ui.card().classes("w-full max-w-2xl mx-auto mt-4"):
    ui.label("Command").classes("text-lg font-bold")
    command = ui.input("Command to execute", placeholder="squeue --me").classes("w-full")
    x11_switch = ui.switch("Forward X11")

# -- Environment variables card --
env_vars: list[dict[str, str]] = []

with ui.card().classes("w-full max-w-2xl mx-auto mt-4"):
    ui.label("Environment Variables").classes("text-lg font-bold")
    env_column = ui.column().classes("w-full gap-2")

    def add_env_var() -> None:
        entry: dict[str, str] = {"key": "", "value": ""}
        env_vars.append(entry)

        with env_column:
            with ui.row().classes("w-full items-center") as row:
                ui.input("Key", on_change=lambda e, ent=entry: ent.__setitem__("key", e.value)).classes(
                    "flex-grow"
                )
                ui.input("Value", on_change=lambda e, ent=entry: ent.__setitem__("value", e.value)).classes(
                    "flex-grow"
                )

                def remove(r=row, ent=entry) -> None:
                    env_vars.remove(ent)
                    r.delete()

                ui.button(icon="delete", on_click=remove).props("flat dense color=negative")

    ui.button("Add Variable", icon="add", on_click=add_env_var).props("flat")

# -- Output + Run --
with ui.card().classes("w-full max-w-2xl mx-auto mt-4"):
    ui.label("Output").classes("text-lg font-bold")
    log = ui.log(max_lines=500).classes("w-full h-64")

    async def execute() -> None:
        if not hostname.value:
            ui.notify("Hostname is required", type="negative")
            return
        if not username.value:
            ui.notify("Username is required", type="negative")
            return
        if not command.value:
            ui.notify("Command is required", type="negative")
            return

        environment = {e["key"]: e["value"] for e in env_vars if e["key"]}

        run_button.disable()
        log.clear()
        try:
            stdout, stderr, exit_code = await run.io_bound(
                ssh_exec,
                hostname=hostname.value,
                username=username.value,
                port=int(port.value),
                password=password.value,
                command=command.value,
                environment=environment,
                forward_x11=x11_switch.value,
            )
            if stdout:
                log.push(stdout.rstrip("\n"))
            if stderr:
                log.push(f"[stderr]\n{stderr.rstrip(chr(10))}")
            log.push(f"[exit code: {exit_code}]")
        except paramiko.AuthenticationException:
            ui.notify("Authentication failed", type="negative")
            log.push("[error] Authentication failed")
        except paramiko.SSHException as exc:
            ui.notify(f"SSH error: {exc}", type="negative")
            log.push(f"[error] SSH error: {exc}")
        except OSError as exc:
            ui.notify(f"Connection error: {exc}", type="negative")
            log.push(f"[error] Connection error: {exc}")
        finally:
            run_button.enable()

    run_button = ui.button("Run", icon="play_arrow", on_click=execute).props("color=primary")

ui.run(title="cscsrun", dark=True)
