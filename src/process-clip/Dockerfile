# Use AWS Lambda Python 3.11 base image
FROM public.ecr.aws/lambda/python:3.11

# Install system dependencies for OpenCV and build tools
# Disable SSL verification due to certificate issues
RUN echo "sslverify=0" >> /etc/yum.conf \
    && yum install -y \
    libgomp \
    gcc \
    gcc-c++ \
    && yum clean all \
    && rm -rf /var/cache/yum

# Copy requirements file
COPY requirements_lambda.txt ${LAMBDA_TASK_ROOT}/

# Install Python dependencies
# Using --no-cache-dir to reduce image size
# Disable SSL verification due to certificate issues
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r ${LAMBDA_TASK_ROOT}/requirements_lambda.txt

# Download spaCy language model
# This downloads the small English model (~12MB) for NLP classification
RUN python -m spacy download en_core_web_sm --no-cache-dir

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/
COPY classification_integration.py ${LAMBDA_TASK_ROOT}/

# Copy smart_framing module
COPY smart_framing/ ${LAMBDA_TASK_ROOT}/smart_framing/

# Copy classification system (plugin-based architecture)
COPY classification/ ${LAMBDA_TASK_ROOT}/classification/

# Set the CMD to your handler
CMD [ "lambda_function.lambda_handler" ]
