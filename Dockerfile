FROM python:3.8

RUN apt-get update && apt-get install -y git

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]
