---------------------------------
Getting everything up and running
---------------------------------

1. Rename .env.example to .env

2. Add your email and Stripe credentials to your .env file.

3. Open a terminal configured to run Docker and then run:

docker-compose down -v
docker-compose up --build
docker-compose exec web dataweb db reset --with-testdb
docker-compose exec web dataweb add all
docker-compose exec web dataweb flake8
docker-compose exec web dataweb test
