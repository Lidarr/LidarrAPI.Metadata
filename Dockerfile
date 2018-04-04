FROM python:2

ARG UID=1000

WORKDIR /metadata
COPY . /metadata

EXPOSE 5000

RUN pip install --process-dependency-links .

RUN useradd -u $UID metadata

USER metadata

CMD ["lidarr-metadata-server"]