FROM python:3.8

RUN apt-get update && apt-get install -y git

WORKDIR /usr/src/app
COPY . ./


RUN pip install --no-cache-dir -r requirements.txt


RUN chmod +x entrypoint.sh
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
