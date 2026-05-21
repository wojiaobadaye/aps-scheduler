"""Production WSGI entry point for gunicorn."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, scheduler, db, Job

app = create_app()

with app.app_context():
    jobs = Job.query.filter_by(enabled=True).all()
    for job in jobs:
        from app.scheduler import add_job_to_scheduler
        add_job_to_scheduler(job.job_id, job.script_name, job.trigger, job.trigger_args)

scheduler.start()
