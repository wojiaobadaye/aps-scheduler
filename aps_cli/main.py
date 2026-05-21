"""aps_cli: manage scripts, jobs, and Docker containers via HTTP API."""

import json
import os
import subprocess
import sys

import click
import requests

API_BASE = os.getenv("APS_API_BASE", "http://localhost:5000")


# ── helpers ───────────────────────────────────────────────────

def _req(method, path, **kwargs):
    url = f"{API_BASE}/api/{path}"
    try:
        r = requests.request(method, url, **kwargs, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        click.echo("Error: cannot connect to API server at %s" % API_BASE, err=True)
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        try:
            msg = e.response.json().get("error", str(e))
        except Exception:
            msg = str(e)
        click.echo("Error: %s" % msg, err=True)
        sys.exit(1)


def _docker_cmd(*args):
    try:
        subprocess.run(["docker", *args], check=True)
    except subprocess.CalledProcessError as e:
        click.echo("Docker command failed: %s" % str(e), err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo("Error: docker not found in PATH", err=True)
        sys.exit(1)


# ── script commands ──────────────────────────────────────────

@click.group()
def script():
    """Manage task scripts."""


@script.command("list")
def script_list():
    """List all scripts."""
    for s in _req("GET", "scripts"):
        click.echo("%3d  %-24s  %s" % (s["id"], s["name"], s.get("description", "")))


@script.command("show")
@click.argument("script_id", type=int)
def script_show(script_id):
    """Show script details."""
    s = _req("GET", "scripts/%d" % script_id)
    click.echo("ID:          %d" % s["id"])
    click.echo("Name:        %s" % s["name"])
    click.echo("Description: %s" % s.get("description", ""))
    click.echo("--- content ---")
    click.echo(s["content"])


@script.command("create")
@click.option("-n", "--name", required=True, help="Script name")
@click.option("-d", "--description", default="", help="Description")
@click.option("-f", "--file", "file_path", help="Read script content from file")
@click.option("--content", help="Script content as string")
def script_create(name, description, file_path, content):
    """Create a new script."""
    if file_path:
        with open(file_path) as f:
            content = f.read()
    if not content:
        click.echo("Error: provide --file or --content", err=True)
        sys.exit(1)
    s = _req("POST", "scripts", json={"name": name, "description": description, "content": content})
    click.echo("Created script id=%d" % s["id"])


@script.command("update")
@click.argument("script_id", type=int)
@click.option("-n", "--name", help="New name")
@click.option("-d", "--description", help="New description")
@click.option("-f", "--file", "file_path", help="New content from file")
@click.option("--content", help="New content as string")
def script_update(script_id, name, description, file_path, content):
    """Update a script."""
    body = {}
    if name:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if file_path:
        with open(file_path) as f:
            body["content"] = f.read()
    elif content:
        body["content"] = content

    if not body:
        click.echo("Nothing to update", err=True)
        sys.exit(1)
    s = _req("PUT", "scripts/%d" % script_id, json=body)
    click.echo("Updated script id=%d" % s["id"])


@script.command("delete")
@click.argument("script_id", type=int)
def script_delete(script_id):
    """Delete a script."""
    _req("DELETE", "scripts/%d" % script_id)
    click.echo("Deleted script id=%d" % script_id)


# ── job commands ─────────────────────────────────────────────

@click.group()
def job():
    """Manage scheduler jobs."""


@job.command("list")
def job_list():
    """List all jobs."""
    for j in _req("GET", "jobs"):
        click.echo(
            "%-24s  script=%-16s  trigger=%-10s  enabled=%s"
            % (j["job_id"], j["script_name"], j["trigger"], j["enabled"])
        )


@job.command("show")
@click.argument("job_id")
def job_show(job_id):
    """Show a job's details."""
    j = _req("GET", "jobs/%s" % job_id)
    for k, v in j.items():
        click.echo("%-16s %s" % (k + ":", v))


@job.command("create")
@click.option("--job-id", required=True, help="Unique job identifier")
@click.option("--script", required=True, help="Script name to execute")
@click.option("--trigger", required=True, type=click.Choice(["interval", "cron", "date"]))
@click.option("--trigger-args", default="{}", help='JSON args e.g. \'{"seconds": 30}\'')
@click.option("--enabled/--disabled", default=True)
def job_create(job_id, script, trigger, trigger_args, enabled):
    """Create a new scheduled job."""
    try:
        json.loads(trigger_args)
    except json.JSONDecodeError:
        click.echo("Error: trigger-args must be valid JSON", err=True)
        sys.exit(1)
    j = _req(
        "POST", "jobs",
        json={
            "job_id": job_id,
            "script_name": script,
            "trigger": trigger,
            "trigger_args": trigger_args,
            "enabled": enabled,
        },
    )
    click.echo("Created job %s" % j["job_id"])


@job.command("update")
@click.argument("job_id")
@click.option("--script", help="Script name")
@click.option("--trigger", type=click.Choice(["interval", "cron", "date"]), help="Trigger type")
@click.option("--trigger-args", help='JSON trigger args')
@click.option("--enabled", type=bool, help="Enable or disable")
def job_update(job_id, script, trigger, trigger_args, enabled):
    """Update a job."""
    body = {}
    if script:
        body["script_name"] = script
    if trigger:
        body["trigger"] = trigger
    if trigger_args:
        try:
            json.loads(trigger_args)
        except json.JSONDecodeError:
            click.echo("Error: trigger-args must be valid JSON", err=True)
            sys.exit(1)
        body["trigger_args"] = trigger_args
    if enabled is not None:
        body["enabled"] = enabled
    if not body:
        click.echo("Nothing to update", err=True)
        sys.exit(1)
    j = _req("PUT", "jobs/%s" % job_id, json=body)
    click.echo("Updated job %s" % j["job_id"])


@job.command("delete")
@click.argument("job_id")
def job_delete(job_id):
    """Delete a job."""
    _req("DELETE", "jobs/%s" % job_id)
    click.echo("Deleted job %s" % job_id)


@job.command("pause")
@click.argument("job_id")
def job_pause(job_id):
    """Pause a job."""
    _req("POST", "jobs/%s/pause" % job_id)
    click.echo("Paused job %s" % job_id)


@job.command("resume")
@click.argument("job_id")
def job_resume(job_id):
    """Resume a paused job."""
    _req("POST", "jobs/%s/resume" % job_id)
    click.echo("Resumed job %s" % job_id)


@job.command("trigger")
@click.argument("job_id")
def job_trigger(job_id):
    """Manually trigger a job."""
    _req("POST", "jobs/%s/trigger" % job_id)
    click.echo("Triggered job %s" % job_id)


@job.command("logs")
@click.argument("job_id")
@click.option("--limit", default=20, help="Number of logs to show")
def job_logs(job_id, limit):
    """Show execution logs for a job."""
    logs = _req("GET", "jobs/%s/logs" % job_id, params={"limit": limit})
    if not logs:
        click.echo("No logs found.")
        return
    for log in logs:
        click.echo(
            "%-24s  %-8s  %s"
            % (log.get("started_at", "?"), log["status"], log.get("error", "")[:60])
        )


# ── scheduler commands ────────────────────────────────────────

@click.group()
def sched():
    """Show scheduler status."""


@sched.command("status")
def sched_status():
    """Show scheduler and job status."""
    st = _req("GET", "scheduler/status")
    click.echo("Running: %s" % st["running"])
    click.echo("")
    for j in st.get("jobs", []):
        click.echo("  %-24s  next=%-24s  trigger=%s" % (j["id"], j["next_run_time"] or "now", j["trigger"]))


# ── docker commands ──────────────────────────────────────────

@click.group()
def docker():
    """Manage Docker container."""


@docker.command("up")
@click.option("-d", "--detach", is_flag=True, help="Run in background")
def docker_up(detach):
    """Build and start the container."""
    args = ["compose", "up", "--build"]
    if detach:
        args.append("-d")
    _docker_cmd(*args)


@docker.command("down")
def docker_down():
    """Stop and remove the container."""
    _docker_cmd("compose", "down")


@docker.command("logs")
@click.option("-f", "--follow", is_flag=True)
def docker_logs(follow):
    """Show container logs."""
    args = ["compose", "logs"]
    if follow:
        args.append("-f")
    _docker_cmd(*args)


@docker.command("restart")
def docker_restart():
    """Restart the container."""
    _docker_cmd("compose", "restart")


@docker.command("ps")
def docker_ps():
    """List containers."""
    _docker_cmd("compose", "ps")


# ── main CLI ─────────────────────────────────────────────────

@click.group()
def cli():
    """aps_cli - APScheduler management tool."""


cli.add_command(script)
cli.add_command(job)
cli.add_command(sched)
cli.add_command(docker)

if __name__ == "__main__":
    cli()
