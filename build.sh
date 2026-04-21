pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --run-syncdb
python manage.py migrate

#python scripts/create_superuser.py