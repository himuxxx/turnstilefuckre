# Debian Bookworm pin kora holo jate package gulo thake
FROM python:3.11-slim-bookworm

# Install Chrome, Xvfb & required dependencies (bad dewa holo purono package gulo)
RUN apt-get update && apt-get install -y \
    wget gnupg unzip xvfb libnss3 libxss1 libasound2 \
    fonts-liberation libu2f-udev libvulkan1 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY service.py .
COPY solver.py .

ENV PORT=8191
EXPOSE 8191

CMD ["python", "service.py"]
