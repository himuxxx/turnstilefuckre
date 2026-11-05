FROM python:3.11-slim

# Install Chrome, Xvfb & dependencies
RUN apt-get update && apt-get install -y \
    wget gnupg unzip xvfb libgconf-2-4 libnss3 libxss1 libasound2 \
    fonts-liberation libappindicator3-1 libu2f-udev libvulkan1 \
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
