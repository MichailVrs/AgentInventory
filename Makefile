init: data-remove create-ssl-certificate images-build-and-pull   db-migrate assets-build

db-migrate:
	docker compose run --rm server /venv/bin/python manage.py db upgrade
	docker compose down

assets-build:
	docker compose run --rm server /venv/bin/python manage.py assets build
	docker compose down

create-ssl-certificate:
	openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout staks/ssl/certs/certificate.key -out staks/ssl/certs/certificate.crt -config staks/ssl/openssl.cnf

data-remove:
	docker compose down --remove-orphans --volumes

osqueryi:
	docker compose run --rm --no-deps --entrypoint=osqueryi agent 


images-build-and-pull: nginx-image-pull postgresql-image-pull redis-image-pull  python-image-build osquery-image-build

nginx-image-pull: 
	docker pull cr.yandex/mirror/nginx
	docker tag cr.yandex/mirror/nginx inventory-nginx
	docker rmi cr.yandex/mirror/nginx

postgresql-image-pull:
	docker pull registry.red-soft.ru/ubi8/postgresql-17:17-260414
	docker tag registry.red-soft.ru/ubi8/postgresql-17:17-260414 inventory-postgresql
	docker rmi registry.red-soft.ru/ubi8/postgresql-17:17-260414

redis-image-pull:
	docker pull registry.red-soft.ru/ubi8/redis:8-260414
	docker tag registry.red-soft.ru/ubi8/redis:8-260414 inventory-redis
	docker rmi registry.red-soft.ru/ubi8/redis:8-260414

python-image-build:
	docker build --rm -t inventory-python docker/python/

osquery-image-build:
	docker build --rm -t inventory-osquery docker/osquery/
