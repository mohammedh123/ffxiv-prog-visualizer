FROM python:3.10
COPY resources/LiberationSerif-Regular.ttf .
RUN mkdir -p /usr/share/fonts/truetype/
RUN install -m644 LiberationSerif-Regular.ttf /usr/share/fonts/truetype/
RUN rm LiberationSerif-Regular.ttf
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt
COPY main.py ./
COPY cache.py cache.json config.ini abilities.json constants.py ./
CMD ["python", "main.py"]