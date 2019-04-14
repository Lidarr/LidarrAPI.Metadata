FROM python:2-alpine

ARG UID=1000
ARG COMMIT_HASH=''
ARG GIT_BRANCH=''

ENV COMMIT_HASH $COMMIT_HASH
ENV GIT_BRANCH $GIT_BRANCH

WORKDIR /metadata
COPY . /metadata

RUN apk update && \
 apk add postgresql-libs && \
 apk add --virtual .build-deps gcc musl-dev postgresql-dev && \
 pip install --no-cache-dir .[deploy] && \
 apk --purge del .build-deps

RUN adduser --system -u $UID metadata

USER metadata

ENTRYPOINT ["gunicorn", "lidarrmetadata.api:app", "-b", "0.0.0.0:5001", "-w", "4"]