FROM ubuntu:22.04
RUN apt-get update && apt-get install -y python3.10 python3-pip

WORKDIR /app

# Установка необходимых системных пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Установка Python и проверка версии
RUN python --version && pip --version

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка зависимостей Python
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всего приложения
COPY . .

# Создаем необходимые директории
RUN mkdir -p data/knowledge_base/docs data/reports logs

# Опционально: инициализация базы данных и знаний
RUN python setup.py

# Запуск приложения
CMD ["python", "main.py"] 