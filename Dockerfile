
FROM python:3.11

WORKDIR /app

COPY *.py /app/

RUN pip install --no-cache-dir flask requests redis flask-redis geopy
RUN pip install pytest  # Ensure pytest is installed

EXPOSE 5000

CMD ["python", "iss_tracker.py"]
