Write-Host "1. Data cleanup (data-remove)..."
docker compose down --remove-orphans --volumes

Write-Host "2. Generating SSL certificates (create-ssl-certificate)..."
try {
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout staks/ssl/certs/certificate.key -out staks/ssl/certs/certificate.crt -config staks/ssl/openssl.cnf
} catch {
    Write-Host "openssl not found locally. Falling back to Docker (nginx)..."
    docker run --rm -v "$($PWD.Path):/work" -w /work cr.yandex/mirror/nginx openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout staks/ssl/certs/certificate.key -out staks/ssl/certs/certificate.crt -config staks/ssl/openssl.cnf
}

Write-Host "3. Preparing images (images-build-and-pull)..."
docker pull cr.yandex/mirror/nginx
docker tag cr.yandex/mirror/nginx inventory-nginx
docker rmi cr.yandex/mirror/nginx

docker pull registry.red-soft.ru/ubi8/postgresql-17:17-260414
docker tag registry.red-soft.ru/ubi8/postgresql-17:17-260414 inventory-postgresql
docker rmi registry.red-soft.ru/ubi8/postgresql-17:17-260414

docker pull registry.red-soft.ru/ubi8/redis:8-260414
docker tag registry.red-soft.ru/ubi8/redis:8-260414 inventory-redis
docker rmi registry.red-soft.ru/ubi8/redis:8-260414

Write-Host "Building Python image..."
docker build --rm -t inventory-python docker/python/

Write-Host "Building Osquery image..."
docker build --rm -t inventory-osquery docker/osquery/

Write-Host "4. Database migration (db-migrate)..."
docker compose run --rm server /venv/bin/python manage.py db upgrade
docker compose down

Write-Host "5. Starting system..."
docker compose up -d

Write-Host "Done! System is running in background."
