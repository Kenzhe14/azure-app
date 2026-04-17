import os
import logging
import uuid
from flask import Flask, request, jsonify
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# LOG
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("CloudAnalyzer")

app = Flask(__name__)

# AWS
try:
    session = boto3.Session(
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )
    rekognition = session.client('rekognition')
    dynamodb = session.resource('dynamodb').Table('ImageAnalysisLog')
    logger.info("AWS SDK успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации AWS: {e}")

@app.route('/analyze', methods=['POST'])
def analyze():
    analysis_id = str(uuid.uuid4())
    logger.info(f"Начало анализа. ID запроса: {analysis_id}")

    if 'image' not in request.files:
        logger.warning(f"ID {analysis_id}: Файл не найден в запросе")
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files['image']
    image_bytes = file.read()

    try:
        # 1. Анализ в AWS Rekognition
        logger.info(f"ID {analysis_id}: Отправка в AWS Rekognition")
        rek_response = rekognition.detect_faces(
            Image={'Bytes': image_bytes},
            Attributes=['ALL']
        )
        
        # Упростим результат для логов
        faces_count = len(rek_response.get('FaceDetails', []))
        logger.info(f"ID {analysis_id}: Найдено лиц: {faces_count}")

        # 2. Сохранение в DynamoDB
        logger.info(f"ID {analysis_id}: Сохранение данных в DynamoDB")
        dynamodb.put_item(Item={
            'AnalysisId': analysis_id,
            'Timestamp': str(logging.time.time()),
            'FacesFound': faces_count,
            'RawData': str(rek_response['FaceDetails'][:2]) # Сохраняем часть для экономии места
        })

        return jsonify({
            "status": "success",
            "analysis_id": analysis_id,
            "faces_detected": faces_count,
            "details": rek_response['FaceDetails']
        })

    except ClientError as e:
        logger.error(f"ID {analysis_id}: Ошибка AWS: {e.response['Error']['Message']}")
        return jsonify({"error": "AWS Service Error"}), 500
    except Exception as e:
        logger.error(f"ID {analysis_id}: Критическая ошибка: {str(e)}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/')
def home():
    return "API is running! Use POST /analyze to process images."

if __name__ == '__main__':
    app.run(debug=True)