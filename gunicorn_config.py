"""Gunicorn configuration file."""

bind = "0.0.0.0:5000"
backlog = 2048

workers = 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

daemon = False
raw_env = []
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

errorlog = "-"
loglevel = "info"
accesslog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

proc_name = None

def on_starting(server):
    """Log when server starts."""
    print("Server starting...")

def on_exit(server):
    """Log when server exits."""
    print("Server stopping...")