web: gunicorn app:app --worker-class=gthread --workers=1 --threads=8 --timeout=60 --keep-alive=5 --max-requests=500 --max-requests-jitter=50
