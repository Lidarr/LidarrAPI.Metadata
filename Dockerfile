FROM python:3.9-bookworm

ARG UID=1000
ARG COMMIT_HASH=''
ARG GIT_BRANCH=''

ENV COMMIT_HASH $COMMIT_HASH
ENV GIT_BRANCH $GIT_BRANCH

WORKDIR /metadata

ENV POETRY_VIRTUALENVS_CREATE=false \
        POETRY_NO_INTERACTION=1 \
        POETRY_CACHE_DIR='/var/cache/pypoetry' \
        POETRY_HOME='/usr/local'

# Copy only dependency files first to leverage Docker layer caching
COPY pyproject.toml poetry.lock ./

# Install Poetry version compatible with requests 2.25.1
RUN pip --disable-pip-version-check --no-cache-dir install poetry==1.4.2 && \
    poetry install --only=main --no-root

# Copy the rest of the application code
COPY . /metadata

# Install the current project 
RUN poetry install --only=main

RUN adduser --system -u $UID metadata

USER metadata

ENTRYPOINT ["uvicorn"]
CMD ["lidarrmetadata.hybrid_app:app", "--host", "0.0.0.0", "--port", "5001"]
