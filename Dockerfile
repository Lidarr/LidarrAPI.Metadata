FROM python:2-alpine

ARG UID=1000
ARG COMMIT_HASH=''
ARG GIT_BRANCH=''

ENV COMMIT_HASH = $COMMIT_HASH
ENV GIT_BRANCH = $GIT_BRANCH

WORKDIR /metadata
COPY . /metadata

EXPOSE 5000

RUN apk update && \
 apk add postgresql-libs && \
 apk add --virtual .build-deps gcc musl-dev postgresql-dev && \
 pip install --no-cache-dir . && \
 apk --purge del .build-deps

RUN adduser --system -u $UID metadata

USER metadata

CMD ["lidarr-metadata-server"]