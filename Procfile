web: gunicorn app:app --worker-class=gevent --workers=2 --worker-connections=100 --timeout=120 --keep-alive=5 --max-requests=500 --max-requests-jitter=50
