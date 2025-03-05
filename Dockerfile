
FROM python:3.11

WORKDIR /app

COPY *.py /app/

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install pytest  #Ensure pytest is installed

EXPOSE 5000

CMD ["python", "iss_tracker.py"]
