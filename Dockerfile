FROM python:3.11

WORKDIR /app

#Copy project files
COPY . /app/

#Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

#Exposes the Flask port
EXPOSE 5000

#Runs the app
CMD ["python", "iss_tracker.py"]

