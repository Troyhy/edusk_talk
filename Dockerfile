FROM python:3.9

ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive
ENV APP_PATH /app
ENV REQUIREMENTS /app/requirements*.txt

WORKDIR $APP_PATH

COPY requirements*.txt /app/
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r ${REQUIREMENTS}
COPY . /app/


CMD ["/usr/local/bin/python3" ,"/app/main.py"]
