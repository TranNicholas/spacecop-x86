# Image: disposable browser smoke check; never part of the target or observer.
# Build inputs: pinned Playwright image, pinned Python packages, and smoke.py.
FROM mcr.microsoft.com/playwright/python:v1.56.0-noble@sha256:a7f6cf3ae520c9d670ad956572c13747ed5abdbba5123a01526f873ed1662528 AS runtime
LABEL org.opencontainers.image.title="SpaceCOP COSMOS browser smoke check" \
      lab.browser.python-dependencies="playwright==1.56.0 greenlet==3.2.4 pyee==13.0.0"
RUN pip install --no-cache-dir playwright==1.56.0 greenlet==3.2.4 pyee==13.0.0
WORKDIR /opt/spacecop-lab
COPY smoke.py ./browser_smoke.py
ENTRYPOINT ["python", "browser_smoke.py"]
