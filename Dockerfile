FROM python:3.9-alpine

ARG UID=1000
ARG COMMIT_HASH=''
ARG GIT_BRANCH=''

ENV COMMIT_HASH $COMMIT_HASH
ENV GIT_BRANCH $GIT_BRANCH

WORKDIR /metadata
COPY . /metadata

RUN apk update && \
        apk add postgresql-libs && \
        apk add --virtual .build-deps alpine-sdk musl-dev postgresql-dev && \
        pip --disable-pip-version-check --no-cache-dir install poetry && \
        poetry install && \
        apk --purge del .build-deps

RUN adduser --system -u $UID metadata

USER metadata

ENTRYPOINT ["lidarr-metadata-server"]
