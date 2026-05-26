FROM python:3.12-slim

# 安装 Miniconda
RUN apt-get update && apt-get install -y wget && \
    wget -O /tmp/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh && \
    apt-get remove -y wget && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/conda/bin:${PATH}"

WORKDIR /app

RUN addgroup --system app && adduser --system --group app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 确保 scripts 目录可读写，确保 conda envs 目录 app 用户可写入
RUN mkdir -p /app/scripts && mkdir -p /opt/conda/envs && chown -R app:app /app/scripts /opt/conda/envs

EXPOSE 5000
USER app

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--access-logfile", "-", "wsgi:app"]
